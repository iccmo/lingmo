"""Helpers for keeping edited chapter text and continuity metadata in sync."""

from __future__ import annotations

import json
import re

from novel_writer.routers.novel.story_bible_service import extract_story_bible, run_consistency_check


def safe_json_list(value) -> list:
    if not value:
        return []
    try:
        parsed = json.loads(value) if isinstance(value, str) else value
        if isinstance(parsed, list):
            return parsed
    except (json.JSONDecodeError, TypeError):
        pass
    if isinstance(value, str):
        return [item.strip() for item in value.replace("；", "\n").replace(";", "\n").splitlines() if item.strip()]
    return []


def chapter_content_rejection(old_content: str, new_content: str) -> str:
    """Return a user-facing reason when saving would likely destroy chapter prose."""
    if not isinstance(new_content, str):
        return "content must be text"
    if not new_content.strip():
        return "content must not be empty"

    old_text = (old_content or "").strip()
    new_text = new_content.strip()
    if old_text and len(old_text) >= 80 and len(new_text) < max(20, int(len(old_text) * 0.25)):
        return "content is too short compared with existing chapter"

    opening = new_text[:180].lstrip()
    if re.search(
        r"^(好的|当然|可以|以下是|下面是|这是|我已|已根据|根据你的|修改说明|修订说明|改动说明|说明[:：])",
        opening,
    ):
        return "content looks like an explanation, not chapter prose"
    if re.search(r"(修改如下|修订如下|改动如下|以下为修订|以下为修改)", opening):
        return "content looks like an explanation, not chapter prose"
    if "```" in new_text[:400] or re.search(r"^#{1,3}\s*(修改|修订|说明)", opening, re.M):
        return "content uses non-prose formatting"
    if re.search(
        r"^(分析报告|评估报告|质量报告|诊断报告|改写计划|修订计划|优化计划|章节大纲|故事大纲|提纲|大纲|创作思路|写作思路|改写思路|问题分析|建议[:：])",
        opening,
    ):
        return "content looks like a report or outline, not chapter prose"
    if re.search(r"以下为.*(分析|报告|计划|提纲|大纲)|(?:问题|建议|目标|修改点|优化点)[:：]", opening):
        return "content looks like a report or outline, not chapter prose"
    early_lines = [line.strip() for line in new_text[:800].splitlines() if line.strip()]
    list_like = sum(1 for line in early_lines[:8] if re.match(r"^([-*•]|\d+[.、])\s*[^。！？]{1,30}[:：]", line))
    if list_like >= 3:
        return "content looks like an outline list, not chapter prose"

    return ""


def metadata_for_content(chapter: dict, content: str) -> dict:
    from novel_writer.generator import Generator
    from novel_writer.story_state import ChapterMeta

    chapter_meta = ChapterMeta(
        number=chapter.get("number", 0),
        title=chapter.get("title", ""),
        word_count=len(content),
        summary=chapter.get("summary", ""),
        content=chapter.get("content", ""),
        key_events=safe_json_list(chapter.get("key_events")),
        revelations=safe_json_list(chapter.get("revelations")),
        narrative_facts=safe_json_list(chapter.get("narrative_facts")),
        ending_hook=chapter.get("ending_hook", ""),
    )
    generator = Generator.__new__(Generator)
    generator.refresh_chapter_content(chapter_meta, content)
    return {
        "content": chapter_meta.content,
        "word_count": chapter_meta.word_count,
        "summary": chapter_meta.summary,
        "narrative_facts": json.dumps(chapter_meta.narrative_facts, ensure_ascii=False),
    }


def update_chapter_content(
    db,
    novel_id: str,
    chapter_num: int,
    content: str,
    refresh_story_bible: bool = False,
    **extra,
) -> None:
    chapter = db.get_chapter(novel_id, chapter_num) or {"number": chapter_num}
    updates = metadata_for_content(chapter, content)
    updates.update(extra)
    if "quality_score" not in updates and chapter.get("content") != updates["content"]:
        updates["quality_score"] = 0
    db.update_chapter(novel_id, chapter_num, **updates)
    try:
        if hasattr(db, "save_chapter_summary"):
            db.save_chapter_summary(novel_id, chapter_num, updates["summary"])
    except Exception as exc:
        try:
            db.log(novel_id, "chapter_summary.sync_failed", {"chapter": chapter_num, "error": str(exc)[:200]})
        except Exception:
            pass
    if not refresh_story_bible:
        return
    try:
        title = chapter.get("title", "")
        extract_story_bible(novel_id, chapter_num, updates["content"], title)
        run_consistency_check(novel_id, chapter_num)
    except Exception as exc:
        try:
            db.log(novel_id, "story_state.sync_failed", {"error": str(exc)[:200]})
        except Exception:
            pass
