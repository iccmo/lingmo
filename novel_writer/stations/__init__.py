"""
灵墨 Station 系统 — 4 模块架构

模块子目录：
  - novel/  : 小说写作工位（生成、质量、约束）
  - script/ : 剧本工位（AI 导演、视觉圣经、Prompt）
  - drama/  : 短剧工位（画面、配音、合成）

共享基类保留在本目录：base.py, llm_mixin.py

向后兼容：所有工位仍可从 stations.xxx 直接导入。
"""

# ── 共享基类 ──
from .base import BaseStation as BaseStation
from .base import StationContext as StationContext
from .llm_mixin import LLMMixin as LLMMixin

# ── 小说模块工位（向后兼容 re-export）──
from .novel.bible_extractor import BibleExtractor as BibleExtractor
from .novel.chapter_writer import ChapterWriter as ChapterWriter
from .novel.consistency_checker import ConsistencyChecker as ConsistencyChecker
from .novel.constraint_builder import ConstraintBuilder as ConstraintBuilder
from .novel.deslop_filter import DeslopFilter as DeslopFilter
from .novel.editor_review import EditorReview as EditorReview
from .novel.foreshadowing_resolver import ForeshadowingResolver as ForeshadowingResolver

# ── 剧本模块工位（向后兼容 re-export）──
from .script.ai_director import AIDirector as AIDirector
from .script.prompt_generator import PromptGenerator as PromptGenerator
from .script.visual_bible import VisualBible as VisualBible

# ── 短剧模块工位（向后兼容 re-export）──
from .drama.compositor import Compositor as Compositor
from .drama.image_generator import ImageGenerator as ImageGenerator
from .drama.music_engine import MusicEngine as MusicEngine
from .drama.voice_engine import VoiceEngine as VoiceEngine
