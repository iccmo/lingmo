"""Support helpers for the main chapter-generation pipeline."""

from __future__ import annotations

import json

from novel_writer.routers.deps import get_db


def _chapter_number(value) -> int | None:
    """Parse chapter numbers from numeric or simple Chinese text values."""
    if value in (None, ""):
        return None
    text = str(value).strip()
    if text.isdigit():
        return int(text)
    numerals = {"零": 0, "〇": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
    for char in ("第", "章", "节", "回", "内", "左", "右", "前", "后", " "):
        text = text.replace(char, "")
    if text == "十":
        return 10
    if "十" in text:
        left, _, right = text.partition("十")
        tens = numerals.get(left, 1) if left else 1
        ones = numerals.get(right, 0) if right else 0
        return tens * 10 + ones
    if len(text) == 1 and text in numerals:
        return numerals[text]
    return None


SOUL_POLARITY_MAP = {
    "freedom-fate": ("自由vs命运", "在这个世界里，每一个选择都引向注定的结局"),
    "truth-deception": ("真实vs谎言", "真相和谎言交织在一起"),
    "desire-constraint": ("欲望vs克制", "每个人都在压抑自己真正想要的"),
    "individual-society": ("个体vs群体", "一个人对抗整个世界的规则"),
    "scale-intimacy": ("宏大vs亲密", "宇宙的浩瀚与个人的渺小"),
}


def _clean_text(value, limit: int = 160) -> str:
    text = str(value or "").strip()
    return text[:limit]


def _format_blueprint_line(character: dict) -> str:
    parts = [
        f"{_clean_text(character.get('name'), 32)}（{_clean_text(character.get('role') or '角色', 16)}）",
    ]
    for label, key in (
        ("出场", "entrance"),
        ("标志", "signature"),
        ("创伤", "coreWound"),
        ("表面", "surfaceTrait"),
        ("隐藏", "hiddenSelf"),
        ("弧线", "arcStart"),
        ("终点", "arcEnd"),
        ("执念", "obsession"),
        ("台词", "voiceSample"),
    ):
        text = _clean_text(character.get(key), 80)
        if text:
            parts.append(f"{label}:{text}")
    return "- " + "；".join(parts)


def build_creation_brief(db, novel_id: str) -> str:
    """Build persisted author-level creative constraints for generation prompts."""
    sections: list[str] = []
    try:
        fp = db.get_soul_fingerprint(novel_id)
    except Exception:
        fp = None
    if fp and fp.get("polarity") and fp.get("answer"):
        polarity_name, polarity_hint = SOUL_POLARITY_MAP.get(fp["polarity"], (fp["polarity"], ""))
        sections.append(
            "【灵魂注入 · 核心矛盾】\n"
            f"- 矛盾：{polarity_name}\n"
            + (f"- 张力：{polarity_hint}\n" if polarity_hint else "")
            + f"- 作者回答：{_clean_text(fp.get('answer'), 260)}\n"
            "- 写作法则：每一章都要追问这个矛盾，但不要给出廉价终极答案。"
        )

    try:
        blueprints = db.get_character_blueprints(novel_id)
    except Exception:
        blueprints = []
    if blueprints:
        lines = [_format_blueprint_line(character) for character in blueprints[:8] if character.get("name")]
        if lines:
            sections.append(
                "【角色蓝图硬约束】\n"
                "以下人物的出场、创伤、说话方式、弧线是长期设定。生成时必须维护人物一致性，不能随意改写核心动机。\n"
                + "\n".join(lines)
            )

    return "\n\n".join(sections)


def _get_provider(novel_id: str | None = None) -> dict:
    db = get_db()
    provider_id = "deepseek"
    if novel_id:
        novel = db.get_novel(novel_id)
        if novel:
            provider_id = novel.get("provider_id", "deepseek")
    provider = db.get_provider(provider_id)
    if not provider or not provider.get("api_key"):
        for candidate in db.list_providers():
            if candidate.get("api_key"):
                provider = db.get_provider(candidate["id"])
                break
    return provider or {
        "id": "deepseek",
        "base_url": "https://api.deepseek.com",
        "api_key": "",
        "models": ["deepseek-v4-pro"],
    }


def _generator_and_model(novel_id: str):
    from novel_writer.config import Config
    from novel_writer.generator import Generator

    provider = _get_provider(novel_id)
    models = provider.get("models", ["deepseek-v4-pro"])
    model = "deepseek-v4-pro" if "deepseek-v4-pro" in str(models) else models[0]
    cfg = Config(
        openai_api_key=provider.get("api_key", ""),
        openai_base_url=provider.get("base_url", ""),
        model=model,
    )
    return Generator(cfg), model


def editor_review(
    novel_id: str,
    chapter_num: int,
    content: str,
    quality_issues: list[str] | None = None,
) -> dict:
    """Review a chapter and return line-specific editing feedback."""
    try:
        db = get_db()
        gen, model = _generator_and_model(novel_id)

        chars = db.get_character_state(novel_id, chapter_num - 1) if chapter_num > 1 else []
        char_context = (
            "\n".join(
                f"- {char['char_name']}: 情绪={char.get('emotion','?')}, 身体={char.get('physical_state','?')}, 位置={char.get('location','?')}"
                for char in chars[:5]
            )
            if chars
            else "无历史数据"
        )

        foreshadowing = db.get_active_foreshadowing(novel_id)
        foreshadowing_context = (
            "\n".join(
                f"- #{thread['id']}: {thread['description'][:60]} (Ch{thread['created_chapter']}, 到期Ch{thread.get('due_by_chapter','?')})"
                for thread in foreshadowing[:5]
            )
            if foreshadowing
            else "无活跃伏笔"
        )

        issues_text = (
            "\n".join(f"- {issue}" for issue in quality_issues)
            if quality_issues
            else "无"
        )

        prompt = f"""你是小说编辑。审读以下章节，给出具体的、可操作的修改意见。

# 角色状态（上一章）
{char_context}

# 活跃伏笔（需在本章或近期回收）
{foreshadowing_context}

# 质量评审发现的问题
{issues_text}

# 待审章节正文（前3000字）
{content[:3000]}

# 你的任务
给出具体的、定位到问题句子的修改意见。格式：
第X段第Y句：「原文」——> 问题：XXX ——> 建议：XXX

只指出最重要的3-5个问题。不要泛泛而谈。每个问题必须精确到一个具体句子。
不要打分。不要说"整体不错"。只说问题。
"""
        result = gen._call_llm_with_retry([{"role": "user", "content": prompt}], max_tokens=1024)
        return {"feedback": result or "", "model": model}
    except Exception as exc:
        return {"feedback": "", "error": str(exc)[:100]}


def targeted_rewrite(novel_id: str, chapter_num: int, content: str, editor_feedback: str) -> str:
    """Rewrite only the portions flagged by editor feedback."""
    if not editor_feedback:
        return content

    try:
        gen, _model = _generator_and_model(novel_id)
        prompt = f"""你是小说作者。编辑给了以下修改意见。请根据意见修改原文。

# 编辑意见
{editor_feedback}

# 原文
{content[:4000]}

# 规则
1. 只修改编辑指出的问题句子。不要重写整章。
2. 保持原有风格、角色声音、情节走向不变。
3. 修改后直接返回全文。不要解释修改了什么。
"""
        result = gen._call_llm_with_retry([{"role": "user", "content": prompt}], max_tokens=4096)
        return result if result and len(result) > len(content) * 0.5 else content
    except Exception:
        return content


def build_constraints(novel_id: str, next_chapter: int) -> str:
    """Build a compact constraint block from story-bible data."""
    db = get_db()
    constraints = []

    novel = db.get_novel(novel_id) or {}
    static_chars = novel.get("characters", [])
    char_map = {character["name"]: character for character in static_chars if character.get("name")}

    chars = db.get_character_state(novel_id)
    if hasattr(db, "get_all_character_states"):
        all_states = db.get_all_character_states(novel_id, up_to_chapter=next_chapter - 1)
    else:
        all_states = chars
    latest: dict[str, dict] = {}
    for character in all_states:
        name = character.get("char_name")
        if not name:
            continue
        chapter_num = int(character.get("chapter_num") or 0)
        previous = latest.get(name)
        if previous is None or chapter_num >= int(previous.get("chapter_num") or 0):
            latest[name] = character

    for name, info in char_map.items():
        traits = []
        if info.get("personality"):
            traits.append(f"性格：{info['personality'][:30]}")
        if info.get("role") and info["role"] != "配角":
            traits.append(f"角色：{info['role']}")
        if traits:
            constraints.append(f"🎭 {name} — {'；'.join(traits)}")

    recent_latest = sorted(
        latest.items(),
        key=lambda item: (int(item[1].get("chapter_num") or 0), item[0]),
        reverse=True,
    )
    for name, character in recent_latest[:8]:
        parts = [name]
        if character.get("physical_state") and character["physical_state"] != "健康":
            parts.append(character["physical_state"])
            if "伤" in str(character["physical_state"]) or "残" in str(character["physical_state"]):
                parts.append("不能使用该部位")
            if character["physical_state"] == "死亡":
                parts.append("不能出场（除非幻觉/回忆）")
        if character.get("emotion"):
            emotion = character["emotion"]
            if "愤怒" in str(emotion):
                parts.append("不会示弱或原谅")
            if "悲伤" in str(emotion) or "绝望" in str(emotion):
                parts.append("不会主动采取行动")
        if character.get("location"):
            parts.append(f"当前在{character['location']}")
        if len(parts) > 1:
            constraints.append(" - ".join(parts))

    if chars and len(chars) > 2:
        last_seen: dict[str, int] = {}
        for character in all_states:
            name = character.get("char_name")
            if not name:
                continue
            chapter_num = int(character.get("chapter_num") or 0)
            last_seen[name] = max(last_seen.get(name, 0), chapter_num)
        recent_names = {
            name
            for name, chapter_num in last_seen.items()
            if chapter_num >= max(1, next_chapter - 5)
        }
        dormant = set(last_seen) - recent_names
        if dormant:
            dormant_names = sorted(dormant, key=lambda name: (last_seen.get(name, 0), name))
            constraints.append(f"💤 久未出场：{', '.join(dormant_names[:3])} — 考虑本章让其出现或暗示存在")

    if novel.get("power_system"):
        constraints.append(f"🌍 修炼体系：{novel['power_system'][:60]}")
    if novel.get("world_rules"):
        try:
            rules = json.loads(novel["world_rules"]) if isinstance(novel["world_rules"], str) else novel["world_rules"]
            if isinstance(rules, list) and rules:
                constraints.append(f"🌍 世界规则：{'；'.join(str(rule)[:40] for rule in rules[:3])}")
        except Exception:
            pass

    if hasattr(db, "get_all_foreshadowing"):
        foreshadowing = [
            thread
            for thread in db.get_all_foreshadowing(novel_id)
            if thread.get("status", "active") in ("active", "overdue")
        ]
    else:
        foreshadowing = db.get_active_foreshadowing(novel_id)
    overdue = []
    for thread in foreshadowing:
        due_by = _chapter_number(thread.get("due_by_chapter"))
        if thread.get("status") == "overdue" or (due_by is not None and due_by <= next_chapter):
            overdue.append(thread)
    if overdue:
        constraints.append(f"⚠️ {len(overdue)} 个伏笔需在本章回收：")
        for thread in overdue[:3]:
            constraints.append(f"  - 必须回收 #{thread.get('id','?')}「{thread.get('description','')[:60]}」")
    elif foreshadowing:
        constraints.append(f"📌 {len(foreshadowing)} 个活跃伏笔，本章可暗示但不需回收")

    costs = db.get_cost_ledger(novel_id)
    gains = len([entry for entry in costs if entry.get("gain")])
    losses = len([entry for entry in costs if entry.get("loss")])
    if gains > losses + 1:
        constraints.append(f"⚖️ 获得 {gains} 次，失去 {losses} 次——本章需要一次失去来平衡代价")
    elif losses > gains + 1:
        constraints.append(f"⚖️ 失去 {losses} 次，获得 {gains} 次——本章需要一次获得来避免过于沉重")

    unsaid = db.get_unsaid(novel_id)
    if unsaid:
        constraints.append(f"🧊 {len(unsaid)} 条隐藏真相——AI 必须知道但不能在正文写出")
        for entry in unsaid[-5:]:
            constraints.append(f"  - 🔒 {entry['entry'][:80]}")

    world = db.get_world_state(novel_id)
    broken = [rule for rule in world if rule.get("is_broken")]
    if broken:
        for rule in broken[-3:]:
            constraints.append(f"🌍 规则「{rule.get('rule_name','?')}」曾被破坏——确保本章不重复破坏")

    timeline = db.get_timeline(novel_id)
    if len(timeline) > 3:
        relay = len([character for character in chars if character.get("emotion")]) / max(1, len(timeline))
        if relay < 0.2:
            constraints.append("📖 关系线长期停滞——本章应推进至少一个角色关系变化")

    return "\n".join(constraints) if constraints else "无特定约束，自由创作"
