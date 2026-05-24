"""故事状态管理器 — 持久化世界观、人物、情节进度"""

import json
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional


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
    plot: Optional[Plot] = None
    chapters: list[ChapterMeta] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)

    # --- 辅助访问 ---
    @property
    def protagonist(self) -> Optional[Character]:
        for c in self.characters:
            if c.role == "主角":
                return c
        return None

    @property
    def total_chapters(self) -> int:
        return len(self.chapters)

    @property
    def total_words(self) -> int:
        return sum(ch.word_count for ch in self.chapters)

    @property
    def latest_chapter(self) -> Optional[ChapterMeta]:
        return self.chapters[-1] if self.chapters else None

    # --- 上下文摘要（注入 prompt） ---
    def recent_context(self, n: int = 5) -> str:
        """最近 n 章摘要，用于控制 prompt 长度"""
        recent = self.chapters[-n:] if len(self.chapters) >= n else self.chapters
        parts = []
        for ch in recent:
            parts.append(f"第{ch.number}章《{ch.title}》：{ch.summary}")
            if ch.ending_hook:
                parts.append(f"结尾钩子：{ch.ending_hook}")
        return "\n".join(parts)

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
        d = {}
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

    def load(self, novel_id: str) -> Optional[StoryState]:
        path = self.novel_path(novel_id)
        if not path.exists():
            return None
        with open(path, "r", encoding="utf-8") as f:
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
