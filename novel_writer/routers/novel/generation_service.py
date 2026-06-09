"""Background services for generation variants and long-run generation tests."""

from __future__ import annotations

import json
import os
import re
import sys
import threading
import time
import traceback
import uuid
from typing import Any

from novel_writer.routers.deps import get_db, get_gen_state
from novel_writer.routers.novel.chapter_metadata import chapter_content_rejection
from novel_writer.routers.novel.generation_support_service import build_creation_brief
from novel_writer.routers.novel.revision_service import _load_state
from novel_writer.routers.novel.story_bible_service import extract_story_bible, run_consistency_check

BATCH_MIN_CHAPTER_WORDS = 1000
ORPHAN_QUOTE_RE = r"\n\s*[」』”\"]"


def _set_status(novel_id: str, status: str, message: str = "", progress: int = 0, overall: float = 0) -> None:
    get_gen_state().set_status(novel_id, status, message, progress, overall)


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


def _generator_and_model(novel_id: str):
    from novel_writer.config import Config
    from novel_writer.generator import Generator

    provider = _get_provider(novel_id)
    models = provider.get("models", ["deepseek-v4-pro"])
    model = "deepseek-v4-pro" if "deepseek-v4-pro" in str(models) else models[0]
    cfg = Config(
        openai_api_key=provider.get("api_key", ""),
        openai_base_url=provider.get("base_url", ""),
        model=model,
    )
    return Generator(cfg), cfg.model


def _style_for(novel_id: str):
    db = get_db()
    try:
        from novel_writer.generator import StyleProfile

        style_data = db.get_style_profile(novel_id)
        if style_data:
            return StyleProfile(**{
                key: value
                for key, value in style_data.items()
                if key in StyleProfile.__dataclass_fields__
            })
    except Exception:
        return None
    return None


_job_lock = threading.Lock()


def _job_queue() -> dict:
    return get_gen_state()._job_queue


def get_queue_status(novel_id: str, active_only: bool = False) -> dict | None:
    """Return the latest queue job for a novel, including recent terminal states."""
    visible_statuses = {"queued", "running"} if active_only else {"queued", "running", "done", "error"}
    with _job_lock:
        for job in reversed(list(_job_queue().values())):
            if job["novel_id"] == novel_id and job["status"] in visible_statuses:
                return {
                    "job_id": job["job_id"],
                    "status": job["status"],
                    "progress": job["progress"],
                    "last_error": job.get("last_error"),
                }
    return None


def start_batch_job(novel_id: str, count: int, quality_threshold: float, model_override: str | None = None) -> dict:
    """Create and start a queued batch-generation job."""
    db = get_db()
    novel = db.get_novel(novel_id)
    job_id = uuid.uuid4().hex[:12]
    next_chapter = db.get_next_chapter_number(novel_id) if hasattr(db, "get_next_chapter_number") else (
        max([chapter.get("number", 0) for chapter in novel.get("chapters", []) if chapter.get("word_count", 0) > 0], default=0) + 1
    )
    job = {
        "job_id": job_id,
        "novel_id": novel_id,
        "status": "queued",
        "progress": {"current": 0, "total": count},
        "count": count,
        "quality_threshold": quality_threshold,
        "model_override": model_override,
        "last_error": None,
    }
    with _job_lock:
        _job_queue()[job_id] = job

    thread = threading.Thread(target=_run_queue_job, args=(job,), daemon=True)
    thread.start()
    return {
        "job_id": job_id,
        "status": "queued",
        "count": count,
        "next_chapter": next_chapter,
    }


