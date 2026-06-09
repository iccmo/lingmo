"""故事状态管理器 — 持久化世界观、人物、情节进度"""

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class Character:
    id: str
    name: str
    role: str                      # 主角/反派/配角/导师
    personality: str
    background: str
    current_power_level: str
    secrets: list[str] = field(default_factory=list)
    relationships: dict[str, str] = field(default_factory=dict)  # name -> relation
    status: str = "alive"          # alive / injured / dead / missing
    # Voice tracking — updated each chapter
    voice_avg_sentence_len: float = 0.0
    voice_question_ratio: float = 0.0
    voice_common_words: list[str] = field(default_factory=list)
    voice_sample: str = ""


@dataclass
class World:
    name: str
    era: str                       # 上古/中古/近现代/未来
    geography: str
    power_system: str              # 修炼体系
    factions: list[dict] = field(default_factory=list)  # {name, description, leader}
    rules: list[str] = field(default_factory=list)      # 世界规则


@dataclass
class ChapterMeta:
    number: int
    title: str
    word_count: int
    summary: str                   # 3-5 句剧情摘要
    content: str = ""              # 章节目录正文
    key_events: list[str] = field(default_factory=list)
    revelations: list[str] = field(default_factory=list)  # 新揭示的信息
    narrative_facts: list[str] = field(default_factory=list)  # 后续章节必须记住的稳定事实
    ending_hook: str = ""          # 结尾钩子
    generated_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class Plot:
    premise: str                   # 一句话简介
    main_arc: str                  # 主线剧情
    current_arc: str               # 当前篇章
    arc_chapter_start: int = 1
    next_plot_points: list[str] = field(default_factory=list)
    foreshadowing: list[str] = field(default_factory=list)  # 已埋的伏笔
    resolved_foreshadowing: list[dict] = field(default_factory=list)  # [{content, chapter}]


