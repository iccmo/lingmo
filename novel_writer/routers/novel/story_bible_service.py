"""Story bible extraction and consistency checks for generated chapters."""

from __future__ import annotations

import json
import re

from novel_writer.routers.deps import get_db


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


def _generator_for(novel_id: str):
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
    return Generator(cfg)


def _parse_story_bible_json(raw: str) -> dict:
    """Parse LLM story-bible JSON from fenced or free-form output."""
    if not raw:
        return {}
    from novel_writer.generator import Generator

    for candidate in Generator._json_object_candidates(raw):
        cleaned = re.sub(r",\s*}", "}", candidate)
        cleaned = re.sub(r",\s*]", "]", cleaned)
        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return {}


def _text(value, limit: int = 120) -> str:
    if value is None:
        return ""
    return str(value).strip()[:limit]


def _json_list(value, limit: int = 8) -> str:
    if value is None:
        items = []
    elif isinstance(value, list):
        items = value
    else:
        items = [value]

    cleaned = []
    seen = set()
    for item in items:
        if isinstance(item, dict):
            text = {str(k): _text(v, 80) for k, v in item.items() if _text(v, 80)}
            marker = json.dumps(text, ensure_ascii=False, sort_keys=True)
        else:
            text = _text(item, 80)
            marker = text
        if not text or marker in seen:
            continue
        seen.add(marker)
        cleaned.append(text)
        if len(cleaned) >= limit:
            break
    return json.dumps(cleaned, ensure_ascii=False)


