"""结构化日志 — 基于 Python logging + rich 终端输出。"""

import logging
import sys

# ── Format ──
FORMAT = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"
DATE_FMT = "%H:%M:%S"

# ── Root logger ──
logging.basicConfig(
    level=logging.INFO,
    format=FORMAT,
    datefmt=DATE_FMT,
    stream=sys.stdout,
)

# ── Module loggers ──

def get_logger(name: str) -> logging.Logger:
    """获取命名 logger。"""
    return logging.getLogger(name)


# Pre-configure noisy libraries
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("asyncio").setLevel(logging.WARNING)
