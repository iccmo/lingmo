"""结构化日志 — JSON 格式输出到 stderr，所有模块共用"""

import json, sys, time
from datetime import datetime, timezone


def log_event(event: str, **kwargs):
    """输出结构化 JSON 日志到 stderr"""
    entry = {
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
        "event": event,
        **kwargs
    }
    print(json.dumps(entry, ensure_ascii=False), file=sys.stderr)


class Metrics:
    """轻量级指标收集（内存中，周期性写入 DB）"""
    def __init__(self):
        self.counters: dict[str, int] = {}
        self.gauges: dict[str, float] = {}
        self.timings: dict[str, list[float]] = {}

    def incr(self, name: str, delta: int = 1):
        self.counters[name] = self.counters.get(name, 0) + delta

    def gauge(self, name: str, value: float):
        self.gauges[name] = value

    def timing(self, name: str, duration_ms: float):
        if name not in self.timings:
            self.timings[name] = []
        self.timings[name].append(duration_ms)

    def snapshot(self) -> dict:
        result = {"counters": dict(self.counters), "gauges": dict(self.gauges)}
        result["timings"] = {
            k: {
                "count": len(v),
                "avg_ms": round(sum(v) / len(v), 1) if v else 0,
                "p95_ms": round(sorted(v)[int(len(v) * 0.95)], 1) if len(v) >= 20 else None,
            }
            for k, v in self.timings.items()
        }
        return result


# Global metrics instance
metrics = Metrics()
