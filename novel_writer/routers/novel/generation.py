"""Generation trigger, queue, auto-mode, and streaming status endpoints."""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import StreamingResponse

from novel_writer.routers.deps import get_db, get_gen_state
from novel_writer.state import is_active_generation_status

from .generation_service import get_queue_status, start_batch_job
from .request_validation import bounded_float, bounded_int, text_field
from . import _legacy

router = APIRouter(tags=["generation"])


def _bounded_float(data: dict, key: str, default: float, lower: float, upper: float) -> float:
    return bounded_float(
        data,
        key,
        default,
        lower,
        upper,
        status_code=422,
        invalid_detail=f"{key} 必须是数字",
        range_detail=f"{key} 必须在 {lower}-{upper} 之间",
    )


def _bounded_int(data: dict, key: str, default: int, lower: int, upper: int) -> int:
    return bounded_int(
        data,
        key,
        default,
        lower,
        upper,
        status_code=422,
        invalid_detail=f"{key} 必须是整数",
        range_detail=f"{key} 必须在 {lower}-{upper} 之间",
    )


def _db():
    return get_db()


def _set_status(novel_id: str, status: str, message: str = "", progress: int = 0, overall: float = 0) -> None:
    get_gen_state().set_status(novel_id, status, message, progress, overall)


def _get_status(novel_id: str) -> dict:
    return get_gen_state().get_status(novel_id)


def _ensure_generation_idle(novel_id: str) -> None:
    current_status = _get_status(novel_id)
    if is_active_generation_status(current_status.get("status")):
        raise HTTPException(409, detail="已有生成任务进行中，请等待完成")

    existing = get_queue_status(novel_id, active_only=True)
    if existing:
        raise HTTPException(409, f"已有任务进行中: {existing['job_id']} (状态: {existing['status']})")


def _sse_status_key(status: dict) -> str:
    """Fingerprint fields that should trigger a live generation status push."""
    return json.dumps(
        {
            "status": status.get("status"),
            "progress": status.get("progress"),
            "message": status.get("message"),
            "overall": status.get("overall"),
            "grade": status.get("grade"),
            "stream_version": status.get("stream_version"),
        },
        sort_keys=True,
        ensure_ascii=False,
    )


@router.post("/api/novels/{novel_id}/generate")
def trigger_generate(novel_id: str, background: BackgroundTasks, data: dict = {}) -> dict:
    db = _db()
    novel = db.get_novel(novel_id)
    if not novel:
        raise HTTPException(404)

    _ensure_generation_idle(novel_id)

    data = data or {}
    direction = text_field(data, "direction")
    if direction:
        _legacy._gen_directions[novel_id] = direction

    soul_injection = text_field(data, "soul_injection")
    if soul_injection:
        _legacy._gen_directions[novel_id + "_soul"] = soul_injection

    quality_threshold = _bounded_float(data, "quality_threshold", 0.8, 0.5, 1.0)
    _legacy._gen_directions[novel_id + "_qthreshold"] = str(quality_threshold)

    model_override = text_field(data, "model")
    if model_override:
        _legacy._gen_directions[novel_id + "_model"] = model_override

    compression = text_field(data, "compression").upper()
    if compression in ("L0", "L1", "L2", "L3", "NONE"):
        _legacy._gen_directions[novel_id + "_compression"] = compression

    if data.get("pattern_disruption"):
        _legacy._gen_directions[novel_id + "_pattern_disruption"] = "1"

    _set_status(novel_id, "generating", "正在排队...", 5)
    background.add_task(_legacy._run_generation, novel_id)
    next_chapter = db.get_next_chapter_number(novel_id) if hasattr(db, "get_next_chapter_number") else (
        max([chapter["number"] for chapter in novel.get("chapters", []) if chapter.get("word_count", 0) > 0], default=0) + 1
    )
    return {"status": "generating", "novel_id": novel_id, "next_chapter": next_chapter}


@router.post("/api/novels/{novel_id}/generate-batch")
def trigger_generate_batch(novel_id: str, data: dict, background: BackgroundTasks) -> dict:
    db = _db()
    novel = db.get_novel(novel_id)
    if not novel:
        raise HTTPException(404)

    data = data or {}
    count = _bounded_int(data, "count", 5, 1, 20)
    quality_threshold = _bounded_float(data, "quality_threshold", 0.8, 0.5, 1.0)
    model_override = str(data.get("model", "") or "").strip() or None

    _ensure_generation_idle(novel_id)

    next_chapter = db.get_next_chapter_number(novel_id) if hasattr(db, "get_next_chapter_number") else (
        max([chapter["number"] for chapter in novel.get("chapters", []) if chapter.get("word_count", 0) > 0], default=0) + 1
    )
    result = start_batch_job(novel_id, count, quality_threshold, model_override)
    result["next_chapter"] = next_chapter
    return result


@router.get("/api/novels/{novel_id}/generate/queue-status")
def generate_queue_status(novel_id: str) -> dict:
    """Get the current batch generation queue status for a novel."""
    queue_status = get_queue_status(novel_id)
    if not queue_status:
        return {"job_id": None, "status": "idle", "progress": {"current": 0, "total": 0}, "last_error": None}
    return queue_status


@router.get("/api/novels/{novel_id}/generate/status")
def generate_status(novel_id: str) -> dict:
    """Get the current single-generation status for fallback polling."""
    return _get_status(novel_id)


@router.post("/api/novels/{novel_id}/auto/start")
def auto_start(novel_id: str) -> dict:
    db = _db()
    if not db.get_novel(novel_id):
        raise HTTPException(404)
    db.set_scheduler_state(novel_id, is_running=1)
    db.log(novel_id, "mode.switched", {"from": "creator", "to": "auto"})
    return {"status": "started"}


@router.post("/api/novels/{novel_id}/auto/stop")
def auto_stop(novel_id: str) -> dict:
    db = _db()
    db.set_scheduler_state(novel_id, is_running=0)
    db.log(novel_id, "mode.switched", {"from": "auto", "to": "creator"})
    return {"status": "stopped"}


@router.post("/api/novels/{novel_id}/auto/once")
def auto_once(novel_id: str, background: BackgroundTasks) -> dict:
    if not _db().get_novel(novel_id):
        raise HTTPException(404)
    _ensure_generation_idle(novel_id)
    _set_status(novel_id, "generating", "正在排队...", 5)
    background.add_task(_legacy._run_generation, novel_id)
    return {"status": "running"}


@router.get("/api/novels/{novel_id}/generate/stream")
async def generate_stream_sse(novel_id: str) -> StreamingResponse:
    """Server-Sent Events stream for real-time generation status."""

    async def event_stream():
        last_status = ""
        while True:
            status = _get_status(novel_id)
            current = _sse_status_key(status)
            emitted = False
            if current != last_status:
                last_status = current
                yield f"data: {json.dumps(status)}\n\n"
                emitted = True
            if not is_active_generation_status(status.get("status")):
                if status.get("status") != "idle" and not emitted:
                    yield f"data: {json.dumps(status)}\n\n"
                break
            await asyncio.sleep(0.5)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
