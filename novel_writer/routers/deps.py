"""
共享依赖 — 供各路由模块使用的全局状态。

server.py 在启动时调用 init_deps() 注入 db 和状态管理函数，
路由模块通过 get_db() / set_status() / get_status() 访问。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from ..database import Database

# 模块级引用，由 server.py 的 init_deps() 设置
_db: Database | None = None
_set_status_fn: Callable[..., None] | None = None
_get_status_fn: Callable[..., dict] | None = None


def init_deps(
    db: Database,
    set_status_fn: Callable[..., None],
    get_status_fn: Callable[..., dict],
) -> None:
    """由 server.py 启动时调用，注入共享依赖。"""
    global _db, _set_status_fn, _get_status_fn
    _db = db
    _set_status_fn = set_status_fn
    _get_status_fn = get_status_fn


def get_db() -> Database:
    """获取全局数据库实例。"""
    if _db is None:
        # Fallback: 兜底初始化（正常不应走到这里）
        from ..database import Database
        return Database()
    return _db


def set_status(novel_id: str, status: str, message: str = "", progress: int = 0, overall: float = 0) -> None:
    """更新生成状态。"""
    if _set_status_fn:
        _set_status_fn(novel_id, status, message, progress, overall)


def get_status(novel_id: str) -> dict:
    """获取生成状态。"""
    if _get_status_fn:
        return _get_status_fn(novel_id)
    return {"status": "unknown", "message": "deps not initialized"}
