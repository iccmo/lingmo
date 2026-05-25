"""
灵墨 Station 系统 — 每个工位独立模块，由 Brain Agent 按需调度。

每个 Station 实现标准接口：
  def run(ctx: dict) -> dict:
      ctx 包含 novel_id, chapter_num, content, quality, bible 等
      返回 {status, data, next_action}
"""

from .constraint_builder import ConstraintBuilder
from .consistency_checker import ConsistencyChecker
from .bible_extractor import BibleExtractor
from .editor_review import EditorReview
from .deslop_filter import DeslopFilter
from .chapter_writer import ChapterWriter
