"""Story-world editing endpoints: world, characters, factions, and outline."""

from __future__ import annotations

import json
import re

from fastapi import APIRouter, HTTPException

from novel_writer.routers.deps import get_db
from novel_writer.routers.novel.request_validation import text_field

router = APIRouter(tags=["story-world"])


def _db():
    return get_db()


def _get_provider(novel_id: str | None = None):
    db = _db()
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


@router.get("/api/novels/{novel_id}/unsaid")
def get_unsaid(novel_id: str) -> dict:
    db = _db()
    if not db.get_novel(novel_id):
        raise HTTPException(404)
    return {"entries": db.get_unsaid(novel_id)}


@router.post("/api/novels/{novel_id}/unsaid")
def add_unsaid(novel_id: str, data: dict) -> dict:
    entry = text_field(data, "entry")
    if not entry or len(entry) < 2:
        raise HTTPException(400, "Entry too short")
    _db().save_unsaid(novel_id, entry)
    return {"ok": True}


@router.delete("/api/novels/{novel_id}/unsaid/{entry_id}")
def remove_unsaid(novel_id: str, entry_id: int) -> dict:
    _db().delete_unsaid(entry_id)
    return {"ok": True}


@router.get("/api/novels/{novel_id}/story-bible")
def get_story_bible(novel_id: str) -> dict:
    """Get complete story bible for a novel."""
    db = _db()
    if not db.get_novel(novel_id):
        raise HTTPException(404, "Novel not found")
    return {
        "characters": db.get_character_state(novel_id),
        "foreshadowing": db.get_active_foreshadowing(novel_id),
        "locations": db.get_location_history(novel_id),
        "timeline": db.get_timeline(novel_id),
        "world_rules": db.get_world_state(novel_id),
        "consistency_log": db.get_consistency_log(novel_id)[:20],
        "cost_ledger": db.get_cost_ledger(novel_id),
    }


@router.post("/api/novels/{novel_id}/seed-bible")
def seed_bible_from_existing(novel_id: str) -> dict:
    """Populate story_bible from existing chapters and character definitions. No LLM needed."""
    db = _db()
    novel = db.get_novel(novel_id)
    if not novel:
        raise HTTPException(404)

    generated_chapters = [chapter for chapter in (novel.get("chapters") or []) if chapter.get("word_count", 0) > 0]
    if not generated_chapters:
        return {"status": "no_content"}

    static_chars = novel.get("characters", [])
    seeded = {"chars": 0, "tl": 0, "loc": 0}
    for chapter in generated_chapters:
        chapter_num = chapter["number"]
        for static_char in static_chars:
            if not static_char.get("name"):
                continue
            exists = [
                char
                for char in db.get_character_state(novel_id, chapter_num)
                if char["char_name"] == static_char["name"]
            ]
            if not exists:
                try:
                    db.save_character_state(
                        novel_id,
                        chapter_num,
                        static_char["name"],
                        emotion="未知",
                        physical_state=static_char.get("status", "健康"),
                        goal="未知",
                        location="未知",
                    )
                    seeded["chars"] += 1
                except Exception:
                    pass
        db.save_timeline_event(
            novel_id,
            chapter_num,
            absolute_time=f"第{chapter_num}章",
            relative_time="未知",
            event_summary=(chapter.get("summary") or chapter.get("title", ""))[:100],
        )
        seeded["tl"] += 1
    return {"status": "seeded", "seeded": seeded, "chapters": len(generated_chapters)}


@router.post("/api/seed-all-bibles")
def seed_all_bibles() -> dict:
    """Seed story bible for all novels with generated chapters."""
    db = _db()
    results = {}
    for novel in db.list_novels():
        if novel.get("total_chapters", 0) > 0:
            try:
                result = seed_bible_from_existing(novel["id"])
                results[novel["id"]] = result.get("seeded", {})
            except Exception as exc:
                results[novel["id"]] = {"error": str(exc)[:100]}
    return {"seeded": len(results), "results": results}


