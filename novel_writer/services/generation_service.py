"""GenerationService — 生成管线封装，Pydantic 类型安全。"""

import json
from typing import Optional

from ..state import gen_state, is_active_generation_status
from ..schemas import GenerateRequest, GenerateBatchRequest, GenerateResponse, QueueStatus, GenStatus
from ..log_config import get_logger

log = get_logger(__name__)


def _next_chapter_number(novel: dict) -> int:
    return max(
        [chapter.get("number", 0) for chapter in novel.get("chapters", []) if chapter.get("word_count", 0) > 0],
        default=0,
    ) + 1


class GenerationService:
    """章节生成服务。委托给 legacy 管线，提供类型安全接口。"""

    def __init__(self, db):
        self.db = db

    def trigger_generate(self, novel_id: str, req: GenerateRequest) -> GenerateResponse:
        """触发单章生成（后台线程，立即返回 job_id）。"""
        from ..routers.novel._legacy import _run_generation

        novel = self.db.get_novel(novel_id)
        if not novel:
            raise ValueError(f"Novel {novel_id} not found")

        # Guard: prevent concurrent generation for the same novel
        current = gen_state.get_status(novel_id)
        if is_active_generation_status(current.get("status")) or gen_state.get_job(novel_id):
            raise ValueError("已有生成任务进行中，请等待完成")

        # 通过 _gen_directions 向后台任务传递参数（legacy 模式）
        gs = gen_state
        if req.direction:
            gs.set_direction(novel_id, req.direction)
        if req.soul_injection:
            gs.set_direction(novel_id + "_soul", req.soul_injection)
        gs.set_direction(novel_id + "_qthreshold", str(req.quality_threshold))
        gs.set_direction(novel_id + "_compression", req.compression)

        # 启动后台生成
        import threading
        job_id = f"gen-{novel_id[:6]}-{id(req) % 10000}"
        gs.set_status(novel_id, "generating", "正在构思章节…", 10)

        thread = threading.Thread(target=_run_generation, args=(novel_id,), daemon=True)
        thread.start()

        log.info(f"Generation started: {job_id}", extra={"novel_id": novel_id})

        return GenerateResponse(
            job_id=job_id,
            status="queued",
            count=1,
            next_chapter=_next_chapter_number(novel),
        )

    def trigger_batch(self, novel_id: str, req: GenerateBatchRequest) -> GenerateResponse:
        """触发批量生成。"""
        if not self.db.get_novel(novel_id):
            raise ValueError(f"Novel {novel_id} not found")

        import threading

        # Set quality threshold for batch runner
        gs = gen_state
        current = gs.get_status(novel_id)
        if is_active_generation_status(current.get("status")) or gs.get_job(novel_id):
            raise ValueError("已有生成任务进行中，请等待完成")

        gs.set_direction(novel_id + "_qthreshold", str(req.quality_threshold))

        job_id = f"batch-{novel_id[:6]}-{id(req) % 10000}"
        gs.set_status(novel_id, "running", f"批量生成{req.count}章...", 0)
        gs.set_job(job_id, {"job_id": job_id, "novel_id": novel_id, "status": "running", "progress": {"current": 0, "total": req.count}, "count": req.count})
        thread = threading.Thread(
            target=self._run_batch_job,
            args=(job_id, novel_id, req.count, req.quality_threshold),
            daemon=True,
        )
        thread.start()

        log.info(f"Batch generation started: {job_id}", extra={"novel_id": novel_id, "count": req.count})
        return GenerateResponse(
            job_id=job_id,
            status="queued",
            count=req.count,
            next_chapter=_next_chapter_number(self.db.get_novel(novel_id)),
        )

    def _run_batch_job(self, job_id: str, novel_id: str, count: int, quality_threshold: float) -> None:
        from ..routers.novel.generation_service import run_batch_generation

        gs = gen_state
        try:
            result = run_batch_generation(novel_id, count, quality_threshold) or {}
            generated = int(result.get("generated", 0) or 0)
            message = result.get("message") or "批量生成未产出有效章节"
            if generated <= 0:
                gs.update_job(
                    job_id,
                    status="error",
                    last_error=message,
                    progress={"current": count, "total": count},
                )
                gs.set_status(novel_id, "error", message, 0)
                return

            updates = {"status": "done", "progress": {"current": count, "total": count}}
            if int(result.get("failed", 0) or 0) > 0:
                updates["last_error"] = message
            gs.update_job(job_id, **updates)
            gs.set_status(novel_id, "complete", message, 100)
        except Exception as exc:
            message = str(exc)[:500]
            gs.update_job(job_id, status="error", last_error=message)
            gs.set_status(novel_id, "error", message, 0)

    def get_queue_status(self, novel_id: str) -> QueueStatus:
        """获取生成队列状态。"""
        gs = gen_state
        job = gs.get_job(novel_id)
        st = gs.get_status(novel_id)

        raw_progress = st.get("progress", {"current": 0, "total": 0})
        if isinstance(raw_progress, (int, float)):
            raw_progress = {"current": int(raw_progress), "total": 100}
        elif not isinstance(raw_progress, dict):
            raw_progress = {"current": 0, "total": 0}

        return QueueStatus(
            job_id=job.get("job_id") if job else None,
            status=st["status"],
            progress=raw_progress,
            last_error=job.get("last_error") if job else None,
        )

    def get_gen_status(self, novel_id: str) -> GenStatus:
        """获取当前生成状态（SSE 用）。"""
        st = gen_state.get_status(novel_id)
        return GenStatus(
            status=st["status"],
            message=st.get("message", ""),
            progress=st.get("progress", 0),
            overall=st.get("overall"),
            stream_content=st.get("stream_content"),
            grade=st.get("grade"),
            quality_detail=st.get("quality_detail"),
        )
