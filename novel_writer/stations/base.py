"""
Station 基础设施 — BaseStation 抽象基类 + StationContext 类型化上下文。

所有 Station 继承 BaseStation，统一接口和共享逻辑。

知识传递机制（借鉴 Manus Knowledge Module）：
  - 每个工位可通过 add_knowledge() 记录决策
  - run() 返回值可包含 "knowledge" 键，由上层管线链式传递
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..database import Database


# ── 工位执行结果 ─────────────────────────────────────────────────


@dataclass
class StationResult:
    """工位执行结果 — 包含状态、数据、决策知识。

    知识字段用于工位间传递决策理由，下游工位可读取上游知识
    来增强自身行为（如 AI Director 的 mood 决定 prompt_generator
    的风格关键词）。
    """

    status: str = "ok"
    data: dict = field(default_factory=dict)
    knowledge: list[dict] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """序列化为 dict，兼容 run() 返回格式。"""
        result: dict = {"status": self.status, **self.data}
        if self.knowledge:
            result["knowledge"] = self.knowledge
        if self.errors:
            result["errors"] = self.errors
        return result

    def add_knowledge(self, station: str, decision: str, rationale: str = "") -> None:
        """便捷方法：添加一条决策知识。"""
        self.knowledge.append({
            "station": station,
            "decision": decision,
            "rationale": rationale,
        })


# ── 上下文 ──────────────────────────────────────────────────────


@dataclass
class StationContext:
    """类型化的 Station 上下文，替代无类型的 dict。"""
    novel_id: str = ""
    chapter_num: int = 0
    db: Database | None = None
    content: str = ""
    force: bool = False
    # Film Studio fields
    output_dir: str = ""
    provider: str = ""
    api_key: str = ""
    # 知识链：上游工位传递的决策知识
    knowledge: list[dict] = field(default_factory=list)
    # 透传额外参数
    extra: dict = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: dict) -> StationContext:
        """从 dict 构建 StationContext，忽略未知字段。"""
        known = {f.name for f in cls.__dataclass_fields__.values() if f.name != "extra"}
        extra = {k: v for k, v in d.items() if k not in known}
        return cls(
            novel_id=d.get("novel_id", ""),
            chapter_num=int(d.get("chapter_num", 0)),
            db=d.get("db"),
            content=d.get("content", ""),
            force=d.get("force", False),
            output_dir=d.get("output_dir", ""),
            provider=d.get("provider", ""),
            api_key=d.get("api_key", ""),
            knowledge=d.get("knowledge", []),
            extra=extra,
        )


# ── 抽象基类 ────────────────────────────────────────────────────


class BaseStation(ABC):
    """所有 Station 的抽象基类。

    知识传递：子类在 run() 中调用 add_knowledge() 记录决策，
    结果通过返回值中的 "knowledge" 键传递给下游。
    """

    name: str = ""
    required_every_chapter: bool = False

    def __init__(self) -> None:
        self._knowledge: list[dict] = []

    @abstractmethod
    def run(self, ctx: dict) -> dict:
        """执行工位逻辑。

        Args:
            ctx: 上下文字典，包含 novel_id, chapter_num, db,
                 knowledge（上游工位决策知识，可选）等。

        Returns:
            结果字典，至少包含 status 字段。
            可选 "knowledge" 键包含本工位决策知识列表。
        """
        ...

    def add_knowledge(self, decision: str, rationale: str = "") -> None:
        """记录本工位的决策知识。

        Args:
            decision: 决策描述（如 "生成8个镜头"）
            rationale: 决策理由（如 "压抑的情绪基调"）
        """
        self._knowledge.append({
            "station": self.name,
            "decision": decision,
            "rationale": rationale,
        })

    def get_knowledge(self) -> list[dict]:
        """获取本工位记录的所有决策知识。"""
        return list(self._knowledge)

    def reset_knowledge(self) -> None:
        """清空决策知识（每次 run 前调用）。"""
        self._knowledge = []

    def get_ctx(self, ctx: dict) -> StationContext:
        """将 dict 上下文解析为 StationContext。"""
        return StationContext.from_dict(ctx)

    @staticmethod
    def get_providers(db: Database) -> list[dict]:
        """获取所有可用的 LLM provider（按优先级排序）。"""
        try:
            providers = db.list_providers()
            enabled = [p for p in providers if p.get("is_enabled") and p.get("api_key")]
            enabled.sort(key=lambda p: p.get("priority", 0), reverse=True)
            return enabled
        except Exception:
            return []