def _chapter_number(value) -> int | None:
    if value in (None, ""):
        return None
    text = str(value).strip()
    match = re.search(r"\d+", text)
    if match:
        return int(match.group())

    numerals = {"零": 0, "〇": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
    text = re.sub(r"[第章节回内左右前后\s]", "", text)
    if not text:
        return None
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


def _is_injured(value: str) -> bool:
    text = str(value or "")
    return any(marker in text for marker in ("伤", "残", "中毒", "昏迷", "濒死", "虚弱", "重创"))


def _is_healthy(value: str) -> bool:
    text = str(value or "")
    return any(marker in text for marker in ("健康", "痊愈", "恢复", "无伤", "完好"))


_COST_LOSS_MARKERS = (
    "受伤", "流血", "重伤", "伤口", "中毒", "濒死", "虚弱", "昏迷",
    "暴露身份", "身份暴露", "暴露", "泄露",
    "欠债", "债务", "欠下", "人情债",
    "关系裂痕", "决裂", "失去信任", "反目",
    "后患", "麻烦", "追杀", "通缉", "代价",
)


def _infer_loss_from_content(content: str, limit: int = 100) -> str:
    """Extract explicit consequence text when the LLM leaves the cost ledger loss blank."""
    text = str(content or "").strip()
    if not text:
        return ""
    snippets: list[str] = []
    for sentence in re.split(r"[。！？!?；;\n]+", text):
        sentence = sentence.strip(" \t\r，,")
        if not sentence:
            continue
        if any(marker in sentence for marker in _COST_LOSS_MARKERS):
            snippets.append(sentence[:60])
        if len(snippets) >= 2:
            break
    return _text("；".join(snippets), limit)


def _loss_type_for(loss: str) -> str:
    if any(marker in loss for marker in ("伤", "血", "中毒", "濒死", "虚弱", "昏迷")):
        return "health"
    if any(marker in loss for marker in ("信任", "裂痕", "决裂", "反目")):
        return "trust"
    if any(marker in loss for marker in ("暴露", "泄露", "通缉", "追杀")):
        return "position"
    if any(marker in loss for marker in ("债", "人情债", "自由")):
        return "freedom"
    return "consequence"


def _latest_prior_state(db, novel_id: str, char_name: str, chapter_num: int) -> dict | None:
    if hasattr(db, "get_all_character_states"):
        states = db.get_all_character_states(novel_id, char_name=char_name, up_to_chapter=chapter_num - 1)
        return states[-1] if states else None
    prev_states = db.get_character_state(novel_id, chapter_num - 1) if chapter_num > 1 else []
    return next((state for state in prev_states if state.get("char_name") == char_name), None)


def extract_story_bible(novel_id: str, chapter_num: int, content: str, chapter_title: str) -> None:
    """Auto-extract structured story data from generated chapter using LLM."""
    try:
        db = get_db()
        gen = _generator_for(novel_id)
        if hasattr(db, "clear_story_bible_chapter"):
            db.clear_story_bible_chapter(novel_id, chapter_num)

        prompt = f"""从以下小说章节中提取结构化信息。输出严格JSON格式，不要加任何解释。

{{
  "characters": [
    {{"name": "角色名", "emotion": "当前情绪", "physical_state": "身体状态",
      "knowledge": ["新获得的信息1"],
      "goal": "当前目标", "location": "当前位置",
      "relationships": [{{"target": "关联角色名", "change": "态度变化描述"}}]
    }}
  ],
  "foreshadowing": [
    {{"description": "新埋的伏笔描述", "hint_text": "原文暗示片段(20字以内)", "due_by_chapter": "预计回收章节(数字)"}}
  ],
  "locations": [
    {{"name": "地点名", "event": "发生的事件(10字)", "state_change": "状态变化"}}
  ],
  "timeline": {{"absolute_time": "故事内时间", "relative_time": "距上一章的时间", "event_summary": "本章事件一句话摘要"}},
  "world_rules": [
    {{"rule": "规则名", "description": "规则描述", "is_broken": false}}
  ],
  "costs": [
    {{"character": "角色名", "gain": "获得什么", "loss": "失去什么", "gain_type": "info/power/relationship/position", "loss_type": "freedom/innocence/trust/health", "is_immediate": true}}
  ]
}}

章节标题：{chapter_title}
章节正文（前3000字）：
{content[:3000]}
"""
        result = gen._call_llm_with_retry([{"role": "user", "content": prompt}], max_tokens=2048)
        if not result:
            return

        data = _parse_story_bible_json(result)
        if not data:
            return

        seen_characters = set()
        for char in data.get("characters", []):
            name = _text(char.get("name") if isinstance(char, dict) else "", 40)
            if name and name not in seen_characters:
                seen_characters.add(name)
                db.save_character_state(
                    novel_id,
                    chapter_num,
                    name,
                    emotion=_text(char.get("emotion"), 60),
                    physical_state=_text(char.get("physical_state"), 60),
                    knowledge=_json_list(char.get("knowledge")),
                    goal=_text(char.get("goal"), 100),
                    location=_text(char.get("location"), 60),
                    relationships=_json_list(char.get("relationships")),
                )

        seen_foreshadowing = set()
        for fs in data.get("foreshadowing", []):
            description = _text(fs.get("description") if isinstance(fs, dict) else "", 160)
            if description and description not in seen_foreshadowing:
                seen_foreshadowing.add(description)
                db.save_foreshadowing(
                    novel_id,
                    chapter_num,
                    description,
                    hint_text=_text(fs.get("hint_text"), 80),
                    due_by=_chapter_number(fs.get("due_by_chapter")),
                )

        seen_locations = set()
        for loc in data.get("locations", []):
            name = _text(loc.get("name") if isinstance(loc, dict) else "", 60)
            if name and name not in seen_locations:
                seen_locations.add(name)
                db.save_location_history(
                    novel_id,
                    chapter_num,
                    name,
                    event=_text(loc.get("event"), 80),
                    state_change=_text(loc.get("state_change"), 100),
                )

        timeline = data.get("timeline", {})
        if isinstance(timeline, dict) and any(timeline.values()):
            db.save_timeline_event(
                novel_id,
                chapter_num,
                absolute_time=_text(timeline.get("absolute_time"), 80),
                relative_time=_text(timeline.get("relative_time"), 80),
                event_summary=_text(timeline.get("event_summary"), 160),
            )

        seen_rules = set()
        for rule in data.get("world_rules", []):
            rule_name = _text(rule.get("rule") if isinstance(rule, dict) else "", 80)
            if rule_name and rule_name not in seen_rules:
                seen_rules.add(rule_name)
                db.save_world_state(
                    novel_id,
                    chapter_num,
                    rule_name,
                    rule_description=_text(rule.get("description"), 160),
                    is_broken=bool(rule.get("is_broken", False)),
                )

        inferred_loss = _infer_loss_from_content(content)
        saved_cost = False
        for cost in data.get("costs", []):
            character = _text(cost.get("character") if isinstance(cost, dict) else "", 40)
            gain = _text(cost.get("gain") if isinstance(cost, dict) else "", 100)
            loss = _text(cost.get("loss") if isinstance(cost, dict) else "", 100) or inferred_loss
            if character and (gain or loss):
                saved_cost = True
                db.save_cost_entry(
                    novel_id,
                    chapter_num,
                    character_name=character,
                    gain=gain,
                    loss=loss,
                    gain_type=_text(cost.get("gain_type"), 40) or "info",
                    loss_type=_text(cost.get("loss_type"), 40) or (_loss_type_for(loss) if loss else "none"),
                    is_immediate=bool(cost.get("is_immediate", True)),
                )
        if inferred_loss and not saved_cost:
            character = next(
                (
                    _text(char.get("name"), 40)
                    for char in data.get("characters", [])
                    if isinstance(char, dict) and _text(char.get("name"), 40)
                ),
                "主角",
            )
            db.save_cost_entry(
                novel_id,
                chapter_num,
                character_name=character,
                gain="",
                loss=inferred_loss,
                gain_type="none",
                loss_type=_loss_type_for(inferred_loss),
                is_immediate=True,
            )
    except Exception as exc:
        print(f"[BIBLE] Extraction failed: {exc}")


def run_consistency_check(novel_id: str, chapter_num: int) -> None:
    """Run consistency checks against the story bible."""
    try:
        db = get_db()

        chars = db.get_character_state(novel_id, chapter_num)

        for char in chars:
            name = char["char_name"]
            prev = _latest_prior_state(db, novel_id, name, chapter_num)
            if not prev:
                continue
            if _is_injured(prev.get("physical_state", "")) and _is_healthy(char.get("physical_state", "")):
                db.log_consistency_issue(
                    novel_id,
                    chapter_num,
                    "character",
                    "error",
                    f"{name} 第{prev.get('chapter_num')}章状态为「{prev.get('physical_state')}」，本章突然变为「{char.get('physical_state')}」——需要说明恢复过程",
                    f"添加一句话说明{name}如何恢复或接受了治疗",
                )
            elif _is_healthy(prev.get("physical_state", "")) and _is_injured(char.get("physical_state", "")):
                db.log_consistency_issue(
                    novel_id,
                    chapter_num,
                    "character",
                    "info",
                    f"{name} 本章受伤（从健康→受伤），需要明确受伤原因",
                    "",
                )
            prev_know = prev.get("knowledge", "[]")
            curr_know = char.get("knowledge", "[]")
            if prev_know != curr_know and prev_know != "[]":
                db.log_consistency_issue(
                    novel_id,
                    chapter_num,
                    "character",
                    "info",
                    f"{name} 的知识状态发生了变化",
                    "",
                )
            prev_location = str(prev.get("location") or "").strip()
            curr_location = str(char.get("location") or "").strip()
            if prev_location and curr_location and prev_location != curr_location:
                db.log_consistency_issue(
                    novel_id,
                    chapter_num,
                    "timeline",
                    "info",
                    f"{name} 从第{prev.get('chapter_num')}章的「{prev_location}」移动到本章「{curr_location}」",
                    "确认正文中有旅行、传送、转场或抵达描写",
                )

        active_foreshadowing = db.get_active_foreshadowing(novel_id)
        for thread in active_foreshadowing:
            due = thread.get("due_by_chapter")
            if due and int(due) < chapter_num:
                db.log_consistency_issue(
                    novel_id,
                    chapter_num,
                    "foreshadowing",
                    "warning",
                    f"伏笔 #{thread['id']}：「{thread['description'][:50]}」预期在第 {due} 章回收，当前第 {chapter_num} 章——已过期",
                    f"建议在第 {chapter_num + 1} 章回收此伏笔，或标记为放弃",
                )
                with db.conn() as conn:
                    conn.execute(
                        "UPDATE foreshadowing_tracker SET status='overdue' WHERE id=? AND status='active'",
                        (thread["id"],),
                    )

        world_rules = db.get_world_state(novel_id)
        broken_rules = [rule for rule in world_rules if rule.get("is_broken")]
        for rule in broken_rules[-3:]:
            db.log_consistency_issue(
                novel_id,
                chapter_num,
                "world",
                "warning",
                f"世界观规则「{rule['rule_name']}」被破坏",
                "确认这是剧情需要还是bug。如需恢复，在后续章节说明规则修正",
            )

    except Exception as exc:
        print(f"[CONSISTENCY] Check failed: {exc}")