def _run_queue_job(job: dict) -> None:
    """Run a batch generation job in a background thread, updating queue status."""
    novel_id = job["novel_id"]
    count = job["count"]
    quality_threshold = job.get("quality_threshold", 0.8)
    model_override = job.get("model_override") or None
    try:
        with _job_lock:
            job["status"] = "running"
        result = run_batch_generation(novel_id, count, quality_threshold, model_override) or {}
        with _job_lock:
            if result.get("generated", 0) <= 0:
                job["status"] = "error"
                job["last_error"] = result.get("message") or "批量生成未产出有效章节"
            else:
                job["status"] = "done"
                if result.get("failed", 0) > 0:
                    job["last_error"] = result.get("message")
            job["progress"]["current"] = job["progress"]["total"]
    except Exception as exc:
        with _job_lock:
            job["status"] = "error"
            job["last_error"] = str(exc)[:500]
    finally:
        def _cleanup_job() -> None:
            time.sleep(300)
            with _job_lock:
                _job_queue().pop(job.get("job_id", ""), None)

        threading.Thread(target=_cleanup_job, daemon=True).start()


def _update_job_progress(novel_id: str, current: int, total: int, error: str = "") -> None:
    """Update the queue job progress for a novel."""
    with _job_lock:
        for job in _job_queue().values():
            if job["novel_id"] == novel_id and job["status"] in ("queued", "running"):
                job["progress"]["current"] = current
                job["progress"]["total"] = total
                if error:
                    job["last_error"] = error
                break


def _restore_story_state(state, snapshot: dict) -> None:
    """Restore StoryState data while preserving the caller's object reference."""
    restored = type(state).from_dict(snapshot)
    state.__dict__.clear()
    state.__dict__.update(restored.__dict__)


def _retarget_generated_chapter(state, chapter, target_num: int) -> int:
    """Make generated chapter metadata and in-memory plot updates match the persisted slot."""
    original_num = int(getattr(chapter, "number", target_num) or target_num)
    chapter.number = target_num
    plot = getattr(state, "plot", None)
    resolved_items = getattr(plot, "resolved_foreshadowing", None) if plot else None
    if isinstance(resolved_items, list) and original_num != target_num:
        for item in resolved_items:
            if isinstance(item, dict) and int(item.get("chapter") or 0) == original_num:
                item["chapter"] = target_num
    return original_num


def _batch_generate_with_retries(
    gen,
    state,
    q_threshold: float,
    rag_context: Any,
    outline: list[dict],
    style,
    author_input: str = "",
) -> tuple[Any, dict, str, int]:
    """Generate one chapter slot without letting rejected retry candidates advance state."""
    slot_state = state.to_dict()
    chapter, quality = gen.batch_generate(
        state,
        n=2,
        rag_context=rag_context,
        outline=outline,
        style=style,
        author_input=author_input,
    )
    body = chapter.content or chapter.summary
    rejection = chapter_content_rejection("", body)

    retries = 0
    max_retries = 3 if q_threshold >= 0.8 else 2
    while (rejection or quality["overall"] < q_threshold) and retries < max_retries:
        retries += 1
        _restore_story_state(state, slot_state)
        chapter, quality = gen.batch_generate(
            state,
            n=1,
            rag_context=rag_context,
            outline=outline,
            style=style,
            author_input=author_input,
        )
        body = chapter.content or chapter.summary
        rejection = chapter_content_rejection("", body)
        if rejection:
            quality = {"overall": 0, "grade": "D", "issues": [rejection]}
            continue
        quality = gen.score_quality(body, state, style=style)
        rejection = chapter_content_rejection("", body)

    if not body or rejection:
        _restore_story_state(state, slot_state)

    return chapter, quality, body, retries


def _batch_final_rejection(chapter, final_quality: dict, q_threshold: float) -> str:
    """Return a rejection reason for final batch text before it can be saved."""
    content = str(getattr(chapter, "content", "") or "")
    orphan_quotes = len(re.findall(ORPHAN_QUOTE_RE, content))
    if orphan_quotes:
        return f"残留{orphan_quotes}个孤儿引号"
    word_count = int(getattr(chapter, "word_count", 0) or 0)
    if word_count < BATCH_MIN_CHAPTER_WORDS:
        return f"字数不足{BATCH_MIN_CHAPTER_WORDS}字（当前{word_count}字）"
    score = float((final_quality or {}).get("overall", 0) or 0)
    if score < q_threshold:
        return f"质量分 {score:.2f} 低于门槛 {q_threshold:.2f}"
    return ""


