"""Agent pipeline orchestration endpoints."""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, HTTPException

from novel_writer.routers.deps import get_db, get_gen_state

from . import _legacy
from .agent_pipeline_service import architect_outline, editor_in_chief_brief
from .generation import _ensure_generation_idle

router = APIRouter(tags=["agent-pipeline"])


def _db():
    return get_db()


@router.get("/api/novels/{novel_id}/agent-report")
def agent_report(novel_id: str) -> dict:
    """Return all agent results from the last pipeline run for this novel."""
    if not _db().get_novel(novel_id):
        raise HTTPException(404, "Novel not found")
    memos = get_gen_state()._agent_memos.get(novel_id, {})
    return {
        "novel_id": novel_id,
        "agent_count": len(memos),
        "agents": memos,
    }


@router.post("/api/novels/{novel_id}/agent-pipeline")
def run_agent_pipeline(novel_id: str, background: BackgroundTasks, data: dict = {}) -> dict:
    """Run the complete Agent pipeline for next chapter generation."""
    db = _db()
    novel = db.get_novel(novel_id)
    if not novel:
        raise HTTPException(404)
    _ensure_generation_idle(novel_id)

    next_chapter = db.get_next_chapter_number(novel_id) if hasattr(db, "get_next_chapter_number") else (
        max([chapter["number"] for chapter in novel.get("chapters", []) if chapter.get("word_count", 0) > 0], default=0) + 1
    )
    brief = editor_in_chief_brief(novel_id, next_chapter)
    outline = architect_outline(novel_id, next_chapter, brief)

    if brief or outline:
        _legacy._gen_directions[novel_id] = f"【总编简报】\n{brief}\n\n【章节大纲】\n{outline}"
        _legacy._gen_directions[novel_id + "_qthreshold"] = "0.75"

    background.add_task(_legacy._run_generation, novel_id)
    return {
        "status": "agent_pipeline_started",
        "novel_id": novel_id,
        "next_chapter": next_chapter,
        "brief": brief[:200] if brief else "(skipped)",
        "outline": outline[:200] if outline else "(skipped)",
    }
