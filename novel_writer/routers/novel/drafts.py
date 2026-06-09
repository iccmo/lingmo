"""Draft direction and selected-draft expansion endpoints."""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, HTTPException

from novel_writer.routers.deps import get_db

from .draft_service import generator_for, run_draft, run_expand

router = APIRouter(tags=["drafts"])


def _db():
    return get_db()


@router.post("/api/novels/{novel_id}/draft")
def draft_directions(novel_id: str, data: dict, background: BackgroundTasks) -> dict:
    if not _db().get_novel(novel_id):
        raise HTTPException(404)
    author_input = data.get("input", "")
    if not author_input:
        raise HTTPException(400, "input required")
    background.add_task(run_draft, novel_id, author_input)
    return {"status": "drafting", "novel_id": novel_id}


@router.post("/api/novels/{novel_id}/expand")
def expand_chapter(novel_id: str, data: dict, background: BackgroundTasks) -> dict:
    if not _db().get_novel(novel_id):
        raise HTTPException(404)
    chosen_id = data.get("chosen_id", "")
    edits = data.get("edits", "")
    if not chosen_id:
        raise HTTPException(400, "chosen_id required")
    background.add_task(
        run_expand,
        novel_id,
        chosen_id,
        data.get("direction", ""),
        data.get("preview", ""),
        data.get("hook", ""),
        edits,
    )
    return {"status": "expanding", "novel_id": novel_id}


@router.get("/api/novels/{novel_id}/preview")
def preview_chapter(novel_id: str) -> dict:
    """Generate a short style preview without creating a full chapter."""
    db = _db()
    novel = db.get_novel(novel_id)
    if not novel:
        raise HTTPException(404)

    gen = generator_for(novel_id)
    sample = gen._call_llm_with_retry(
        [
            {
                "role": "system",
                "content": "你是小说家。写200字的章节开头——展示风格、声音和节奏。这是给编辑看的样本，不需要完整章节。",
            },
            {
                "role": "user",
                "content": f"书名：{novel['title']}\n简介：{novel.get('synopsis', '')}\n请写200字开篇样本。",
            },
        ],
        max_tokens=400,
    )
    return {"preview": sample[:400]}
