"""Background services for draft direction and draft expansion workflows."""

from __future__ import annotations

import json

from novel_writer.routers.deps import get_db
from novel_writer.routers.novel.chapter_metadata import chapter_content_rejection
from novel_writer.routers.novel.generation_support_service import build_creation_brief
from novel_writer.routers.novel.generation_service import (
    _sync_new_foreshadowing,
    _sync_next_plot_points,
    _sync_resolved_foreshadowing,
)
from novel_writer.routers.novel.revision_service import _load_state
from novel_writer.routers.novel.story_bible_service import extract_story_bible, run_consistency_check
from novel_writer.story_state import ChapterMeta


def _get_provider(novel_id: str | None = None) -> dict:
    db = get_db()
    provider_id = "deepseek"
    if novel_id:
        novel = db.get_novel(novel_id)
        if novel:
            provider_id = novel.get("provider_id", "deepseek")
    provider = db.get_provider(provider_id)
    if not provider or not provider.get("api_key"):
        for candidate in db.list_providers():
            if candidate.get("api_key"):
                provider = db.get_provider(candidate["id"])
                break
    return provider or {
        "id": "deepseek",
        "base_url": "https://api.deepseek.com",
        "api_key": "",
        "models": ["deepseek-v4-pro"],
    }


def _config_for(novel_id: str):
    from novel_writer.config import Config

    provider = _get_provider(novel_id)
    models = provider.get("models", ["deepseek-v4-pro"])
    model = models[0] if isinstance(models, list) and models else "deepseek-v4-pro"
    return Config(
        openai_api_key=provider.get("api_key", ""),
        openai_base_url=provider.get("base_url", ""),
        model=model,
    )


def generator_for(novel_id: str):
    from novel_writer.generator import Generator

    return Generator(_config_for(novel_id))


def run_draft(novel_id: str, author_input: str) -> None:
    """Background: generate draft directions."""
    db = get_db()
    try:
        state = _load_state(novel_id)
        if not state:
            return
        gen = generator_for(novel_id)
        creation_brief = build_creation_brief(db, novel_id)
        prompt_input = creation_brief + ("\n\n作者输入：" + author_input if author_input else "")
        gen.draft_directions(state, prompt_input)
        db.log(novel_id, "draft.generated", {"input": author_input[:100]})
    except Exception as exc:
        db.log(novel_id, "draft.failed", {"error": str(exc)})


def run_expand(
    novel_id: str,
    chosen_id: str,
    direction: str,
    preview: str,
    hook: str,
    edits: str,
) -> None:
    """Background: expand a selected draft into a full chapter."""
    db = get_db()
    try:
        from novel_writer.generator import DraftOption

        cfg = _config_for(novel_id)
        state = _load_state(novel_id)
        if not state:
            return
        gen = generator_for(novel_id)
        author_input = build_creation_brief(db, novel_id)
        draft = DraftOption(id=chosen_id, title="", direction=direction, preview=preview, hook=hook)
        title, body = gen.expand(state, draft, edits, author_input=author_input)

        body_de_ai, de_ai_changes = gen.de_ai(body)
        if de_ai_changes > 0:
            print(f"[EXPAND] de-AI: {de_ai_changes} changes")

        try:
            quality = gen.score_quality(body_de_ai or body, state)
        except Exception:
            quality = {"overall": 0, "grade": "?", "issues": []}

        final_body = body_de_ai or body
        rejection = chapter_content_rejection("", final_body)
        if rejection:
            raise ValueError(f"扩写结果不是有效章节正文：{rejection}")
        word_count = len(final_body)
        novel = db.get_novel(novel_id)
        chapter_number = db.get_next_chapter_number(novel_id) if hasattr(db, "get_next_chapter_number") else (
            max([chapter["number"] for chapter in novel.get("chapters", []) if chapter.get("word_count", 0) > 0], default=0) + 1
        )
        meta = {
            "key_events": gen._normalize_text_list(f"{direction}\n{preview}", limit=4),
            "revelations": [],
            "ending_hook": hook.strip(),
        }
        narrative_facts = gen._extract_narrative_facts(meta, final_body)
        summary = final_body[:200]
        try:
            final_quality = gen.judge_quality(final_body, state)
        except Exception:
            final_quality = {"overall": quality.get("overall", 0)}
        db.add_chapter(
            novel_id=novel_id,
            number=chapter_number,
            title=title,
            word_count=word_count,
            summary=summary,
            content=final_body,
            ending_hook=meta["ending_hook"],
            key_events=json.dumps(meta["key_events"], ensure_ascii=False),
            revelations=json.dumps(meta["revelations"], ensure_ascii=False),
            narrative_facts=json.dumps(narrative_facts, ensure_ascii=False),
            quality_score=final_quality.get("overall", 0),
            model_used=cfg.model,
        )
        state.chapters.append(ChapterMeta(
            number=chapter_number,
            title=title,
            word_count=word_count,
            summary=summary,
            content=final_body,
            key_events=meta["key_events"],
            revelations=meta["revelations"],
            narrative_facts=narrative_facts,
            ending_hook=meta["ending_hook"],
        ))
        try:
            _sync_resolved_foreshadowing(db, novel_id, state, chapter_number)
            _sync_new_foreshadowing(db, novel_id, state, chapter_number)
            _sync_next_plot_points(db, novel_id, state)
            extract_story_bible(novel_id, chapter_number, final_body, title)
            run_consistency_check(novel_id, chapter_number)
        except Exception as sync_exc:
            db.log(novel_id, "story_state.sync_failed", {"error": str(sync_exc)[:200]})
        db.log(
            novel_id,
            "chapter.expanded",
            {
                "chapter": chapter_number,
                "title": title,
                "quality": quality.get("overall", 0),
                "grade": quality.get("grade", "?"),
            },
        )
        de_ai_info = f" de-AI:{de_ai_changes}" if de_ai_changes > 0 else ""
        print(f"[EXPAND] {novel_id} ch{chapter_number} — {word_count}w — Q:{quality.get('grade', '?')}({quality.get('overall', 0)}){de_ai_info}")
    except Exception as exc:
        db.log(novel_id, "expand.failed", {"error": str(exc)})
