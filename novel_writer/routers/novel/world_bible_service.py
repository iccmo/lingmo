"""Background service for world-bible generation."""

from __future__ import annotations

import json
import re
from pathlib import Path

from novel_writer.routers.deps import get_db, get_gen_state


def _set_status(novel_id: str, status: str, message: str = "", progress: int = 0, overall: float = 0) -> None:
    get_gen_state().set_status(novel_id, status, message, progress, overall)


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


def run_world_bible(novel_id: str) -> None:
    """Background: generate complete world bible from synopsis."""
    db = get_db()
    gen = _generator_for(novel_id)
    novel = db.get_novel(novel_id)
    try:
        _set_status(novel_id, "generating", "生成世界观设定...")
        bible = gen._call_llm_with_retry(
            [
                {"role": "system", "content": "你是世界观设计师。基于小说简介生成完整的设定集。"},
                {
                    "role": "user",
                    "content": f"""基于以下简介，生成完整世界观设定（JSON格式）：

简介：{novel.get('synopsis', '')}
体裁：{novel.get('genre', '玄幻')}

输出JSON：
{{
  "world_name": "世界名称",
  "era": "时代背景",
  "power_system": "核心力量体系（100字内）",
  "geography": "地理格局（100字内）",
  "factions": [{{"name":"势力名","description":"简介","leader":"首领"}}],
  "key_locations": [{{"name":"地名","description":"描述"}}],
  "historical_events": [{{"event":"事件名","year":"时间","impact":"影响"}}],
  "cultural_notes": "文化/社会特色（200字内）"
}}

只输出JSON。""",
                },
            ],
            max_tokens=2048,
        )

        json_match = re.search(r"\{[\s\S]*\}", bible)
        if json_match:
            data = json.loads(json_match.group(0))
            updates = {}
            for key in ["world_name", "era", "power_system"]:
                if key in data:
                    updates[key] = data[key]
            if "geography" in data:
                updates["world_geo"] = data.get("geography", "")
            if updates:
                db.update_novel(novel_id, **updates)
            for faction in data.get("factions", [])[:5]:
                with db.conn() as conn:
                    conn.execute(
                        "INSERT OR IGNORE INTO factions (novel_id,name,description,leader) VALUES (?,?,?,?)",
                        (
                            novel_id,
                            faction.get("name", ""),
                            faction.get("description", "")[:200],
                            faction.get("leader", ""),
                        ),
                    )
            bible_dir = Path("data") / "bibles"
            bible_dir.mkdir(exist_ok=True)
            (bible_dir / f"{novel_id}.json").write_text(
                json.dumps(data, ensure_ascii=False, indent=2)
            )
            db.log(novel_id, "world.bible_generated", {"factions": len(data.get("factions", []))})
        _set_status(novel_id, "complete", "世界设定集已生成")
    except Exception as exc:
        _set_status(novel_id, "error", str(exc)[:200])
