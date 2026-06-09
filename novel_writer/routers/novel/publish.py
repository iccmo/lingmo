"""Novel publishing endpoints."""

from __future__ import annotations

import sys

from fastapi import APIRouter, BackgroundTasks, HTTPException

from novel_writer.routers.deps import get_db

router = APIRouter(tags=["publishing"])


def _db():
    return get_db()


@router.post("/api/novels/{novel_id}/publish")
def trigger_publish(novel_id: str, data: dict | None = None, background: BackgroundTasks = BackgroundTasks()):
    data = data or {}
    db = _db()
    novel = db.get_novel(novel_id)
    if not novel:
        raise HTTPException(404)
    chapters = novel.get("chapters", [])
    if not chapters:
        raise HTTPException(400, "No chapters")
    chapter_number = data.get("chapter_number") if isinstance(data, dict) else None
    if chapter_number is None:
        chapter_number = chapters[-1]["number"]
    background.add_task(_run_publish, novel_id, chapter_number)
    return {"status": "publishing", "novel_id": novel_id, "chapter": chapter_number}


@router.get("/api/novels/{novel_id}/publish-status")
def publish_status(novel_id: str) -> dict:
    """Return publish status for all chapters."""
    db = _db()
    novel = db.get_novel(novel_id)
    if not novel:
        raise HTTPException(404)
    chapters = novel.get("chapters", [])
    with db.conn() as conn:
        rows = conn.execute(
            """
            SELECT p.chapter_id, p.success, c.number
            FROM publish_records p
            JOIN chapters c ON c.id = p.chapter_id
            WHERE c.novel_id = ? AND p.success = 1
            """,
            (novel_id,),
        ).fetchall()
        published = {row["number"] for row in rows}
    return {
        "published": sorted(published),
        "pending": [
            chapter["number"]
            for chapter in chapters
            if chapter.get("word_count", 0) > 0 and chapter["number"] not in published
        ],
    }


def _run_publish(novel_id: str, chapter_number: int):
    """Background task: publish chapter to platform."""
    db = _db()
    try:
        import asyncio

        from novel_writer.publisher import Publisher

        publisher = Publisher()
        try:
            loop = asyncio.get_running_loop()
            future = asyncio.run_coroutine_threadsafe(publisher.publish(novel_id, chapter_number), loop)
            result = future.result(timeout=120)
        except RuntimeError:
            result = asyncio.run(publisher.publish(novel_id, chapter_number))
        if result.success:
            print(f"[PUB] {novel_id} ch{chapter_number} published to {result.platform}")
        else:
            print(f"[PUB FAIL] {novel_id} ch{chapter_number}: {result.error}")
    except Exception as exc:
        db.log(novel_id, "publish.failed", {"chapter": chapter_number, "error": str(exc)})
        print(f"[PUB ERROR] {novel_id}: {exc}", file=sys.stderr)
