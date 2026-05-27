"""
角色视觉一致性记忆 — CharacterConsistencyMemory

跨章节追踪角色外观变化（服装、伤痕、发型等），确保 AI 绘图 prompt
在不同章节间保持视觉一致性。

灵感来源：Windsurf Memory System 的 "proactively inject context" 策略。

存储：复用 character_state 表的 notes 字段（JSON 格式）。
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ...database import Database

logger = logging.getLogger(__name__)


@dataclass
class VisualSnapshot:
    """角色在某章的视觉快照。"""
    chapter_num: int
    costume: str = ""
    injury_marks: str = ""
    hair_style: str = ""
    accessories: str = ""
    mood_expression: str = ""
    extra: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"chapter_num": self.chapter_num}
        if self.costume:
            d["costume"] = self.costume
        if self.injury_marks:
            d["injury_marks"] = self.injury_marks
        if self.hair_style:
            d["hair_style"] = self.hair_style
        if self.accessories:
            d["accessories"] = self.accessories
        if self.mood_expression:
            d["mood_expression"] = self.mood_expression
        if self.extra:
            d["extra"] = self.extra
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> VisualSnapshot:
        return cls(
            chapter_num=d.get("chapter_num", 0),
            costume=d.get("costume", ""),
            injury_marks=d.get("injury_marks", ""),
            hair_style=d.get("hair_style", ""),
            accessories=d.get("accessories", ""),
            mood_expression=d.get("mood_expression", ""),
            extra=d.get("extra", {}),
        )


class CharacterConsistencyMemory:
    """跨章节角色视觉一致性记忆。

    借鉴 Windsurf Memory System：
    - 主动记录，无需用户确认
    - 自动在需要时注入到 prompt
    - 跟踪视觉属性的渐变（如伤疤、服装变化）

    使用方式::

        memory = CharacterConsistencyMemory(db, novel_id)

        # 记录视觉状态
        memory.record_visual_state(1, "林动", {
            "costume": "灰色卫衣", "hair_style": "黑色短发"
        })

        # 在 prompt_generator 中注入一致性约束
        prompt_hint = memory.build_consistency_prompt("林动", current_chapter=5)
    """

    _VISUAL_KEY = "__visual_consistency"

    def __init__(self, db: Database, novel_id: str) -> None:
        self.db = db
        self.novel_id = novel_id

    # ── 写入 ──────────────────────────────────────────────────────

    def record_visual_state(
        self,
        chapter_num: int,
        char_key: str,
        attributes: dict[str, str],
    ) -> None:
        """记录角色在某章的视觉状态。

        将视觉属性存入 character_state.notes 的 JSON 字段中，
        与已有叙事层数据（emotion, location 等）共存。

        Args:
            chapter_num: 章节号。0 = 基线（视觉圣经初始设定）。
            char_key: 角色名/键。
            attributes: 视觉属性字典。键包括 costume, injury_marks,
                hair_style, accessories, mood_expression 以及任意扩展。
        """
        snapshot = VisualSnapshot(chapter_num=chapter_num, **{  # type: ignore[arg-type]
            k: v for k, v in attributes.items()
            if k in VisualSnapshot.__dataclass_fields__ and k != "chapter_num"
        })

        # 读取已有 notes，合并 visual 数据
        existing_notes = self._read_notes(chapter_num, char_key)
        visual_history: list[dict] = existing_notes.get(self._VISUAL_KEY, [])

        # 覆盖同一章节的记录
        visual_history = [
            s for s in visual_history if s.get("chapter_num") != chapter_num
        ]
        visual_history.append(snapshot.to_dict())
        visual_history.sort(key=lambda s: s.get("chapter_num", 0))

        existing_notes[self._VISUAL_KEY] = visual_history
        self._write_notes(chapter_num, char_key, existing_notes)

        logger.debug(
            "Recorded visual state: %s ch%d — %s",
            char_key, chapter_num, attributes,
        )

    # ── 读取 ──────────────────────────────────────────────────────

    def get_visual_history(
        self,
        char_key: str,
        up_to_chapter: int = 9999,
    ) -> list[VisualSnapshot]:
        """获取角色视觉历史（到指定章节为止）。

        从所有 character_state 记录中聚合该角色的视觉快照。

        Args:
            char_key: 角色名/键。
            up_to_chapter: 最大章节号（含）。

        Returns:
            按章节排序的视觉快照列表。
        """
        # 使用 get_all_character_states 获取所有章节的记录
        # （get_character_state 无 chapter_num 时只返回最大章节）
        states = self.db.get_all_character_states(
            self.novel_id, char_name=char_key, up_to_chapter=up_to_chapter,
        )
        snapshots: list[VisualSnapshot] = []
        for cs in states:
            notes_raw = cs.get("notes", "")
            if not notes_raw:
                continue
            try:
                notes = json.loads(notes_raw)
            except (json.JSONDecodeError, TypeError):
                continue
            visual_list = notes.get(self._VISUAL_KEY, [])
            for vd in visual_list:
                snapshots.append(VisualSnapshot.from_dict(vd))

        snapshots.sort(key=lambda s: s.chapter_num)
        return snapshots

    def get_latest_visual(self, char_key: str, current_chapter: int) -> VisualSnapshot | None:
        """获取角色到当前章节为止的最新视觉状态。"""
        history = self.get_visual_history(char_key, up_to_chapter=current_chapter)
        return history[-1] if history else None

    # ── Prompt 注入 ────────────────────────────────────────────────

    def build_consistency_prompt(self, char_key: str, current_chapter: int) -> str:
        """构建一致性提示词（注入到 prompt_generator）。

        将角色视觉历史浓缩为一句描述，告诉 AI 绘图工具
        "角色之前长什么样，现在应该长什么样"。

        Returns:
            一致性提示词字符串。如果无历史记录则返回空字符串。

        Example::

            "林动：前3章穿灰色卫衣，第4章受伤后左臂缠绷带。
             当前第5章——保持绷带，服装可升级但体型/发型不变。"
        """
        history = self.get_visual_history(char_key, up_to_chapter=current_chapter)
        if not history:
            return ""

        # 基线（第0章或最早的记录）
        baseline = history[0]
        # 最新状态
        latest = history[-1]

        parts: list[str] = [f"{char_key}："]

        # 如果有服装变化
        if baseline.costume and latest.costume:
            if baseline.costume != latest.costume:
                parts.append(f"最初穿{baseline.costume}，第{latest.chapter_num}章换为{latest.costume}")
            else:
                parts.append(f"穿{latest.costume}")

        # 伤痕变化
        if latest.injury_marks and latest.injury_marks != "无":
            parts.append(f"有{latest.injury_marks}")

        # 发型
        if latest.hair_style:
            parts.append(f"{latest.hair_style}")

        # 饰品
        if latest.accessories:
            parts.append(f"佩戴{latest.accessories}")

        # 如果历史超过2个快照，加上渐变说明
        if len(history) > 2:
            changes = []
            for snap in history[1:]:
                snap_changes = []
                if snap.costume and snap.costume != baseline.costume:
                    snap_changes.append(f"换{snap.costume}")
                if snap.injury_marks and snap.injury_marks != "无":
                    snap_changes.append(f"新增{snap.injury_marks}")
                if snap_changes:
                    changes.append(f"第{snap.chapter_num}章{'，'.join(snap_changes)}")
            if changes:
                parts.append(f"变化：{'；'.join(changes)}")

        # 稳定性约束
        parts.append(
            f"第{current_chapter}章——保持体型、发型、面部特征不变，"
            "服装可升级但整体风格延续"
        )

        return "".join(parts)

    # ── 一致性检测 ──────────────────────────────────────────────────

    def detect_inconsistency(
        self,
        chapter_num: int,
        char_key: str,
        new_attributes: dict[str, str],
    ) -> list[str]:
        """检测新描述与历史的一致性冲突。

        Args:
            chapter_num: 当前章节号。
            char_key: 角色名/键。
            new_attributes: 新的视觉属性描述。

        Returns:
            冲突描述列表。空列表表示一致。
        """
        history = self.get_visual_history(char_key, up_to_chapter=chapter_num - 1)
        if not history:
            return []

        errors: list[str] = []
        latest = history[-1]

        # 检查伤痕一致性：如果之前有永久性伤痕，新描述中不能缺失
        if (latest.injury_marks
                and latest.injury_marks != "无"
                and not new_attributes.get("injury_marks")):
            errors.append(
                f"{char_key}在第{latest.chapter_num}章有{latest.injury_marks}，"
                f"但第{chapter_num}章未提及伤痕"
            )

        # 检查极端体型变化（如身高变化不可能）
        # 这个规则在 build_consistency_prompt 中通过"保持体型不变"约束

        return errors

    # ── 内部方法 ──────────────────────────────────────────────────

    def _read_notes(self, chapter_num: int, char_key: str) -> dict[str, Any]:
        """读取 character_state.notes 并解析为 dict。"""
        states = self.db.get_character_state(self.novel_id, chapter_num)
        for cs in states:
            if cs.get("char_name") == char_key:
                notes_raw = cs.get("notes", "")
                if notes_raw:
                    try:
                        return json.loads(notes_raw)
                    except (json.JSONDecodeError, TypeError):
                        pass
        return {}

    def _write_notes(self, chapter_num: int, char_key: str, notes: dict[str, Any]) -> None:
        """将 dict 写入 character_state.notes（更新已有记录或插入新记录）。

        先尝试 UPDATE 已有记录的 notes 字段，如果没有记录则 INSERT。
        """
        notes_json = json.dumps(notes, ensure_ascii=False)
        with self.db.conn() as c:
            cursor = c.execute(
                """UPDATE character_state SET notes=?, updated_at=datetime('now')
                   WHERE novel_id=? AND chapter_num=? AND char_name=?""",
                (notes_json, self.novel_id, chapter_num, char_key),
            )
            if cursor.rowcount == 0:
                c.execute(
                    """INSERT INTO character_state (novel_id, chapter_num, char_name, notes)
                       VALUES (?, ?, ?, ?)""",
                    (self.novel_id, chapter_num, char_key, notes_json),
                )
