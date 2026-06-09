"""Background services for multi-step novel orchestration."""

from __future__ import annotations

from novel_writer.routers.deps import get_db, get_gen_state
from novel_writer.routers.novel.chapter_metadata import chapter_content_rejection, update_chapter_content
from novel_writer.routers.novel.generation_support_service import build_creation_brief
from novel_writer.routers.novel.revision_service import _generator_for, _load_state


def _set_status(novel_id: str, status: str, message: str = "", progress: int = 0, overall: float = 0) -> None:
    get_gen_state().set_status(novel_id, status, message, progress, overall)


def _existing_chapter_content(db, state, novel_id: str, chapter_num: int) -> str:
    try:
        chapter = db.get_chapter(novel_id, chapter_num)
        if chapter:
            return chapter.get("content", "")
    except Exception:
        pass
    for chapter in getattr(state, "chapters", []) or []:
        if getattr(chapter, "number", None) == chapter_num:
            return getattr(chapter, "content", "") or ""
    return ""


def _rewrite_is_saveable(db, state, novel_id: str, chapter_num: int, content: str, operation: str) -> bool:
    rejection = chapter_content_rejection(_existing_chapter_content(db, state, novel_id, chapter_num), content)
    if not rejection:
        return True
    try:
        db.log(
            novel_id,
            "pipeline.rewrite_rejected",
            {"chapter": chapter_num, "operation": operation, "reason": rejection},
        )
    except Exception:
        pass
    return False


def run_pipeline(novel_id: str) -> None:
    """Background: autonomous publication pipeline."""
    db = get_db()
    gen = _generator_for(novel_id)
    style = None
    try:
        from novel_writer.generator import StyleProfile

        style_data = db.get_style_profile(novel_id)
        if style_data:
            style = StyleProfile(**{
                key: value
                for key, value in style_data.items()
                if key in StyleProfile.__dataclass_fields__
            })
    except Exception:
        pass

    try:
        _set_status(novel_id, "generating", "Phase 1/3: 生成全部章节…")
        state = _load_state(novel_id)
        if not state:
            return
        novel = db.get_novel(novel_id)
        outline_items = [
            {"number": chapter["number"], "title": chapter["title"], "summary": chapter["summary"]}
            for chapter in novel.get("chapters", [])
            if chapter.get("word_count", 0) == 0
        ]
        remaining = len(outline_items) or 10
        author_input = build_creation_brief(db, novel_id)
        gen.generate_chapters(state, n=min(remaining, 10), style=style, author_input=author_input)
        db.log(novel_id, "pipeline.phase1", {"chapters": state.total_chapters})

        _set_status(novel_id, "revising", "Phase 2/3: 基于结局回修前3章…")
        if state.total_chapters >= 5:
            revised = gen.revise_opening(state, target_chapters=3, style=style)
            saved_revisions = 0
            for chapter in revised:
                if not _rewrite_is_saveable(db, state, novel_id, chapter.number, chapter.content, "revise_opening"):
                    continue
                update_chapter_content(db, novel_id, chapter.number, chapter.content, refresh_story_bible=True)
                saved_revisions += 1
            db.log(novel_id, "pipeline.phase2", {"revised": saved_revisions, "rejected": len(revised) - saved_revisions})

        _set_status(novel_id, "generating", "Phase 3/3: 经典模式重写弱章…")
        novel = db.get_novel(novel_id)
        generated_chapters = [
            chapter for chapter in novel.get("chapters", []) if chapter.get("word_count", 0) > 0
        ]
        if generated_chapters:
            scores = [
                (chapter["number"], chapter.get("quality_score", 0))
                for chapter in generated_chapters
            ]
            scores.sort(key=lambda item: item[1])
            bottom_20 = [
                chapter_num
                for chapter_num, quality in scores[:max(1, len(scores) // 5)]
                if quality < 0.75
            ]
            for chapter_num in bottom_20:
                _set_status(novel_id, "generating", f"经典重写第{chapter_num}章…")
                new_chapter = None
                state2 = _load_state(novel_id)
                if state2:
                    new_chapter = gen.generate_chapter_classic(state2, style=style, author_input=author_input)
                if new_chapter:
                    if not _rewrite_is_saveable(db, state2, novel_id, chapter_num, new_chapter.content, "classic_rewrite"):
                        continue
                    update_chapter_content(db, novel_id, chapter_num, new_chapter.content, refresh_story_bible=True)
                    if style:
                        style.regeneration_log.append({
                            "chapter": chapter_num,
                            "reason": "pipeline_weak",
                        })
                    db.log(novel_id, "pipeline.phase3", {"regenerated": chapter_num})

        _set_status(novel_id, "complete", "管线完成！")
    except Exception as exc:
        _set_status(novel_id, "error", str(exc)[:200])