@router.get("/api/novels/{novel_id}/cost-ledger")
def get_cost_ledger(novel_id: str) -> dict:
    db = _db()
    if not db.get_novel(novel_id):
        raise HTTPException(404)

    entries = db.get_cost_ledger(novel_id)
    total_gains = len([entry for entry in entries if entry.get("gain")])
    total_losses = len([entry for entry in entries if entry.get("loss")])
    balance = total_gains - total_losses
    return {
        "entries": entries,
        "summary": {
            "total_gains": total_gains,
            "total_losses": total_losses,
            "balance": balance,
            "status": "balanced" if abs(balance) <= 2 else ("surplus" if balance > 0 else "deficit"),
        },
    }


@router.post("/api/novels/{novel_id}/consistency/{issue_id}/fix")
def mark_consistency_fixed(novel_id: str, issue_id: int) -> dict:
    _db().mark_consistency_fixed(issue_id)
    return {"ok": True}


@router.get("/api/novels/{novel_id}/counterpoint")
def get_counterpoint(novel_id: str) -> dict:
    """Track multiple storylines and their relative speed."""
    db = _db()
    if not db.get_novel(novel_id):
        raise HTTPException(404)

    chars = db.get_character_state(novel_id)
    foreshadowing = db.get_active_foreshadowing(novel_id)
    timeline = db.get_timeline(novel_id)
    costs = db.get_cost_ledger(novel_id)

    total_chapters = len(timeline)
    plot_progress = min(100, total_chapters * 5) if total_chapters else 0
    relationship_chapters = {char["chapter_num"] for char in chars if char.get("emotion")}
    relationship_speed = len(relationship_chapters) / max(1, total_chapters) if total_chapters else 0
    theme_speed = len(costs) / max(1, total_chapters) if total_chapters else 0

    lines = [
        {
            "name": "情节线",
            "id": "plot",
            "speed": plot_progress,
            "status": "正常" if 20 < plot_progress < 80 else ("缓慢" if plot_progress <= 20 else "过速"),
        },
        {
            "name": "关系线",
            "id": "rel",
            "speed": round(relationship_speed * 100),
            "status": "正常" if 0.2 < relationship_speed < 0.8 else ("滞后" if relationship_speed <= 0.2 else "过密"),
        },
        {
            "name": "主题线",
            "id": "theme",
            "speed": round(theme_speed * 100),
            "status": "正常" if theme_speed > 0 else "未激活",
        },
        {
            "name": "秘密线",
            "id": "secret",
            "speed": len(foreshadowing),
            "status": "正常" if 1 <= len(foreshadowing) <= 5 else ("过载" if len(foreshadowing) > 5 else "枯竭"),
        },
    ]

    lagging = [line for line in lines if line["status"] in ("滞后", "缓慢", "未激活", "枯竭")]
    if lagging:
        suggestion = f"{lagging[0]['name']}滞后——建议下章推进此线"
    elif any(line["status"] == "过密" for line in lines):
        suggestion = "关系线过密——建议暂缓感情戏"
    else:
        suggestion = "各线均衡，可自由推进"

    return {"lines": lines, "lagging": [line["name"] for line in lagging], "suggestion": suggestion}