def _sync_resolved_foreshadowing(
    db,
    novel_id: str,
    state,
    chapter_num: int,
    source_chapter_num: int | None = None,
) -> None:
    """Persist in-memory resolved foreshadowing markers back to the story bible."""
    plot = getattr(state, "plot", None)
    if not plot or not getattr(plot, "resolved_foreshadowing", None):
        return
    if not hasattr(db, "get_all_foreshadowing") or not hasattr(db, "resolve_foreshadowing"):
        return

    threads = [
        thread
        for thread in db.get_all_foreshadowing(novel_id)
        if thread.get("status", "active") in ("active", "overdue")
    ]
    accepted_chapters = {int(chapter_num)}
    if source_chapter_num is not None:
        accepted_chapters.add(int(source_chapter_num))
    for resolved in plot.resolved_foreshadowing:
        if int(resolved.get("chapter") or 0) not in accepted_chapters:
            continue
        content = str(resolved.get("content") or "").strip()
        if not content:
            continue
        matched = next(
            (
                thread
                for thread in threads
                if str(thread.get("description") or "").strip() == content
            ),
            None,
        )
        if not matched:
            content_chars = set(content.replace(" ", ""))
            best_score = 0.0
            for thread in threads:
                description = str(thread.get("description") or "").strip()
                description_chars = set(description.replace(" ", ""))
                if not content_chars or not description_chars:
                    continue
                score = len(content_chars & description_chars) / len(content_chars | description_chars)
                if score > best_score:
                    best_score = score
                    matched = thread
            if best_score < 0.35:
                matched = None
        if not matched:
            continue
        db.resolve_foreshadowing(matched["id"], chapter_num, content)
        threads = [thread for thread in threads if thread.get("id") != matched.get("id")]


def _text_similarity(left: str, right: str) -> float:
    left_chars = set(left.replace(" ", ""))
    right_chars = set(right.replace(" ", ""))
    if not left_chars or not right_chars:
        return 0.0
    return len(left_chars & right_chars) / len(left_chars | right_chars)


def _sync_new_foreshadowing(db, novel_id: str, state, chapter_num: int) -> None:
    """Persist newly introduced in-memory foreshadowing threads."""
    plot = getattr(state, "plot", None)
    foreshadowing = getattr(plot, "foreshadowing", None) if plot else None
    if not foreshadowing:
        return
    if not hasattr(db, "save_foreshadowing"):
        return

    existing = []
    if hasattr(db, "get_all_foreshadowing"):
        existing = [
            str(thread.get("description") or "").strip()
            for thread in db.get_all_foreshadowing(novel_id)
            if str(thread.get("description") or "").strip()
        ]

    seen = set(existing)
    for item in foreshadowing:
        content = str(item or "").strip()
        if not content:
            continue
        if content in seen:
            continue
        if any(_text_similarity(content, old) >= 0.6 for old in existing):
            continue
        db.save_foreshadowing(novel_id, chapter_num, content)
        existing.append(content)
        seen.add(content)


