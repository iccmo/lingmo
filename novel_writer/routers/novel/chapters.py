"""Chapter CRUD, formatting, ordering, and version endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from novel_writer.routers.deps import get_db
from novel_writer.routers.novel.chapter_metadata import (
    chapter_content_rejection,
    safe_json_list,
    update_chapter_content,
)

router = APIRouter(tags=["chapters"])


def _db():
    return get_db()


CHAPTER_SCOPED_COLUMNS: tuple[tuple[str, str], ...] = (
    ("chapters", "number"),
    ("chapter_summaries", "chapter_num"),
    ("chapter_traces", "chapter_num"),
    ("cost_logs", "chapter_number"),
    ("character_state", "chapter_num"),
    ("foreshadowing_tracker", "created_chapter"),
    ("foreshadowing_tracker", "due_by_chapter"),
    ("foreshadowing_tracker", "resolved_chapter"),
    ("location_history", "chapter_num"),
    ("story_timeline", "chapter_num"),
    ("world_state", "chapter_num"),
    ("consistency_log", "chapter_num"),
    ("voice_profile", "chapter_num"),
    ("cost_ledger", "chapter_num"),
    ("audio_bookmarks", "chapter_num"),
    ("audio_playlist", "chapter_num"),
    ("audio_progress", "chapter_num"),
    ("storyboards", "chapter_num"),
)


def _column_exists(conn, table: str, column: str) -> bool:
    try:
        return any(row["name"] == column for row in conn.execute(f"PRAGMA table_info({table})"))
    except Exception:
        return False


def _update_chapter_number_column(conn, novel_id: str, table: str, column: str, old_num: int, new_num: int) -> None:
    if not _column_exists(conn, table, column):
        return
    conn.execute(
        f"UPDATE {table} SET {column}=? WHERE novel_id=? AND {column}=?",
        (new_num, novel_id, old_num),
    )


def _parse_reorder_number(value, field: str) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise HTTPException(400, f"{field} must be an integer")
    if number < 1 or number > 2000:
        raise HTTPException(400, f"{field} must be between 1 and 2000")
    return number


def _validate_reorder_mapping(conn, novel_id: str, order) -> dict[int, int]:
    if not isinstance(order, dict):
        raise HTTPException(400, "order must be an object")

    mapping: dict[int, int] = {}
    for old_num, new_num in order.items():
        old_chapter = _parse_reorder_number(old_num, "old chapter number")
        new_chapter = _parse_reorder_number(new_num, "new chapter number")
        if old_chapter != new_chapter:
            mapping[old_chapter] = new_chapter

    if not mapping:
        return {}

    targets = list(mapping.values())
    if len(set(targets)) != len(targets):
        raise HTTPException(400, "target chapter numbers must be unique")

    existing_sources = {
        row["number"]
        for row in conn.execute(
            f"SELECT number FROM chapters WHERE novel_id=? AND number IN ({','.join('?' for _ in mapping)})",
            (novel_id, *mapping.keys()),
        )
    }
    missing_sources = sorted(set(mapping) - existing_sources)
    if missing_sources:
        raise HTTPException(400, f"source chapters do not exist: {', '.join(str(num) for num in missing_sources)}")

    existing_targets = {
        row["number"]
        for row in conn.execute(
            f"SELECT number FROM chapters WHERE novel_id=? AND number IN ({','.join('?' for _ in targets)})",
            (novel_id, *targets),
        )
    }
    conflicting_targets = sorted(existing_targets - set(mapping))
    if conflicting_targets:
        raise HTTPException(400, f"target chapters already exist: {', '.join(str(num) for num in conflicting_targets)}")

    return mapping


def _reorder_chapter_scoped_data(conn, novel_id: str, order: dict) -> None:
    mapping = order
    if not mapping:
        return

    temp_offset = -100000
    for old_num in mapping:
        temp_num = old_num + temp_offset
        for table, column in CHAPTER_SCOPED_COLUMNS:
            _update_chapter_number_column(conn, novel_id, table, column, old_num, temp_num)

    for old_num, new_num in mapping.items():
        temp_num = old_num + temp_offset
        for table, column in CHAPTER_SCOPED_COLUMNS:
            _update_chapter_number_column(conn, novel_id, table, column, temp_num, new_num)


@router.get("/api/novels/{novel_id}/chapters/{chapter_num}")
def get_chapter(novel_id: str, chapter_num: int) -> dict:
    chapter = _db().get_chapter(novel_id, chapter_num)
    if not chapter:
        raise HTTPException(404, "Not found")
    return {
        "number": chapter["number"],
        "content": chapter.get("content", ""),
        "title": chapter.get("title", ""),
        "ending_hook": chapter.get("ending_hook", ""),
        "key_events": safe_json_list(chapter.get("key_events")),
        "revelations": safe_json_list(chapter.get("revelations")),
        "narrative_facts": safe_json_list(chapter.get("narrative_facts")),
        "summary": chapter.get("summary", ""),
        "word_count": chapter.get("word_count", 0),
        "quality_score": chapter.get("quality_score", 0),
        "model_used": chapter.get("model_used", ""),
        "generated_at": chapter.get("generated_at", ""),
    }


@router.put("/api/novels/{novel_id}/chapters/{chapter_num}")
def save_chapter(novel_id: str, chapter_num: int, data: dict) -> dict:
    db = _db()
    if not db.get_novel(novel_id):
        raise HTTPException(404, "Not found")
    new_content = str(data.get("content", "") or "")
    old = None
    old = db.get_chapter(novel_id, chapter_num)
    rejection = chapter_content_rejection(old.get("content", "") if old else "", new_content)
    if rejection:
        raise HTTPException(400, rejection)
    try:
        if not old:
            db.add_chapter(
                novel_id,
                number=chapter_num,
                title=f"第{chapter_num}章",
                word_count=0,
                content="",
                summary="",
                ending_hook="",
            )
            old = db.get_chapter(novel_id, chapter_num)
        if old and old.get("content") and old["content"] != new_content:
            db.save_voice_sample(novel_id, chapter_num, old["content"][:500], new_content[:500])
    except Exception:
        pass
    updates = {"edit_ratio": data.get("edit_ratio", 0)}
    if old and old.get("content") != new_content:
        updates["quality_score"] = 0
    update_chapter_content(
        db,
        novel_id,
        chapter_num,
        new_content,
        refresh_story_bible=True,
        **updates,
    )
    return {"ok": True}


@router.post("/api/novels/{novel_id}/chapters/{chapter_num}/fix-formatting")
def fix_chapter_formatting(novel_id: str, chapter_num: int) -> dict:
    """Fix orphan quotes and normalize formatting on an existing chapter."""
    db = _db()
    if not db.get_novel(novel_id):
        raise HTTPException(404, "Novel not found")
    with db.conn() as conn:
        row = conn.execute(
            "SELECT content FROM chapters WHERE novel_id=? AND number=?",
            (novel_id, chapter_num),
        ).fetchone()
    if not row:
        raise HTTPException(404, "Chapter not found")
    content = row["content"]
    if not content:
        raise HTTPException(400, "Chapter has no content")
    from novel_writer.generator import Generator

    generator = Generator.__new__(Generator)
    cleaned, changes = generator.fix_formatting(content)
    rejection = chapter_content_rejection(content, cleaned)
    if rejection:
        raise HTTPException(400, f"formatting result rejected: {rejection}")
    update_chapter_content(db, novel_id, chapter_num, cleaned, refresh_story_bible=True)
    return {"ok": True, "changes": changes, "before": len(content), "after": len(cleaned)}


@router.post("/api/novels/{novel_id}/chapters/reorder")
def reorder_chapters(novel_id: str, data: dict) -> dict:
    """Reorder chapters. data.order = {old_number: new_number, ...}."""
    db = _db()
    if not db.get_novel(novel_id):
        raise HTTPException(404)
    order = data.get("order", {})
    with db.conn() as conn:
        mapping = _validate_reorder_mapping(conn, novel_id, order)
        _reorder_chapter_scoped_data(conn, novel_id, mapping)
    return {"ok": True}


@router.get("/api/novels/{novel_id}/chapters/{chapter_num}/versions")
def chapter_versions(novel_id: str, chapter_num: int) -> dict:
    """Get version history for a chapter."""
    return {"versions": _db().get_chapter_versions(novel_id, chapter_num)}


@router.get("/api/novels/{novel_id}/chapters/{chapter_num}/versions/{version_id}")
def chapter_version_content(version_id: int) -> dict:
    """Get a specific version's content."""
    content = _db().get_chapter_version_content(version_id)
    if not content:
        raise HTTPException(404)
    return {"content": content}


@router.delete("/api/novels/{novel_id}/chapters/{chapter_num}")
def delete_chapter(novel_id: str, chapter_num: int) -> dict:
    db = _db()
    if hasattr(db, "delete_chapter"):
        db.delete_chapter(novel_id, chapter_num)
    else:
        if hasattr(db, "clear_story_bible_chapter"):
            db.clear_story_bible_chapter(novel_id, chapter_num)
        with db.conn() as conn:
            conn.execute("DELETE FROM chapters WHERE novel_id=? AND number=?", (novel_id, chapter_num))
    return {"ok": True}
