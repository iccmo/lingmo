"""生成追踪 — 记录每章生成的每一步耗时、成本、状态。"""

import time
import json
from dataclasses import dataclass, field
from typing import Optional

from .log_config import get_logger

log = get_logger(__name__)


@dataclass
class StepTrace:
    name: str
    duration_ms: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    cost: float = 0.0
    status: str = "ok"  # ok | fallback | skipped | error
    summary: str = ""


@dataclass
class ChapterTrace:
    novel_id: str
    chapter_num: int
    steps: list[StepTrace] = field(default_factory=list)
    final_quality: float = 0.0
    total_duration_ms: int = 0
    total_cost: float = 0.0
    created_at: str = ""

    def to_dict(self) -> dict:
        return {
            "novel_id": self.novel_id,
            "chapter_num": self.chapter_num,
            "steps": [
                {"name": s.name, "duration_ms": s.duration_ms,
                 "cost": round(s.cost, 6), "status": s.status, "summary": s.summary}
                for s in self.steps
            ],
            "final_quality": self.final_quality,
            "total_duration_ms": self.total_duration_ms,
            "total_cost": round(self.total_cost, 6),
            "created_at": self.created_at,
        }


class TraceRecorder:
    """记录生成管线的每一步。"""

    def __init__(self, novel_id: str, chapter_num: int):
        self.trace = ChapterTrace(
            novel_id=novel_id,
            chapter_num=chapter_num,
        )
        self._start = time.time()
        self._start_abs = time.time()

    def step(self, name: str, tokens_in: int = 0, tokens_out: int = 0,
             cost: float = 0, status: str = "ok", summary: str = ""):
        """记录已完成的一步。"""
        now = time.time()
        duration = int((now - self._start) * 1000)
        self._start = now  # reset for next step

        self.trace.steps.append(StepTrace(
            name=name,
            duration_ms=duration,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost=cost,
            status=status,
            summary=summary,
        ))

    def finish(self, quality: float, db_instance=None):
        """标记完成，写入数据库。"""
        now = time.time()
        self.trace.final_quality = round(quality, 3)
        self.trace.total_duration_ms = int((now - self._start_abs) * 1000)
        self.trace.total_cost = sum(s.cost for s in self.trace.steps)
        from datetime import datetime
        self.trace.created_at = datetime.now().isoformat()

        if db_instance:
            try:
                db_instance.save_chapter_trace(self.trace.to_dict())
            except Exception as e:
                log.warning(f"Failed to save trace: {e}")

        # Print summary
        lines = [f"[TRACE] Ch{self.trace.chapter_num} {self.trace.total_duration_ms}ms ${self.trace.total_cost:.4f} Q={self.trace.final_quality}"]
        for s in self.trace.steps:
            lines.append(f"  {s.status:8s} {s.name:25s} {s.duration_ms:5d}ms {s.summary}")
        log.info("\n".join(lines))

        return self.trace

    # _start_abs set in __init__