def _sync_next_plot_points(db, novel_id: str, state) -> None:
    """Persist generated next-step plot targets so later generation resumes with them."""
    plot = getattr(state, "plot", None)
    points = getattr(plot, "next_plot_points", None) if plot else None
    if not points:
        return

    desired = []
    seen_desired = set()
    for point in points:
        content = str(point or "").strip()
        if not content or content in seen_desired:
            continue
        desired.append(content)
        seen_desired.add(content)

    novel = db.get_novel(novel_id) or {}
    existing = {
        str(point.get("content") or "").strip()
        for point in novel.get("plot_points", [])
        if point.get("type", "plot") == "plot" and not point.get("is_resolved")
    }
    sort_order = max(
        [
            int(point.get("sort_order") or 0)
            for point in novel.get("plot_points", [])
            if point.get("type", "plot") == "plot"
        ]
        or [0]
    )
    with db.conn() as conn:
        for old in existing - seen_desired:
            conn.execute(
                """UPDATE plot_points
                   SET is_resolved=1, resolved_at=datetime('now')
                   WHERE novel_id=? AND type='plot' AND is_resolved=0 AND content=?""",
                (novel_id, old),
            )
        for content in desired:
            if content in existing:
                continue
            sort_order += 1
            conn.execute(
                "INSERT INTO plot_points (novel_id,type,content,is_resolved,sort_order) VALUES (?,?,?,?,?)",
                (novel_id, "plot", content, 0, sort_order),
            )
            existing.add(content)


