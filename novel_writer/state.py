"""统一共享状态 — 所有模块使用同一个状态实例。

避免 novel.py 和 server.py 各自维护独立 _gen_status 的问题。
"""

import asyncio
import threading


TERMINAL_GENERATION_STATUSES = {"", "idle", "complete", "done", "error", "failed", "finished"}


def is_active_generation_status(status: str | None) -> bool:
    """Treat any non-terminal generation-state label as an active operation."""
    return (status or "").strip().lower() not in TERMINAL_GENERATION_STATUSES


class GenerationState:
    """生成管线共享状态，线程安全。"""

    def __init__(self):
        self._status: dict[str, dict] = {}
        self._lock = threading.Lock()
        self._events: dict[str, asyncio.Event] = {}  # novel_id → Event for SSE push
        self._directions: dict[str, str] = {}
        self._directions_lock = threading.Lock()
        self._job_queue: dict[str, dict] = {}
        self._job_lock = threading.Lock()
        self._agent_memos: dict[str, dict] = {}

    # ── Generation Status ──

    def set_status(
        self,
        novel_id: str,
        status: str,
        message: str = "",
        progress: int = 0,
        overall: float = 0,
        extra: dict | None = None,
    ):
        with self._lock:
            previous = self._status.get(novel_id, {})
            next_status = {"status": status, "message": message, "progress": progress}
            if self._should_preserve_stream(previous, status, progress):
                for key in ("stream_content", "stream_version"):
                    if key in previous:
                        next_status[key] = previous[key]
            if overall > 0:
                next_status["overall"] = round(overall, 2)
            if extra:
                next_status.update(extra)
            self._status[novel_id] = next_status
        # Notify SSE listeners
        event = self._events.get(novel_id)
        if event:
            event.set()

    @staticmethod
    def _should_preserve_stream(previous: dict, status: str, progress: int) -> bool:
        if "stream_content" not in previous:
            return False
        if status == "generating" and progress <= 10:
            return False
        previous_status = previous.get("status")
        if status == "generating" and previous_status in {"complete", "error", "idle"}:
            return False
        return status in {"generating", "reviewing", "editing", "judging", "complete", "error"}

    def update_stream_content(self, novel_id: str, content: str):
        """Update live preview text without resetting the current generation status."""
        with self._lock:
            current = self._status.setdefault(
                novel_id,
                {"status": "generating", "message": "", "progress": 0},
            )
            current["stream_content"] = content
            current["stream_version"] = int(current.get("stream_version", 0)) + 1
        event = self._events.get(novel_id)
        if event:
            event.set()

    def get_status(self, novel_id: str) -> dict:
        return self._status.get(novel_id, {"status": "idle", "message": "", "progress": 0})

    def get_status_dict(self) -> dict[str, dict]:
        """Return a shallow copy for read-only iteration (e.g. SSE polling)."""
        with self._lock:
            return dict(self._status)

    def pop_status(self, novel_id: str) -> dict | None:
        with self._lock:
            return self._status.pop(novel_id, None)

    # ── Generation Directions (quality threshold, soul injection, etc.) ──

    def set_direction(self, key: str, value: str):
        with self._directions_lock:
            self._directions[key] = value

    def pop_direction(self, key: str, default: str = "") -> str:
        with self._directions_lock:
            return self._directions.pop(key, default)

    def clean_directions(self, novel_id: str):
        """Remove all direction keys for a given novel."""
        with self._directions_lock:
            for suffix in ("", "_soul", "_qthreshold", "_model", "_compression"):
                self._directions.pop(novel_id + suffix, None)

    # ── Job Queue ──

    def get_job(self, novel_id: str) -> dict | None:
        with self._job_lock:
            for job in self._job_queue.values():
                if job["novel_id"] == novel_id and job["status"] in ("queued", "running"):
                    return dict(job)
        return None

    def set_job(self, job_id: str, job: dict):
        with self._job_lock:
            self._job_queue[job_id] = job

    def update_job(self, job_id: str, **kw):
        with self._job_lock:
            if job_id in self._job_queue:
                self._job_queue[job_id].update(kw)

    def remove_job(self, job_id: str):
        with self._job_lock:
            self._job_queue.pop(job_id, None)

    def get_job_dict(self) -> dict[str, dict]:
        with self._job_lock:
            return dict(self._job_queue)

    # ── SSE Events ──

    def get_event(self, novel_id: str) -> asyncio.Event:
        """Get or create an asyncio.Event for SSE push notifications."""
        if novel_id not in self._events:
            self._events[novel_id] = asyncio.Event()
        return self._events[novel_id]

    def clear_event(self, novel_id: str):
        """Clear event after SSE consumer disconnects."""
        self._events.pop(novel_id, None)

    # ── Agent Memos ──

    def get_memo(self, novel_id: str) -> dict | None:
        return self._agent_memos.get(novel_id)

    def set_memo(self, novel_id: str, memo: dict):
        self._agent_memos[novel_id] = memo

    def pop_memo(self, novel_id: str) -> dict | None:
        return self._agent_memos.pop(novel_id, None)


# Singleton
gen_state = GenerationState()
