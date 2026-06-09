"""Service helpers for agent-pipeline chapter planning."""

from __future__ import annotations

from novel_writer.routers.deps import get_db
from novel_writer.routers.novel.generation_support_service import build_creation_brief


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


def editor_in_chief_brief(novel_id: str, chapter_num: int) -> str:
    """Read story bible and write a concise chapter brief."""
    try:
        db = get_db()
        gen = _generator_for(novel_id)

        chars = db.get_character_state(novel_id)
        foreshadowing = db.get_active_foreshadowing(novel_id)
        unsaid = db.get_unsaid(novel_id)
        costs = db.get_cost_ledger(novel_id)
        creation_brief = build_creation_brief(db, novel_id)

        char_lines = (
            "\n".join(
                f"- {char['char_name']}: 情绪={char.get('emotion','?')}, 身体={char.get('physical_state','?')}, 目标={char.get('goal','?')}"
                for char in chars[-5:]
            )
            if chars
            else "首章"
        )
        foreshadowing_lines = (
            "\n".join(
                f"- #{item['id']}: {item['description'][:60]} (到期Ch{item.get('due_by_chapter','?')})"
                for item in foreshadowing[:5]
            )
            if foreshadowing
            else "无活跃伏笔"
        )
        unsaid_lines = "\n".join(f"- 🔒 {entry['entry'][:80]}" for entry in unsaid[-5:]) if unsaid else "无"
        cost_lines = (
            "\n".join(
                f"- {entry.get('character_name','?')}: +{entry.get('gain','')} / -{entry.get('loss','')}"
                for entry in costs[-3:]
            )
            if costs
            else "无"
        )

        prompt = f"""你是小说总编。根据以下信息，为第{chapter_num}章写一份简报（不超过300字）。
不要写正文。只写要求。

【创作硬约束】
{creation_brief or "无额外创作硬约束"}

【当前角色状态】
{char_lines}

【活跃伏笔】
{foreshadowing_lines}

【隐藏真相（不能说）】
{unsaid_lines}

【近期代价】
{cost_lines}

【简报要求】
1. 本章需要推进什么情节？（1-2句）
2. 本章必须出现的角色和他们的情感状态
3. 本章必须回收的伏笔（如果有）
4. 本章的主题约束（代价必须被支付）
5. 本章的节奏（快/慢/中）

直接输出简报，不要编号。像在跟作者说话一样写。
"""
        return gen._call_llm_with_retry([{"role": "user", "content": prompt}], max_tokens=512) or ""
    except Exception as exc:
        print(f"[AGENT-EIC] Failed: {exc}")
        return ""


def architect_outline(novel_id: str, chapter_num: int, brief: str) -> str:
    """Turn an editor-in-chief brief into a chapter outline."""
    if not brief:
        return ""

    try:
        db = get_db()
        gen = _generator_for(novel_id)
        creation_brief = build_creation_brief(db, novel_id)
        prompt = f"""你是小说结构师。根据总编的简报，为第{chapter_num}章设计大纲。

【创作硬约束】
{creation_brief or "无额外创作硬约束"}

【总编简报】
{brief}

【输出格式】
开场（1-2句，地点+人物+初始状态）
发展（2-3个情节点）
转折（1个关键的转折或揭示）
结尾（钩子，1-2句）

每个情节点包含：类型（开场/冲突/发现/转折/结尾）、涉及角色、地点、要传达的情感。
直接输出大纲，不要编号。简洁即可。
"""
        return gen._call_llm_with_retry([{"role": "user", "content": prompt}], max_tokens=512) or ""
    except Exception as exc:
        print(f"[AGENT-ARCH] Failed: {exc}")
        return ""