def run_batch_generation(novel_id: str, count: int, quality_threshold: float = 0.8, model_override: str | None = None) -> dict:
    """Background: queue-compatible batch generation."""
    try:
        db = get_db()
        from novel_writer.config import Config
        from novel_writer.generator import Generator

        provider = _get_provider(novel_id)
        models = provider.get("models", ["deepseek-v4-pro"])
        if isinstance(models, str):
            import json as _json
            try: models = _json.loads(models)
            except Exception: models = ["deepseek-v4-pro"]
        model = model_override or (models[0] if models else "deepseek-v4-pro")
        cfg = Config(
            openai_api_key=provider.get("api_key", ""),
            openai_base_url=provider.get("base_url", ""),
            model=model,
        )
        gen = Generator(cfg)
        state = _load_state(novel_id)
        if isinstance(state, str):
            state = None  # defensive: _load_state returned error string
        if not state:
            return {
                "requested": count,
                "generated": 0,
                "failed": count,
                "failed_slots": [],
                "message": "批量生成失败：无法加载小说状态",
            }

        q_threshold = float(quality_threshold)
        outline = _build_batch_targets(db, novel_id, count)
        if not outline or not isinstance(outline, list):
            existing_chapters = [c for c in state.chapters] if state else []
            max_num = max([c.number for c in existing_chapters if c.word_count > 0], default=0)
            outline = [{"number": max_num + 1 + i, "title": f"第{max_num + 1 + i}章", "summary": ""} for i in range(count)]

        style = _style_for(novel_id)
        if isinstance(style, str):
            style = None  # defensive: DB returned malformed style
        author_input = build_creation_brief(db, novel_id)
        if isinstance(author_input, str):
            author_input = ""  # defensive
        _ensure_smart_context(novel_id, gen, state)

        rag_context: Any = gen.retrieve_relevant_context(
            query=state.plot.current_arc or state.plot.premise,
            novel_id=novel_id,
            top_k=5,
        )

        existing_summaries = db.get_chapter_summaries(novel_id)
        # Build summary text for injection into prompt (not used directly as rag_context)
        summary_context = ""
        if existing_summaries:
            summary_parts = ["【前情摘要】"]
            for s in existing_summaries:
                summary_parts.append(f"第{s['chapter_num']}章: {s['summary_text']}")
            if isinstance(rag_context, list) and rag_context:
                for r in rag_context:
                    if isinstance(r, dict):
                        summary_parts.append(f"- 第{r.get('chapter_number','?')}章「{r.get('title','')}」: {str(r.get('chunk_text',''))[:200]}")
            summary_context = "\n".join(summary_parts)

        generated_count = 0
        failed_slots: list[int] = []
        failed_reasons: dict[int, str] = {}

        for index, outline_item in enumerate(outline):
            if not isinstance(outline_item, dict):
                continue
            existing_chapters = [c for c in state.chapters] if state else []
            default_num = max([c.number for c in existing_chapters if c.word_count > 0], default=0) + 1 + index
            target_num = outline_item.get("number", default_num)
            progress_pct = ((index + 1) * 100) // count
            _set_status(novel_id, "generating", f"正在生成第{target_num}章...", progress_pct)
            _update_job_progress(novel_id, index, count)
            getattr(gen, 'reset_cumulative_cost', lambda: None)()

            chapter, quality, body, retries = _batch_generate_with_retries(
                gen,
                state,
                q_threshold=q_threshold,
                rag_context=summary_context or rag_context,
                outline=outline,
                style=style,
                author_input=author_input,
            )

            if not body:
                print(f"[BATCH ERROR] {novel_id} ch{target_num}: generate returned empty content (tried {retries + 1} times), skipping slot {target_num}")
                db.log(novel_id, "chapter.empty_skipped", {"target_num": target_num, "retries": retries})
                failed_slots.append(target_num)
                failed_reasons[target_num] = "内容为空"
                _set_status(novel_id, "error", f"第{target_num}章生成失败（内容为空），已跳过", 0)
                _update_job_progress(novel_id, index + 1, count, f"第{target_num}章生成失败（内容为空）")
                continue

            body = gen._self_edit(body, state, style)
            cleaned_body, de_ai_changes = gen.de_ai(body)
            if de_ai_changes > 0:
                print(f"[BATCH] {novel_id} de-AI: {de_ai_changes} changes")

            final_quality = gen.judge_quality(cleaned_body or body, state, style)
            if final_quality.get("method") == "llm":
                detail = final_quality.get("judge_detail", {})
                print(f"[BATCH] {novel_id} ch{chapter.number} judge: {final_quality['grade']}({final_quality['overall']}) — {detail.get('biggest_issue', '')}")

            save_body = cleaned_body or body
            save_body, save_deai_changes = gen.de_ai(save_body)
            if save_deai_changes > de_ai_changes:
                de_ai_changes = save_deai_changes
            if save_body != (cleaned_body or body):
                final_quality = gen.judge_quality(save_body, state, style)
            source_chapter_num = _retarget_generated_chapter(state, chapter, target_num)
            gen.refresh_chapter_content(chapter, save_body)
            rejection = chapter_content_rejection("", chapter.content)
            if rejection:
                print(f"[BATCH ERROR] {novel_id} ch{target_num}: invalid chapter content ({rejection}), skipping slot {target_num}")
                db.log(novel_id, "chapter.invalid_skipped", {"target_num": target_num, "reason": rejection})
                failed_slots.append(target_num)
                failed_reasons[target_num] = "内容不是有效正文"
                _set_status(novel_id, "error", f"第{target_num}章生成失败（内容不是有效正文），已跳过", 0)
                _update_job_progress(novel_id, index + 1, count, f"第{target_num}章生成失败（内容不是有效正文）")
                continue
            final_rejection = _batch_final_rejection(chapter, final_quality, q_threshold)
            if final_rejection:
                print(f"[BATCH ERROR] {novel_id} ch{target_num}: final gate rejected ({final_rejection}), skipping slot {target_num}")
                db.log(
                    novel_id,
                    "chapter.final_quality_skipped",
                    {
                        "target_num": target_num,
                        "reason": final_rejection,
                        "word_count": chapter.word_count,
                        "quality": final_quality.get("overall", 0),
                        "threshold": q_threshold,
                    },
                )
                failed_slots.append(target_num)
                failed_reasons[target_num] = final_rejection
                _set_status(novel_id, "error", f"第{target_num}章生成失败（{final_rejection}），已跳过", 0)
                _update_job_progress(novel_id, index + 1, count, f"第{target_num}章生成失败（{final_rejection}）")
                continue
            cost_info = getattr(gen, 'pipeline_cost', {}) or {}
            db.add_chapter(
                novel_id=novel_id,
                number=chapter.number,
                title=chapter.title,
                word_count=chapter.word_count,
                summary=chapter.summary,
                content=save_body,
                ending_hook=chapter.ending_hook,
                key_events=json.dumps(chapter.key_events),
                revelations=json.dumps(chapter.revelations),
                narrative_facts=json.dumps(chapter.narrative_facts, ensure_ascii=False),
                quality_score=final_quality["overall"],
                model_used=cfg.model,
                prompt_tokens=cost_info.get("prompt_tokens", 0),
                completion_tokens=cost_info.get("completion_tokens", 0),
                cost=round(cost_info.get("cost", 0), 6),
            )

            try:
                _sync_resolved_foreshadowing(
                    db,
                    novel_id,
                    state,
                    chapter.number,
                    source_chapter_num=source_chapter_num,
                )
                _sync_new_foreshadowing(db, novel_id, state, chapter.number)
                _sync_next_plot_points(db, novel_id, state)
                extract_story_bible(novel_id, chapter.number, chapter.content, chapter.title)
                run_consistency_check(novel_id, chapter.number)
            except Exception as exc:
                print(f"[BATCH] story bible update failed for ch{target_num}: {exc}")

            state.chapters.append(chapter)

            try:
                gen._extract_character_voices(cleaned_body, state)
            except Exception:
                pass

            if state.total_chapters % 10 == 0:
                try:
                    audit = gen.audit_foreshadowing(state)
                    if audit.get("warning"):
                        print(f"[BATCH] ⚠️  {novel_id}: {audit['warning']}")
                except Exception:
                    pass

            db.log(novel_id, "chapter.generated", {
                "chapter": target_num,
                "words": len(cleaned_body),
                "quality": quality["overall"],
                "grade": quality["grade"],
                "de_ai_changes": de_ai_changes,
                "batch": index + 1,
            })
            generated_count += 1
            print(f"[BATCH] {novel_id} ch{target_num}/{state.total_chapters} — {len(cleaned_body)}w — Q:{quality['grade']}({quality['overall']})")

            if target_num > 30 and len(cleaned_body) > 100:
                try:
                    _generate_single_chapter_summary(novel_id, gen, target_num, cleaned_body[:1000])
                except Exception as exc:
                    print(f"[BATCH] summary gen failed for ch{target_num}: {exc}")

        failed_count = len(failed_slots)
        if generated_count == count:
            message = f"批量生成完成：{generated_count}章"
            status = "complete"
        elif generated_count > 0:
            failed_text = "、".join(
                f"第{number}章{failed_reasons.get(number, '生成失败')}" for number in failed_slots
            )
            message = f"批量生成完成：{generated_count}/{count}章（{failed_text}，已跳过）"
            status = "complete"
        else:
            failed_text = "、".join(
                f"第{number}章{failed_reasons.get(number, '生成失败')}" for number in failed_slots
            )
            reason_suffix = f"（{failed_text}）" if failed_text else ""
            message = f"批量生成失败：0/{count}章产出有效内容{reason_suffix}"
            status = "error"

        _set_status(novel_id, status, message, 100 if generated_count else 0)
        _update_job_progress(novel_id, count, count)
        return {
            "requested": count,
            "generated": generated_count,
            "failed": failed_count,
            "failed_slots": failed_slots,
            "message": message,
        }

    except Exception as exc:
        import traceback
        traceback.print_exc()
        db = get_db()
        err_msg = str(exc)[:200]
        _set_status(novel_id, "error", f"批量生成失败: {err_msg}", 0)
        _update_job_progress(novel_id, 0, 0, err_msg)
        db.log(novel_id, "error.critical", {"error": err_msg})
        print(f"[BATCH ERROR] {novel_id}: {err_msg}", file=sys.stderr)
        return {
            "requested": count,
            "generated": 0,
            "failed": count,
            "failed_slots": [],
            "message": f"批量生成失败: {err_msg}",
        }