@router.post("/api/text/analyze")
def analyze_text(data: dict) -> dict:
    """Run lightweight text analysis server-side for a given text."""
    text = text_field(data, "text") or text_field(data, "content")
    if not text or len(text) < 10:
        raise HTTPException(400, "Text too short")

    chars = len(text.replace("\n", "").replace(" ", ""))
    contradictions = len(re.findall(r"但是|可是|然而|却|不过|只是", text))
    questions = len(re.findall(r"[？?]", text))
    suspensions = len(re.findall(r"…|\.\.\.", text))
    surprises = len(re.findall(r"[！!]", text))
    density = round((contradictions + questions + suspensions + surprises) / max(1, chars / 100), 1)

    reversals = len(re.findall(r"但是|可是|然而|却|不过|没想到|谁知|不料", text))
    sentences = [sentence for sentence in re.split(r"[。！？.!?\n]+", text) if sentence.strip()]
    torque = round(min(1, reversals / max(1, len(sentences) * 0.1)), 2)

    visual = len(re.findall(r"看|见|望|盯|瞪|光|亮|暗|黑|白|红|蓝|绿|色", text))
    tactile = len(re.findall(r"碰|触|摸|握|抓|按|压|冷|热|凉|暖|烫|疼|痛", text))
    auditory = len(re.findall(r"听|闻|声|响|音|说|道|问|答|喊|叫|吼|静|默", text))

    first_sentences = sentences[:3]
    opening_text = "。".join(first_sentences)
    has_body = any(re.findall(r"碰|触|摸|握|冷|热|疼|痛|看|见|听|闻", opening_text))
    has_expect = any(re.findall(r"[？?…]|但是|可是|然而|不过", opening_text))
    opening_strength = (1 if has_body else 0) + (1 if has_expect else 0)

    return {
        "chars": chars,
        "sentences": len(sentences),
        "density": density,
        "forces": {"torque": torque},
        "body_sense": {"visual": visual, "tactile": tactile, "auditory": auditory, "total": visual + tactile + auditory},
        "opening": {
            "strength": opening_strength,
            "assessment": "强" if opening_strength >= 2 else "可" if opening_strength >= 1 else "弱",
        },
        "style_fingerprint": {
            "sentence_length": round(chars / max(1, len(sentences))),
            "dialogue_ratio": round(len(re.findall(r"「|」|\"", text)) / max(1, chars) * 100, 1),
            "description_ratio": round(len(re.findall(r"看|见|望|光|色|影", text)) / max(1, chars) * 100, 1),
        },
    }


@router.put("/api/novels/{novel_id}/world")
def update_world(novel_id: str, data: dict) -> dict:
    """Update world settings."""
    db = _db()
    if not db.get_novel(novel_id):
        raise HTTPException(404)
    updates = {}
    for key in ["world_name", "world_era", "world_geo", "power_system", "main_arc", "current_arc"]:
        if key in data:
            updates[key] = data[key]
    if "world_rules" in data:
        value = data["world_rules"]
        updates["world_rules"] = json.dumps(value) if isinstance(value, list) else str(value)
    if updates:
        db.update_novel(novel_id, **updates)
    return {"ok": True}


@router.put("/api/novels/{novel_id}/characters/{char_key}")
def update_character(novel_id: str, char_key: str, data: dict) -> dict:
    """Update a character."""
    with _db().conn() as conn:
        row = conn.execute(
            "SELECT id FROM characters WHERE novel_id=? AND char_key=?",
            (novel_id, char_key),
        ).fetchone()
        if not row:
            raise HTTPException(404, "Character not found")
        fields = {
            key: data[key]
            for key in ["name", "role", "personality", "background", "power_level", "status"]
            if key in data
        }
        if fields:
            sets = ", ".join(f"{key}=?" for key in fields)
            conn.execute(
                f"UPDATE characters SET {sets}, updated_at=datetime('now') WHERE id=?",
                list(fields.values()) + [row["id"]],
            )
    return {"ok": True}


@router.post("/api/novels/{novel_id}/characters")
def add_character(novel_id: str, data: dict) -> dict:
    """Add a new character."""
    db = _db()
    if not db.get_novel(novel_id):
        raise HTTPException(404)
    char_key = text_field(data, "char_key")
    if not char_key:
        raise HTTPException(400, "char_key required")
    with db.conn() as conn:
        conn.execute(
            """INSERT INTO characters (novel_id,char_key,name,role,personality,background,power_level)
            VALUES (?,?,?,?,?,?,?)""",
            (
                novel_id,
                char_key,
                data.get("name", char_key),
                data.get("role", "配角"),
                data.get("personality", ""),
                data.get("background", ""),
                data.get("power_level", ""),
            ),
        )
    return {"ok": True}


