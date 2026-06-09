"""Manual foreshadowing management endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from novel_writer.routers.deps import get_db
from novel_writer.routers.novel.request_validation import bounded_int, text_field

from . import _legacy

router = APIRouter(tags=["foreshadowing"])


def _db():
    return get_db()


@router.get("/api/novels/{novel_id}/foreshadowing")
def get_foreshadowing_audit(novel_id: str) -> dict:
    """Get foreshadowing audit: open, stale, recovered stats."""
    db = _db()
    if not db.get_novel(novel_id):
        raise HTTPException(404, "Novel not found")

    from novel_writer.config import Config
    from novel_writer.generator import Generator

    provider = _legacy._get_provider(novel_id)
    cfg = Config(
        openai_api_key=provider.get("api_key", ""),
        openai_base_url=provider.get("base_url", ""),
        model=provider.get("models", "deepseek-v4-pro")[0] if provider.get("models") else "gpt-4o",
    )
    state = _legacy._load_state(novel_id)
    if not state:
        raise HTTPException(500, "Failed to load state")
    return Generator(cfg).audit_foreshadowing(state)


@router.get("/api/novels/{novel_id}/foreshadowing/all")
def get_all_foreshadowing(novel_id: str) -> dict:
    """Get all foreshadowing records."""
    db = _db()
    if not db.get_novel(novel_id):
        raise HTTPException(404)
    with db.conn() as conn:
        rows = conn.execute(
            "SELECT * FROM foreshadowing_tracker WHERE novel_id=? ORDER BY created_chapter",
            (novel_id,),
        ).fetchall()
    return {"items": [dict(row) for row in rows]}


@router.post("/api/novels/{novel_id}/foreshadowing/{fs_id}/resolve")
def resolve_foreshadowing(novel_id: str, fs_id: int, data: dict) -> dict:
    """Mark foreshadowing as resolved."""
    db = _db()
    if not db.get_novel(novel_id):
        raise HTTPException(404)
    chapter_num = bounded_int(
        data,
        "chapter_num",
        0,
        0,
        2000,
        status_code=400,
        invalid_detail="chapter_num must be an integer",
        range_detail="chapter_num must be 0-2000",
    )
    text = text_field(data, "text")
    db.resolve_foreshadowing(fs_id, chapter_num, text)
    return {"ok": True}


@router.post("/api/novels/{novel_id}/foreshadowing")
def add_foreshadowing_manual(novel_id: str, data: dict) -> dict:
    """Manually add foreshadowing."""
    db = _db()
    if not db.get_novel(novel_id):
        raise HTTPException(404)
    description = text_field(data, "description")
    if not description:
        raise HTTPException(400, "Description required")
    chapter = bounded_int(
        data,
        "chapter",
        0,
        0,
        2000,
        status_code=400,
        invalid_detail="chapter must be an integer",
        range_detail="chapter must be 0-2000",
    )
    hint = text_field(data, "hint")
    due = data.get("due_by")
    due_by = None
    if due is not None and due != "":
        due_by = bounded_int(
            data,
            "due_by",
            0,
            0,
            2000,
            status_code=400,
            invalid_detail="due_by must be an integer",
            range_detail="due_by must be 0-2000",
        )
    db.save_foreshadowing(novel_id, chapter, description, hint, due_by)
    return {"ok": True}