def _build_batch_targets(db, novel_id: str, count: int) -> list[dict]:
    """Build contiguous append-safe batch slots, attaching matching outline hints."""
    next_chapter = db.get_next_chapter_number(novel_id) if hasattr(db, "get_next_chapter_number") else 1
    outline_by_number: dict[int, dict] = {}
    try:
        with db.conn() as conn:
            rows = conn.execute(
                """SELECT number, title, summary FROM chapters
                   WHERE novel_id=? AND word_count=0 AND number>=? AND number<?
                   ORDER BY number""",
                (novel_id, next_chapter, next_chapter + count),
            ).fetchall()
            outline_by_number = {
                row["number"]: {"number": row["number"], "title": row["title"], "summary": row["summary"]}
                for row in rows
            }
    except Exception:
        outline_by_number = {}

    return [
        outline_by_number.get(number, {"number": number, "title": f"第{number}章", "summary": ""})
        for number in range(next_chapter, next_chapter + count)
    ]


def _ensure_smart_context(novel_id: str, gen, state) -> None:
    """Summarize older chapters for long novels so context stays compact."""
    db = get_db()
    if os.environ.get("SKIP_SUMMARIES"):
        return

    total = state.total_chapters
    if total < 30:
        return

    summarize_up_to = max(5, total - 25)
    if db.has_chapter_summaries(novel_id, summarize_up_to):
        return

    print(f"[CONTEXT] Smart context: summarizing chapters 1..{summarize_up_to} for {novel_id}")

    for chapter_num in range(1, summarize_up_to + 1):
        existing = db.get_chapter_summaries(novel_id, [chapter_num])
        if existing:
            continue

        chapter = db.get_chapter(novel_id, chapter_num)
        if not chapter or not chapter.get("content"):
            continue

        content = chapter["content"][:1000]
        summary = _generate_summary_with_llm(gen, novel_id, chapter_num, content)
        if summary:
            db.save_chapter_summary(novel_id, chapter_num, summary)
            print(f"[CONTEXT] Summarized ch{chapter_num}: {summary[:60]}...")

    print(f"[CONTEXT] Smart context summaries complete for {novel_id}")