@router.delete("/api/novels/{novel_id}/characters/{char_key}")
def delete_character(novel_id: str, char_key: str) -> dict:
    db = _db()
    if not db.get_novel(novel_id):
        raise HTTPException(404, "Novel not found")
    with db.conn() as conn:
        conn.execute("DELETE FROM characters WHERE novel_id=? AND char_key=?", (novel_id, char_key))
    return {"ok": True}


@router.post("/api/novels/{novel_id}/factions")
def add_faction(novel_id: str, data: dict) -> dict:
    db = _db()
    if not db.get_novel(novel_id):
        raise HTTPException(404)
    name = text_field(data, "name")
    if not name:
        raise HTTPException(400, "name required")
    with db.conn() as conn:
        conn.execute(
            "INSERT INTO factions (novel_id,name,description,leader,sort_order) VALUES (?,?,?,?,?)",
            (novel_id, name, data.get("description", ""), data.get("leader", ""), data.get("sort_order", 0)),
        )
    return {"ok": True}


@router.put("/api/novels/{novel_id}/factions/{faction_id}")
def update_faction(novel_id: str, faction_id: int, data: dict) -> dict:
    with _db().conn() as conn:
        row = conn.execute("SELECT id FROM factions WHERE id=? AND novel_id=?", (faction_id, novel_id)).fetchone()
        if not row:
            raise HTTPException(404)
        fields = {key: data[key] for key in ["name", "description", "leader", "sort_order"] if key in data}
        if fields:
            sets = ", ".join(f"{key}=?" for key in fields)
            conn.execute(f"UPDATE factions SET {sets} WHERE id=?", list(fields.values()) + [faction_id])
    return {"ok": True}


@router.delete("/api/novels/{novel_id}/factions/{faction_id}")
def delete_faction(novel_id: str, faction_id: int) -> dict:
    with _db().conn() as conn:
        conn.execute("DELETE FROM factions WHERE id=? AND novel_id=?", (faction_id, novel_id))
    return {"ok": True}


@router.get("/api/novels/{novel_id}/outline")
def get_outline(novel_id: str) -> dict:
    """Get planned chapters with recent generated chapter context."""
    db = _db()
    if not db.get_novel(novel_id):
        raise HTTPException(404)
    with db.conn() as conn:
        outline_rows = conn.execute(
            """SELECT number, title, summary FROM chapters
            WHERE novel_id=? AND word_count=0 ORDER BY number""",
            (novel_id,),
        ).fetchall()
        generated_rows = conn.execute(
            """SELECT number, title, summary FROM chapters
            WHERE novel_id=? AND word_count>0 ORDER BY number DESC LIMIT 5""",
            (novel_id,),
        ).fetchall()
    return {
        "outline": [{"number": row["number"], "title": row["title"], "summary": row["summary"]} for row in outline_rows],
        "recent_chapters": [
            {"number": row["number"], "title": row["title"], "summary": row["summary"]} for row in generated_rows
        ],
        "next_number": (
            db.get_next_chapter_number(novel_id)
            if hasattr(db, "get_next_chapter_number")
            else (generated_rows[0]["number"] + 1 if generated_rows else 1)
        ),
    }


@router.post("/api/novels/{novel_id}/outline")
def save_outline(novel_id: str, data: dict) -> dict:
    """Save planned chapter outline items without overwriting generated chapters."""
    db = _db()
    if not db.get_novel(novel_id):
        raise HTTPException(404)
    items = data.get("items", [])
    with db.conn() as conn:
        for item in items:
            number = item.get("number", 0)
            if number <= 0:
                continue
            existing = conn.execute(
                "SELECT word_count FROM chapters WHERE novel_id=? AND number=?",
                (novel_id, number),
            ).fetchone()
            if existing and existing["word_count"] > 0:
                continue
            conn.execute(
                """INSERT OR REPLACE INTO chapters (novel_id,number,title,summary,word_count)
                VALUES (?,?,?,?,0)""",
                (novel_id, number, item.get("title", ""), item.get("summary", "")),
            )
    return {"ok": True}


