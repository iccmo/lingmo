"""
共享依赖 — 供各路由模块使用的全局状态。

server.py 在启动时调用 init_deps() 注入 db，
路由模块通过 get_db() / gen_state 访问。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..database import Database
    from ..state import GenerationState

# 模块级引用，由 server.py 的 init_deps() 设置
_db: Database | None = None
_gen_state: GenerationState | None = None


def init_deps(db: Database, gen_state: GenerationState) -> None:
    """由 server.py 启动时调用，注入共享依赖。"""
    global _db, _gen_state
    _db = db
    _gen_state = gen_state


def get_db() -> Database:
    """获取全局数据库实例。"""
    if _db is None:
        from ..database import Database
        return Database()
    return _db


def get_gen_state() -> GenerationState:
    """获取全局生成状态实例。"""
    if _gen_state is None:
        from ..state import gen_state as _fallback
        return _fallback
    return _gen_state


# Backward-compat wrappers for modules that still import these directly
def set_status(novel_id: str, status: str, message: str = "", progress: int = 0, overall: float = 0) -> None:
    get_gen_state().set_status(novel_id, status, message, progress, overall)


def get_status(novel_id: str) -> dict:
    return get_gen_state().get_status(novel_id)