def _generate_single_chapter_summary(novel_id: str, gen, chapter_num: int, content: str) -> None:
    summary = _generate_summary_with_llm(gen, novel_id, chapter_num, content)
    if summary:
        get_db().save_chapter_summary(novel_id, chapter_num, summary)


def _generate_summary_with_llm(gen, novel_id: str, chapter_num: int, content: str) -> str:
    try:
        result = gen._call_llm_with_retry(
            [
                {
                    "role": "system",
                    "content": (
                        "你是一位小说编辑。用一句话概括以下章节的核心事件、人物变化、主角主动选择，"
                        "以及收益带来的代价/后果（不超过60字）。如果有受伤、债务、暴露风险、关系裂痕或后续麻烦，必须保留。"
                    ),
                },
                {"role": "user", "content": content[:1000]},
            ],
            max_tokens=128,
        )
        summary = result.strip()
        usage = getattr(gen, "_last_usage", None)
        if usage:
            _record_chapter_cost(
                novel_id,
                chapter_num,
                usage.get("model", ""),
                usage.get("prompt_tokens", 0),
                usage.get("completion_tokens", 0),
                usage.get("total_tokens", 0),
                usage.get("cost", 0),
                purpose="summarize",
            )
        return summary
    except Exception as exc:
        print(f"[CONTEXT] Failed to summarize ch{chapter_num}: {exc}")
        return ""


def _record_chapter_cost(
    novel_id: str,
    chapter_number: int,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    total_tokens: int,
    cost: float,
    purpose: str = "generate",
) -> None:
    try:
        get_db().log_cost(
            novel_id,
            chapter_number,
            model,
            prompt_tokens,
            completion_tokens,
            total_tokens,
            cost,
            purpose,
        )
    except Exception:
        pass