@router.delete("/api/novels/{novel_id}/outline/{chapter_num}")
def delete_outline_item(novel_id: str, chapter_num: int) -> dict:
    """Delete an outline item only when it has no generated content."""
    with _db().conn() as conn:
        existing = conn.execute(
            "SELECT word_count FROM chapters WHERE novel_id=? AND number=?",
            (novel_id, chapter_num),
        ).fetchone()
        if not existing:
            raise HTTPException(404)
        if existing["word_count"] > 0:
            raise HTTPException(400, "Cannot delete outline for a generated chapter")
        conn.execute(
            "DELETE FROM chapters WHERE novel_id=? AND number=? AND word_count=0",
            (novel_id, chapter_num),
        )
    return {"ok": True}


@router.post("/api/novels/{novel_id}/suggest-outline")
def suggest_outline(novel_id: str) -> dict:
    """Suggest three next-chapter directions from current novel context."""
    db = _db()
    novel = db.get_novel(novel_id)
    if not novel:
        raise HTTPException(404, "Novel not found")

    chapters = novel.get("chapters", [])
    generated = [chapter for chapter in chapters if chapter.get("word_count", 0) > 0]
    recent_titles = [chapter.get("title", "") for chapter in generated[-5:]]
    recent_hooks = [chapter.get("ending_hook", "") for chapter in generated[-3:] if chapter.get("ending_hook")]
    synopsis = novel.get("synopsis", "")
    genre = novel.get("genre", "玄幻")
    next_chapter = db.get_next_chapter_number(novel_id) if hasattr(db, "get_next_chapter_number") else (
        max([chapter.get("number", 0) for chapter in generated], default=0) + 1
    )

    prompt = f"""你是资深网文编辑。基于以下小说信息，建议第{next_chapter}章的3个不同走向。

小说类型：{genre}
简介：{synopsis}
最近章节：{' -> '.join(recent_titles) if recent_titles else '无'}
{'上章钩子：' + '；'.join(recent_hooks) if recent_hooks else ''}

请给出3个不同的下一章方向。每个方向20-40字，格式严格如下（每行一个方向，共3行）：
标题：xxx | 钩子：xxx | 摘要：xxx | 基调：xxx
"""

    try:
        from novel_writer.config import Config
        from novel_writer.generator import Generator

        provider = _get_provider(novel_id)
        cfg = Config(
            openai_api_key=provider.get("api_key", ""),
            openai_base_url=provider.get("base_url", ""),
            model=provider.get("models", "deepseek-v4-pro")[0] if provider.get("models") else "gpt-4o",
        )
        generator = Generator(cfg)
        raw = generator._call_llm_with_retry([{"role": "user", "content": prompt}], max_tokens=256)
    except Exception as exc:
        raise HTTPException(500, f"LLM call failed: {exc}")

    suggestions = []
    for line in raw.strip().split("\n"):
        parts = {}
        for segment in line.strip().split("|"):
            segment = segment.strip()
            if "：" in segment:
                key, value = segment.split("：", 1)
                parts[key] = value
        if "标题" in parts:
            suggestions.append(
                {
                    "title": parts.get("标题", "").strip(),
                    "hook": parts.get("钩子", "").strip(),
                    "summary": parts.get("摘要", "").strip(),
                    "tone": parts.get("基调", "").strip(),
                }
            )
        if len(suggestions) >= 3:
            break

    if not suggestions:
        suggestions = [{"title": f"第{next_chapter}章", "hook": raw[:80], "summary": raw[:150], "tone": genre}]

    return {"next_chapter": next_chapter, "suggestions": suggestions[:3]}