@dataclass
class StoryState:
    novel_id: str
    title: str
    author: str
    synopsis: str                  # 简介（用于平台发布）
    genre: str
    world: World
    characters: list[Character] = field(default_factory=list)
    plot: Plot | None = None
    chapters: list[ChapterMeta] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)

    # --- 辅助访问 ---
    @property
    def protagonist(self) -> Character | None:
        for c in self.characters:
            if c.role == "主角":
                return c
        return None

    @property
    def total_chapters(self) -> int:
        return max((chapter.number for chapter in self.chapters), default=0)

    @property
    def total_words(self) -> int:
        return sum(ch.word_count for ch in self.chapters)

    @property
    def latest_chapter(self) -> ChapterMeta | None:
        return max(self.chapters, key=lambda chapter: chapter.number, default=None)

    # --- 上下文摘要（注入 prompt） ---
    def recent_context(self, n: int = 5) -> str:
        """最近 n 章摘要，用于控制 prompt 长度"""
        ordered_chapters = sorted(self.chapters, key=lambda chapter: chapter.number)
        recent = ordered_chapters[-n:] if len(ordered_chapters) >= n else ordered_chapters
        parts = []
        for ch in recent:
            parts.append(f"第{ch.number}章《{ch.title}》：{ch.summary}")
            if ch.ending_hook:
                parts.append(f"结尾钩子：{ch.ending_hook}")
        return "\n".join(parts)

    def memory_context(
        self,
        max_chapters: int = 12,
        max_items: int = 18,
        anchor_chapters: int = 4,
        anchor_items: int = 6,
    ) -> str:
        """Long-running continuity facts distilled from previous chapters."""
        if not self.chapters:
            return "暂无长期事实。"

        def as_text_list(value: Any) -> list[str]:
            if value is None:
                return []
            if isinstance(value, str):
                return [item.strip() for item in value.replace("；", "\n").replace(";", "\n").splitlines() if item.strip()]
            if isinstance(value, list):
                return [str(item).strip() for item in value if str(item).strip()]
            return [str(value).strip()] if str(value).strip() else []

        seen: set[str] = set()
        ordered_chapters = sorted(self.chapters, key=lambda chapter: chapter.number)

        def chapter_items(chapters: list[ChapterMeta], limit: int) -> list[str]:
            items: list[str] = []
            for ch in chapters:
                candidates = [
                    *as_text_list(getattr(ch, "narrative_facts", [])),
                    *as_text_list(getattr(ch, "key_events", []))[:2],
                    *as_text_list(getattr(ch, "revelations", []))[:2],
                ]
                if ch.ending_hook:
                    candidates.append(f"第{ch.number}章留下悬念：{ch.ending_hook}")
                for fact in candidates:
                    fact = str(fact).strip()
                    if not fact or fact in seen:
                        continue
                    seen.add(fact)
                    items.append(f"第{ch.number}章：{fact}")
                    if len(items) >= limit:
                        return items
            return items

        recent_chapters = ordered_chapters[-max_chapters:]
        anchor_chapter_list: list[ChapterMeta] = []
        if len(ordered_chapters) > max_chapters + anchor_chapters:
            recent_numbers = {chapter.number for chapter in recent_chapters}
            anchor_chapter_list = [
                chapter
                for chapter in ordered_chapters[:anchor_chapters]
                if chapter.number not in recent_numbers
            ]

        anchor_limit = min(anchor_items, max_items) if anchor_chapter_list else 0
        recent_limit = max(0, max_items - anchor_limit)
        items = [
            *chapter_items(anchor_chapter_list, anchor_limit),
            *chapter_items(recent_chapters, recent_limit),
        ]

        if not items:
            return "暂无长期事实。"
        return "\n".join(f"- {item}" for item in items)

    # --- 角色上下文 ---
    def character_context(self) -> str:
        lines = []
        for ch in self.characters:
            line = (
                f"- {ch.name}（{ch.role}）：{ch.personality}。"
                f"背景：{ch.background}。当前境界：{ch.current_power_level}。"
                f"状态：{ch.status}"
            )
            if ch.secrets:
                line += f"\n  秘密：{'；'.join(ch.secrets)}"
            if ch.voice_sample:
                line += (
                    f"\n  说话风格：平均每句{ch.voice_avg_sentence_len:.0f}字，"
                    f"问句占比{ch.voice_question_ratio:.0%}。"
                    f"惯用词：{'、'.join(ch.voice_common_words[:5]) if ch.voice_common_words else '无'}。"
                    f"代表台词：「{ch.voice_sample[:80]}」"
                )
            lines.append(line)
        return "\n".join(lines)

    # --- 序列化 ---
    def to_dict(self) -> dict:
        """转为可 JSON 序列化的 dict"""
        d: dict[str, Any] = {}
        d["novel_id"] = self.novel_id
        d["title"] = self.title
        d["author"] = self.author
        d["synopsis"] = self.synopsis
        d["genre"] = self.genre
        d["tags"] = self.tags
        d["world"] = asdict(self.world)
        d["characters"] = [asdict(c) for c in self.characters]
        d["plot"] = asdict(self.plot) if self.plot else None
        d["chapters"] = [asdict(ch) for ch in self.chapters]
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "StoryState":
        world = World(**d["world"])
        characters = [Character(**c) for c in d.get("characters", [])]
        plot = Plot(**d["plot"]) if d.get("plot") else None
        chapters = [ChapterMeta(**ch) for ch in d.get("chapters", [])]
        return cls(
            novel_id=d["novel_id"],
            title=d["title"],
            author=d["author"],
            synopsis=d["synopsis"],
            genre=d["genre"],
            world=world,
            characters=characters,
            plot=plot,
            chapters=chapters,
            tags=d.get("tags", []),
        )


# ==================== 持久化 ====================

class StateManager:
    """管理故事状态的读写"""

    def __init__(self, data_dir: str):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def novel_path(self, novel_id: str) -> Path:
        return self.data_dir / f"{novel_id}.json"

    def list_novels(self) -> list[str]:
        """列出所有已创建的小说 ID"""
        ids = []
        for f in self.data_dir.glob("*.json"):
            ids.append(f.stem)
        return sorted(ids)

    def load(self, novel_id: str) -> StoryState | None:
        path = self.novel_path(novel_id)
        if not path.exists():
            return None
        with open(path, encoding="utf-8") as f:
            return StoryState.from_dict(json.load(f))

    def save(self, state: StoryState):
        path = self.novel_path(state.novel_id)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(state.to_dict(), f, ensure_ascii=False, indent=2)

    def add_chapter(self, state: StoryState, chapter: ChapterMeta):
        state.chapters.append(chapter)
        self.save(state)

    def delete_novel(self, novel_id: str):
        path = self.novel_path(novel_id)
        if path.exists():
            path.unlink()