def run_generation_classic(novel_id: str) -> None:
    """Background: generate one chapter using classic multi-candidate mode."""
    try:
        db = get_db()
        _set_status(novel_id, "generating", "经典模式：正在多版本筛选…（约需3-5分钟）", 10)
        gen, model = _generator_and_model(novel_id)
        state = _load_state(novel_id)
        if not state:
            return
        outline = _build_batch_targets(db, novel_id, 1)
        rag_context = gen.retrieve_relevant_context(
            query=state.plot.current_arc or state.plot.premise,
            novel_id=novel_id,
            top_k=5,
        )
        style = _style_for(novel_id)
        author_input = build_creation_brief(db, novel_id)

        _set_status(novel_id, "generating", "经典模式：生成+淘汰中…", 20)
        chapter = gen.generate_chapter_classic(
            state,
            style=style,
            rag_context=rag_context,
            outline=outline,
            author_input=author_input,
        )
        body = chapter.content or chapter.summary
        cleaned, _de_ai_changes = gen.de_ai(body)
        quality = gen.judge_quality(cleaned or body, state, style)
        gen.refresh_chapter_content(chapter, cleaned or body)
        rejection = chapter_content_rejection("", chapter.content)
        if rejection:
            raise RuntimeError(f"生成结果不是有效章节正文：{rejection}")

        db.add_chapter(
            novel_id=novel_id,
            number=chapter.number,
            title=chapter.title,
            word_count=chapter.word_count,
            summary=chapter.summary,
            content=chapter.content,
            ending_hook=chapter.ending_hook,
            key_events=json.dumps(chapter.key_events),
            revelations=json.dumps(chapter.revelations),
            narrative_facts=json.dumps(chapter.narrative_facts, ensure_ascii=False),
            quality_score=quality["overall"],
            model_used=model,
        )
        try:
            _sync_resolved_foreshadowing(db, novel_id, state, chapter.number)
            _sync_new_foreshadowing(db, novel_id, state, chapter.number)
            _sync_next_plot_points(db, novel_id, state)
            extract_story_bible(novel_id, chapter.number, chapter.content, chapter.title)
            run_consistency_check(novel_id, chapter.number)
        except Exception as exc:
            print(f"[CLASSIC] story bible update failed for ch{chapter.number}: {exc}")
        _set_status(
            novel_id,
            "complete",
            f"第{chapter.number}章完成 — 经典模式 — Q:{quality.get('grade','?')}({quality.get('overall',0):.2f})",
            100,
        )
    except Exception as exc:
        _set_status(novel_id, "error", f"经典模式失败: {str(exc)[:200]}", 0)


def _run_single_generation(novel_id: str, compression: str, quality_threshold: float) -> dict:
    """Adapter for BatchRunner while the main generation pipeline still lives in legacy."""
    from . import _legacy

    state = get_gen_state()
    _legacy._gen_directions[novel_id + "_compression"] = compression
    _legacy._gen_directions[novel_id + "_qthreshold"] = str(quality_threshold)
    _legacy._run_generation(novel_id)
    status = state._status.get(novel_id, {})
    return {
        "quality": {
            "overall": status.get("overall", 0),
            "grade": status.get("grade", "?"),
        },
        "word_count": status.get("word_count", 0),
        "retries": status.get("retries", 0),
        "auto_recovery": status.get("auto_recovery", False),
    }


def run_longrun_batch_generation(
    novel_id: str,
    chapters: int,
    compression: str,
    quality_threshold: float,
) -> None:
    """Background: run batch generation with metrics tracking."""
    from novel_writer.stations.novel.batch_runner import BatchRunner

    db = get_db()
    state = get_gen_state()
    try:
        runner = BatchRunner(db, _get_provider, _run_single_generation)
        report = runner.run(novel_id, chapters, compression, quality_threshold)
        state._status[novel_id] = {
            "status": "batch_complete",
            "message": f"批量生成完成: {report['chapters_generated']}/{chapters}章",
            "progress": 100,
            "batch_report": report,
        }
        print(runner.format_report(report))
    except Exception as exc:
        state._status[novel_id] = {
            "status": "batch_failed",
            "message": f"批量生成失败: {str(exc)[:100]}",
            "progress": 0,
        }
        traceback.print_exc()
