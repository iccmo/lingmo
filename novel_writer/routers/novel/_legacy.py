"""小说路由 — CRUD、写作生成、质量分析、导出发布。"""

import json
import sys
import copy
from pathlib import Path

from novel_writer.log_config import get_logger
log = get_logger(__name__)

from fastapi import APIRouter, BackgroundTasks, HTTPException

from novel_writer.brain_agent import BrainAgent
from novel_writer.stations.novel.constraint_compressor import ConstraintCompressor
from novel_writer.routers.deps import get_db, get_gen_state
from novel_writer.routers.novel.generation_support_service import (
    build_creation_brief,
    build_constraints,
    editor_review,
    targeted_rewrite,
)
from novel_writer.routers.novel.generation_service import (
    _sync_new_foreshadowing,
    _sync_next_plot_points,
    _sync_resolved_foreshadowing,
)
from novel_writer.routers.novel.chapter_metadata import chapter_content_rejection, update_chapter_content
from novel_writer.routers.novel.story_bible_service import extract_story_bible, run_consistency_check

router = APIRouter(tags=["novel"])


def _gstate():
    """Shortcut to access the shared generation state singleton."""
    return get_gen_state()


def _get_db():
    """Lazy DB access — always fetches from deps, never caches at module level."""
    return get_db()


def _get_provider(novel_id: str | None = None):
    """Get configured model provider — default to DeepSeek."""
    db = _get_db()
    provider_id = "deepseek"
    if novel_id:
        novel = db.get_novel(novel_id)
        if novel:
            provider_id = novel.get("provider_id", "deepseek")
    provider = db.get_provider(provider_id)
    if not provider or not provider.get("api_key"):
        for p in db.list_providers():
            if p.get("api_key"):
                provider = db.get_provider(p["id"])
                break
    return provider or {"id": "deepseek", "base_url": "https://api.deepseek.com", "api_key": "", "models": ["deepseek-v4-pro"]}


# Compat aliases for existing code that uses module-level names
_set_status = lambda *a, **kw: _gstate().set_status(*a, **kw)
_get_status = lambda *a: _gstate().get_status(*a)
_gen_status = _gstate()._status
_gen_lock = _gstate()._lock


# Lazy DB proxy — resolves at first access, not import time
class _LazyDB:
    """Proxy that delegates all attribute access to the real database instance."""
    def _real(self):
        return get_db()
    def __getattr__(self, name):
        return getattr(self._real(), name)

db = _LazyDB()


# ═══════════════ Helpers ═══════════════

def _legacy_rewrite_is_saveable(novel_id: str, chapter_num: int, content: str, operation: str) -> bool:
    try:
        chapter = db.get_chapter(novel_id, chapter_num)
        old_content = chapter.get("content", "") if chapter else ""
    except Exception:
        old_content = ""
    rejection = chapter_content_rejection(old_content, content)
    if not rejection:
        return True
    try:
        db.log(
            novel_id,
            "autonomous.rewrite_rejected",
            {"chapter": chapter_num, "operation": operation, "reason": rejection},
        )
    except Exception:
        pass
    return False


def _legacy_generated_content_error(content: str) -> str:
    rejection = chapter_content_rejection("", content)
    if not rejection:
        return ""
    return f"生成结果不是有效章节正文：{rejection}"


def _build_pattern_disruption_prompt(body: str) -> str:
    return f"""以下是一章小说正文。如果这一章的结构是"铺垫→冲突→解决→悬念"的标准模式，请在保持主线的前提下，做以下任一改变：
1. 把高潮提前到中间，后半段写余波
2. 用一句毫不相关的话结尾（但暗中与主题呼应）
3. 在最紧张的时刻插入一段平静的描写

硬性保真：
1. 不得删除或淡化主角主动选择、拒绝、承担、冒险、反击、押注
2. 不得删除或淡化收益带来的代价、后果、后患、伤口、债务、身份暴露、关系裂痕、后续麻烦
3. 可以打散结构，但不能把有代价的胜利改成无代价开挂，不能把主角改成被事件推着走

如果文章结构已经独特，则保持不变。请直接返回全文。

正文：
{body}"""


def _final_save_quality_error(final_quality: dict, q_threshold: float) -> str:
    try:
        score = float((final_quality or {}).get("overall", 0) or 0)
    except (TypeError, ValueError):
        score = 0.0
    if score >= q_threshold:
        return ""
    return f"最终保存稿质量 {score:.2f} 低于门槛 {q_threshold:.2f}，已拒绝落库"


def _build_recovery_direction(state, prev_chapter=None) -> str:
    direction = (
        f"写{state.genre}小说第{state.total_chapters + 1}章。保持风格一致。"
        "本章必须让主角做出清晰主动选择：拒绝、承担、冒险、反击或押注。"
        "本章重要收益必须绑定具体代价或后果：受伤、失去、身份暴露、资源消耗、关系裂痕或后续麻烦至少一种。"
    )
    if prev_chapter:
        direction += f" 上章：{prev_chapter.title}。{prev_chapter.ending_hook}"
    return direction


def _random_name(genre: str = "玄幻") -> str:
    from novel_writer.generator import random_protagonist_name
    name, _ = random_protagonist_name(genre)
    return name

# ═══════════════ Chapters ═══════════════

# ═══════════════ Generate ═══════════════

# In-memory store for chapter generation directions
_gen_directions: dict[str, str] = {}

# In-memory store for agent pipeline results (keyed by novel_id)
_constraints_cache: dict[str, str] = {}

def _structify_guidance(guidance: str) -> str:
    """Convert verbose technique advice into structured constraints the LLM can follow."""
    if not guidance or len(guidance) < 10:
        return ""
    rules = []
    for line in guidance.split('\n'):
        line = line.strip()
        if not line:
            continue
        lower = line.lower()
        # Convert suggestions to rules
        if any(w in lower for w in ['建议', '可以', '考虑', '或许', '可能']):
            line = line.replace('建议', '').replace('可以', '必须').replace('考虑', '必须')
        if any(w in lower for w in ['增加', '减少', '提高', '降低', '避免', '必须', '不能']):
            rules.append(f"- {line}")
    if not rules:
        return ""
    return "【必须严格遵守的硬性技法规则】\n" + "\n".join(rules[:5])


def _with_generation_context(base_context: str, repair_instruction: str = "") -> str:
    """Keep soul/character/constraint context attached during retries and rewrites."""
    base_context = (base_context or "").strip()
    repair_instruction = (repair_instruction or "").strip()
    if base_context and repair_instruction:
        return f"{base_context}\n\n【本次修复要求】\n{repair_instruction}"
    return repair_instruction or base_context

def _run_generation(novel_id: str):
    """V3: Full generation pipeline with quality scoring, de-AI, and RAG"""
    from novel_writer.trace import TraceRecorder
    novel = db.get_novel(novel_id)
    next_ch = db.get_next_chapter_number(novel_id) if hasattr(db, "get_next_chapter_number") else (
        max([c.get("number", 0) for c in novel.get("chapters", []) if c.get("word_count", 0) > 0], default=0) + 1
    )
    tracer = TraceRecorder(novel_id, next_ch)

    # Checkpoint recovery: if previous run left a checkpoint, use it to resume
    checkpoint = _gen_status.get(novel_id, {}).get("checkpoint")
    recovered_raw = ""
    if checkpoint and isinstance(checkpoint, dict):
        recovered_raw = checkpoint.get("raw_body", "")
        recovered_phase = checkpoint.get("phase", "")
        if recovered_raw and len(recovered_raw) > 50:
            log.warning("Recovering from checkpoint phase=%s novel=%s ch=%d", recovered_phase, novel_id, next_ch)
            _gen_status[novel_id].pop("checkpoint", None)

    try:
        tracer.step("init", summary="启动生成管线")
        _set_status(novel_id, "generating", "正在构思章节…（生成中，约需60秒）", 10)
        from novel_writer.config import Config
        from novel_writer.generator import Generator
        provider = _get_provider(novel_id)
        model_override = _gen_directions.pop(novel_id + "_model", "")
        model = model_override or (provider.get("models", "deepseek-v4-pro")[0] if provider.get("models") else "gpt-4o")
        cfg = Config(
            openai_api_key=provider.get("api_key", ""),
            openai_base_url=provider.get("base_url", ""),
            model=model,
        )
        gen = Generator(cfg)
        getattr(gen, 'reset_cumulative_cost', lambda: None)()
        # Streaming callback: push partial content to status for live preview
        def on_stream(text: str):
            # Strip thinking tokens and clean
            clean = gen._strip_thinking(text)
            _gstate().update_stream_content(novel_id, clean[:8000])
        gen._on_stream_chunk = on_stream  # type: ignore[attr-defined]
        state = _load_state(novel_id)
        # Load style profile
        style = None
        try:
            from novel_writer.generator import StyleProfile, _get_style_for_genre
            style_data = db.get_style_profile(novel_id)
            if style_data:
                style = StyleProfile(**{k: v for k, v in style_data.items() if k in StyleProfile.__dataclass_fields__})
            if style is None:
                style = _get_style_for_genre(state.genre)
        except Exception:
            style = None
        if not state:
            return

        # Load outline for context injection
        outline = []
        try:
            next_outline_ch = db.get_next_chapter_number(novel_id) if hasattr(db, "get_next_chapter_number") else next_ch
            with db.conn() as conn:
                rows = conn.execute(
                    """SELECT number, title, summary FROM chapters
                       WHERE novel_id=? AND word_count=0 AND number>=? AND number<?
                       ORDER BY number""",
                    (novel_id, next_outline_ch, next_outline_ch + 1)
                ).fetchall()
                outline = [{"number": r["number"], "title": r["title"], "summary": r["summary"]} for r in rows]
        except Exception:
            pass

        # RAG: retrieve relevant context (auto-expands to 15 for novels >30 chapters)
        rag_context = gen.retrieve_relevant_context(
            query=state.plot.current_arc or state.plot.premise,
            novel_id=novel_id,
            top_k=5,
        )

        # Global context for long novels — inject recent chapter summaries
        global_ctx = gen.get_global_context(novel_id, max_chapters=10)
        if global_ctx:
            if rag_context:
                rag_context = rag_context or []
            else:
                rag_context = []
            rag_context.insert(0, {"chapter_number": 0, "title": "📖 前情提要", "chunk_text": global_ctx, "similarity": 1.0})

        # Inject unsaid_book hidden truths into context
        try:
            unsaid_entries = db.get_unsaid(novel_id)
            if unsaid_entries:
                unsaid_text = "\n".join(f"- {e['entry']}" for e in unsaid_entries[-10:])
                if rag_context:
                    rag_context = [{"chapter_number": 0, "title": "🔒 作者隐藏设定", "chunk_text": unsaid_text, "similarity": 1.0}] + rag_context
                else:
                    rag_context = [{"chapter_number": 0, "title": "🔒 作者隐藏设定", "chunk_text": unsaid_text, "similarity": 1.0}]
        except Exception:
            pass

        # Batch generate (n versions, pick best by quality)
        import time as _time
        t0 = _time.time()
        # Read author direction + soul injection if set
        author_direction = _gen_directions.pop(novel_id, "")
        soul_injection = _gen_directions.pop(novel_id + "_soul", "")
        creation_brief = soul_injection or build_creation_brief(db, novel_id)
        if creation_brief:
            author_direction = creation_brief + ("\n\n作者方向：" + author_direction if author_direction else "")
        # Inject lessons from previous failures
        lessons = gen.inject_lessons(novel_id, db)
        if lessons:
            author_direction = lessons + author_direction
        # 【核心】Brain Agent + 约束压缩 —— 数据库写小说，AI只是笔
        next_ch = state.total_chapters + 1
        brain = BrainAgent(db)
        constraint_result = brain.constraint_builder.run({
            "novel_id": novel_id, "chapter_num": next_ch, "db": db
        })
        compressor = ConstraintCompressor()
        # Configurable compression level (default L1, "NONE" to skip constraints)
        comp_level = _gen_directions.pop(novel_id + "_compression", "L1")
        compressed = {"text": "", "char_count": 0}
        if comp_level == "NONE":
            _set_status(novel_id, "generating", "正在生成候选版本…（无约束对照组）", 20)
        else:
            compressed = compressor.compress(constraint_result, comp_level)
            if compressed["text"]:
                author_direction = f"【硬约束】\n{compressed['text']}\n\n" + ("【作者方向】\n" + author_direction if author_direction else "")
            _set_status(novel_id, "generating", f"正在生成候选版本…（约束{compressed['char_count']}字）", 20)
        tracer.step("constraint_compression", summary=f"压缩后{compressed['char_count']}字约束")

        # 【技法顾问】场景分析 → 写作指导注入
        technique_guidance = ""
        try:
            from novel_writer.stations.novel.technique_advisor import TechniqueAdvisor
            advisor = TechniqueAdvisor()
            prev_chs = [c for c in state.chapters if c.word_count > 0]
            prev_hook = prev_chs[-1].ending_hook if prev_chs else ""
            tech_result = advisor.run({
                "novel_id": novel_id,
                "chapter_num": next_ch,
                "db": db,
                "outline": outline,
                "prev_hook": prev_hook,
                "genre": state.genre,
                "constraints": compressed.get("text", "") if comp_level != "NONE" else "",
            })
            if tech_result.get("guidance"):
                raw_guidance = tech_result["guidance"]
                # Convert natural language advice to structured constraints
                structured = _structify_guidance(raw_guidance)
                tracer.step("technique_advisor", summary=f"结构化技法{len(structured)}字" if structured else "跳过")
                if structured:
                    author_direction = author_direction + "\n\n【硬技法约束】\n" + structured
                print(f"[TECHNIQUE] {novel_id} Ch{next_ch}: {technique_guidance[:60]}...")
        except Exception as e:
            print(f"[TECHNIQUE] skipped: {e}")

        chapter, quality = gen.batch_generate(state, n=2, rag_context=rag_context, outline=outline, style=style, author_input=author_direction)
        if getattr(gen, 'model_switched', None):
            _gen_status[novel_id]["model_switched"] = gen.model_switched
        tracer.step("batch_generate", summary=f"Q={quality.get('overall',0):.2f}" if quality else "n=2")
        gen_duration = (_time.time() - t0) * 1000
        body = chapter.content or chapter.summary

        # Checkpoint: save raw body to recover from crashes during post-processing
        _gen_status[novel_id]["checkpoint"] = {"phase": "generated", "raw_body": body}

        # Guard: empty content means LLM API returned nothing
        if not body or len(body.strip()) < 50:
            _set_status(novel_id, "error", "生成失败：模型返回内容为空，请检查 API 配置或重试", 0)
            db.log(novel_id, "generation.empty_body", {"chapter": next_ch, "model": cfg.model})
            return

        # Use dynamic threshold based on recent quality history
        q_threshold = gen.get_dynamic_threshold(novel_id, db)
        user_threshold = _gen_directions.pop(novel_id + "_qthreshold", "")
        if user_threshold:
            q_threshold = max(q_threshold, float(user_threshold))
        retries = 0
        max_retries = 3 if q_threshold >= 0.8 else 2
        while quality['overall'] < q_threshold and retries < max_retries:
            retries += 1
            issues_str = '；'.join(quality.get('issues', ['质量不足']))
            print(f"[GEN] {novel_id} Q={quality['overall']} — retry #{retries}: {issues_str}")

            # Phase 1: Targeted edit (lightweight, for minor quality gaps)
            if retries == 1 and quality['overall'] >= q_threshold - 0.15:
                _set_status(novel_id, "reviewing", "定向编辑修复中…", 32)
                editor_result = editor_review(novel_id, chapter.number, body, quality.get('issues', []))
                if editor_result.get('feedback'):
                    _set_status(novel_id, "generating", "根据编辑意见定向修改…", 37)
                    body = targeted_rewrite(novel_id, chapter.number, body, editor_result['feedback'])
                    _set_status(novel_id, "reviewing", "重新评分…", 42)
                    quality = gen.score_quality(body, state, style)
                    print(f"[GEN] {novel_id} Editor fix Q={quality['overall']}")
                    if quality['overall'] >= q_threshold:
                        break

            # Phase 2: Targeted fix based on specific issues (for larger gaps)
            if retries <= 2 and quality['overall'] >= q_threshold - 0.2:
                _set_status(novel_id, "generating", f"针对性修复：{issues_str[:30]}…", 35 + retries * 10, quality['overall'])
                fix_prompt = f"请改进以下问题：{issues_str}。保持其他部分不变。"
                chapter, quality = gen.batch_generate(
                    state,
                    n=1,
                    rag_context=rag_context,
                    outline=outline,
                    style=style,
                    author_input=_with_generation_context(author_direction, fix_prompt),
                )
                body = chapter.content or chapter.summary
                quality = gen.score_quality(body, state, style)
                if quality['overall'] >= q_threshold:
                    break

            # Phase 3: Full regenerate (last resort)
            _set_status(novel_id, "generating", f"全面重写…（第{retries+1}次）", 40 + retries * 15, quality['overall'])
            chapter, quality = gen.batch_generate(
                state,
                n=1,
                rag_context=rag_context,
                outline=outline,
                style=style,
                author_input=_with_generation_context(author_direction, "全面重写上一版，优先解决质量问题，但必须保持全部硬约束。"),
            )
            body = chapter.content or chapter.summary
            _set_status(novel_id, "reviewing", "正在质检评分…", 60)

        # Combined edit+spec — pacing + specificity in one LLM call (saves ~120s)
        _gen_status[novel_id]["checkpoint"] = {"phase": "editing", "raw_body": body}
        _set_status(novel_id, "editing", "正在精修+具体化…（约60秒）", 65)
        edit_constraints = f"\n\n硬约束（修改时不得破坏）：\n{author_direction[:4000]}" if author_direction else ""
        combined_prompt = f"""你是资深编辑。同时完成以下优化，返回修改后的全文：

1. 精修：修复冗余、节奏、过渡问题
2. 具体化：将模糊描写（如"很生气""非常漂亮"）替换为具体的五感细节
{edit_constraints}

正文：
{body}

直接返回修改后的全文，不要任何说明。"""
        try:
            resp = gen._call_llm_with_retry([{"role": "user", "content": combined_prompt}], max_tokens=8192)
            if resp and len(resp) > len(body) * 0.7:
                body = resp
                tracer.step("edit", summary="精修+具体化(合并)")
        except Exception as e:
            print(f"[GEN] {novel_id} combined edit failed: {e}")

        # De-AI post-processing
        cleaned_body, de_ai_changes = gen.de_ai(body)
        tracer.step("de_ai", summary=f"{de_ai_changes}处修改")
        if de_ai_changes > 0:
            print(f"[GEN] {novel_id} de-AI: {de_ai_changes} changes")

        # Constraint check
        try:
            constraint_text = compressed.get("text", "") if comp_level != "NONE" else ""
            if constraint_text:
                check = gen.check_constraints(cleaned_body or body, constraint_text)
                tracer.step("constraint_check", summary=f"{len(check.get('violations',[]))} violations" if check.get("violations") else "passed")
                if check.get("violations"):
                    db.log(novel_id, "constraint.violations", {"violations": check["violations"]})
        except Exception as e:
            print(f"[GEN] {novel_id} constraint check failed: {e}")

        # Pattern Disruption — for chapters 3+, optional (saves 1 LLM call)
        if chapter.number >= 3 and _gen_directions.pop(novel_id + "_pattern_disruption", ""):
            try:
                disruption_prompt = _build_pattern_disruption_prompt(body)
                disruption_messages = [{"role": "user", "content": disruption_prompt}]
                disruption_result = gen._call_llm_with_retry(disruption_messages, max_tokens=8192)
                if disruption_result and len(disruption_result) > len(body) * 0.8:
                    body = disruption_result
                    cleaned_body = ""
                    tracer.step("pattern_disruption", status="ok", summary="模式打散")
                    print(f"[GEN] {novel_id} pattern disruption applied")
            except Exception as e:
                print(f"[GEN] {novel_id} disruption pass failed: {e}")

        # LLM Judge — final quality evaluation
        _set_status(novel_id, "judging", "正在 AI 评估质量…（约15秒）", 80)
        final_quality = gen.judge_quality(cleaned_body or body, state, style)
        tracer.step("llm_judge", summary=f"Q={final_quality.get('overall',0):.2f} grade={final_quality.get('grade','?')}" if final_quality else "failed")
        if final_quality.get("method") == "llm":
            print(f"[GEN] {novel_id} LLM judge: {final_quality['grade']}({final_quality['overall']}) — {final_quality.get('judge_detail', {})}")

        # If LLM judge score is below threshold, retry with judge feedback
        judge_retries = 0
        while final_quality['overall'] < q_threshold and judge_retries < 2:
            judge_retries += 1
            issues_str = '；'.join(final_quality.get('issues', ['质量不足']))
            print(f"[GEN] {novel_id} LLM Judge Q={final_quality['overall']} — judge retry #{judge_retries}: {issues_str}")
            _set_status(novel_id, "generating", f"LLM 评审未达标，针对性重写…（第{judge_retries}次）", 50 + judge_retries * 15, final_quality['overall'])
            chapter, quality = gen.batch_generate(
                state,
                n=1,
                rag_context=rag_context,
                outline=outline,
                style=style,
                author_input=_with_generation_context(author_direction, f"请改进以下问题：{issues_str}"),
            )
            body = chapter.content or chapter.summary
            # Re-do de-AI and judge
            body = gen._self_edit(body, state, style)
            cleaned_body, _ = gen.de_ai(body)
            final_quality = gen.judge_quality(cleaned_body or body, state, style)
            body = cleaned_body or body

        # Auto-extract causal events for world simulation
        try:
            causal_prompt = f"""以下是一章小说正文。请提取本章中2-3个最重要的因果事件——这些事件会在后续章节中产生涟漪效应。

格式（每行一条）：
{chapter.title}中发生了X → 这将导致Y

正文（前2000字）：
{(cleaned_body or body)[:2000]}"""
            causal_messages = [{"role": "user", "content": causal_prompt}]
            causal_result = gen._call_llm_with_retry(causal_messages, max_tokens=512)
            if causal_result:
                # Store in _gen_status for frontend + log
                _gen_status[novel_id]["causal_events"] = causal_result[:500]
                print(f"[GEN] {novel_id} causal events extracted: {causal_result[:100]}")
        except Exception as e:
            print(f"[GEN] {novel_id} causal extraction failed: {e}")

        # Clear checkpoint on success
        _gen_status[novel_id].pop("checkpoint", None)

        # Save chapter
        tracer.finish(quality=final_quality.get('overall', 0) if final_quality else 0, db_instance=db)
        # Final de-AI pass: ensure orphan quotes are fixed before saving
        save_content = cleaned_body or body
        save_content, save_deai_changes = gen.de_ai(save_content)
        if save_deai_changes > de_ai_changes:
            de_ai_changes = save_deai_changes
        if save_content != (cleaned_body or body):
            final_quality = gen.judge_quality(save_content, state, style)
            tracer.step("llm_judge_final_save", summary=f"Q={final_quality.get('overall',0):.2f} grade={final_quality.get('grade','?')}" if final_quality else "failed")
        final_save_error = _final_save_quality_error(final_quality, q_threshold)
        if final_save_error:
            tracer.step("llm_judge_final_save", status="error", summary=final_save_error)
            db.log(novel_id, "generation.final_save_quality_rejected", {"reason": final_save_error})
            _set_status(novel_id, "error", final_save_error, 0, final_quality.get("overall", 0) if final_quality else 0)
            return
        gen.refresh_chapter_content(chapter, save_content)
        content_error = _legacy_generated_content_error(chapter.content)
        if content_error:
            raise ValueError(content_error)

        cost_info = getattr(gen, 'pipeline_cost', None) or {}
        if callable(cost_info):
            cost_info = cost_info() or {}
        cid = db.add_chapter(
            novel_id=novel_id, number=chapter.number, title=chapter.title,
            word_count=chapter.word_count, summary=chapter.summary,
            content=save_content, ending_hook=chapter.ending_hook,
            key_events=json.dumps(chapter.key_events),
            revelations=json.dumps(chapter.revelations),
            narrative_facts=json.dumps(chapter.narrative_facts, ensure_ascii=False),
            quality_score=final_quality['overall'], model_used=cfg.model,
            prompt_tokens=cost_info.get("prompt_tokens", 0),
            completion_tokens=cost_info.get("completion_tokens", 0),
            cost=round(cost_info.get("cost", 0), 6),
        )
        if save_content and len(save_content) > 100:
            try:
                from novel_writer.routers.novel.generation_service import _generate_single_chapter_summary
                _generate_single_chapter_summary(novel_id, gen, chapter.number, save_content[:1000])
            except Exception as exc:
                print(f"[GEN] summary gen failed for ch{chapter.number}: {exc}")
        try:
            _sync_resolved_foreshadowing(db, novel_id, state, chapter.number)
            _sync_new_foreshadowing(db, novel_id, state, chapter.number)
            _sync_next_plot_points(db, novel_id, state)
        except Exception as sync_exc:
            db.log(novel_id, "story_state.sync_failed", {"error": str(sync_exc)[:200]})

        # V7: Pre-generate TTS audio in background (non-blocking)
        try:
            import threading

            from novel_writer.routers.audiobook import _pregen_tts_background
            threading.Thread(target=_pregen_tts_background, args=(novel_id, chapter.number), daemon=True).start()
        except Exception:
            pass

        # Brain Agent: post-generation checks (deslop + consistency)
        try:
            final_body = cleaned_body or body
            brain = BrainAgent(db)
            deslop_ctx = {"content": final_body}
            if technique_guidance:
                deslop_ctx["technique_guidance"] = technique_guidance
            deslop_result = brain.deslop_filter.run(deslop_ctx)
            print(f"[BRAIN] Deslop score: {deslop_result['score']}/{deslop_result.get('max_score', 50)} ({deslop_result['grade']})")
            consistency_result = brain.consistency_checker.run({
                "novel_id": novel_id, "chapter_num": chapter.number, "db": db
            })
            print(f"[BRAIN] Consistency: {consistency_result['error_count']} errors, confidence={consistency_result['confidence']}%")
        except Exception as e:
            print(f"[BRAIN] Post-check failed: {e}")

        # V11: Extract story bible + consistency check → Agent prep next chapter (synchronous)
        try:
            extract_story_bible(novel_id, chapter.number, save_content, chapter.title)
            run_consistency_check(novel_id, chapter.number)
            # Foreshadowing auto-resolution: detect resolved threads
            try:
                from novel_writer.stations.novel.foreshadowing_resolver import ForeshadowingResolver
                resolver = ForeshadowingResolver()
                fs_result = resolver.run({
                    "novel_id": novel_id,
                    "chapter_num": chapter.number,
                    "chapter_content": save_content,
                    "db": db,
                })
                if fs_result.get("resolved", 0) > 0:
                    print(f"[FORESHADOW] Auto-resolved {fs_result['resolved']} thread(s) in ch{chapter.number}")
                    db.log(novel_id, "foreshadowing.resolved", {
                        "chapter": chapter.number,
                        "resolved_count": fs_result["resolved"],
                        "threads": fs_result.get("threads", []),
                    })
            except Exception as e:
                print(f"[FORESHADOW] Auto-resolution failed: {e}")
            _constraints_cache[novel_id] = build_constraints(novel_id, chapter.number + 1)
        except Exception:
            pass

        # Extract character voices from generated chapter
        try:
            gen._extract_character_voices(save_content, state)
        except Exception:
            pass

        # StyleProfile auto-calibration every 5 chapters
        if style and (chapter.number) % 5 == 0:
            try:
                traces = db.get_chapter_traces(novel_id)
                if traces:
                    gen.calibrate_style(style, traces)
                    db.save_style_profile(novel_id, style)
            except Exception as e:
                log.warning("Style calibration failed: %s", e)

        # Foreshadowing audit every 10 chapters
        try:
            if (chapter.number) % 10 == 0:
                audit = gen.audit_foreshadowing(state)
                if audit.get("warning"):
                    print(f"[GEN] ⚠️  {novel_id}: {audit['warning']}")
                    db.log(novel_id, "foreshadowing.audit", audit)
        except Exception:
            pass

        # Include quality details for frontend display
        quality_detail = final_quality.get("judge_detail", {})
        quality_msg = f"第{chapter.number}章完成 — {chapter.word_count}字 — Q:{final_quality['grade']}({final_quality['overall']})"
        # Quality trend for frontend
        trend = None
        try:
            trend = gen.compute_quality_trend(novel_id, db)
        except Exception:
            pass
        quality_extra = {
            "quality_detail": quality_detail,
            "grade": final_quality.get("grade", "?"),
            "overall": final_quality["overall"],
        }
        if trend is not None:
            quality_extra["quality_trend"] = trend
        _set_status(novel_id, "complete", quality_msg, 100, final_quality["overall"], extra=quality_extra)
        db.log(novel_id, "chapter.generated", {
            "chapter": chapter.number,
            "words": chapter.word_count,
            "quality": final_quality['overall'],
            "grade": final_quality['grade'],
            "de_ai_changes": de_ai_changes,
            "rag_hits": len(rag_context),
        })
        print(f"[GEN] {novel_id} ch{chapter.number} — {chapter.word_count}w — Q:{quality['grade']}({quality['overall']})")
    except Exception as e:
        import traceback
        # Record failed trace
        try:
            tracer.step("error", status="error", summary=str(e)[:100])
            tracer.finish(quality=0.0, db_instance=db)
        except Exception:
            pass
        err_msg = str(e)[:200]
        err_type = type(e).__name__
        tb = traceback.format_exc()[-300:]
        try:
            ch_num = state.total_chapters + 1 if state else 'unknown'
        except:
            ch_num = 'unknown'
        phase = f"chapter {ch_num}"

        # Log first attempt failure
        db.log(novel_id, "generation.attempt.failed", {
            "error": err_msg,
            "type": err_type,
            "phase": phase,
            "attempt": 1,
        })
        print(f"[GEN ERROR] {novel_id} attempt 1: {err_type}: {err_msg}", file=sys.stderr)
        print(f"[GEN TRACEBACK] {tb}", file=sys.stderr)

        # Auto-recovery: retry ONCE after 5 seconds with simpler prompt
        import time as _time
        _set_status(novel_id, "generating", f"生成失败，5秒后自动重试… [{err_type}]", 5)
        _time.sleep(5)

        try:
            _set_status(novel_id, "generating", "自动恢复中 — 使用简化模式重试…", 15)
            db.log(novel_id, "generation.auto_recovery", {
                "original_error": err_msg,
                "original_type": err_type,
                "phase": phase,
            })

            # Re-init generator (connection may have been broken)
            from novel_writer.config import Config
            from novel_writer.generator import Generator
            provider = _get_provider(novel_id)
            model = provider.get("models", "deepseek-v4-pro")[0] if provider.get("models") else "gpt-4o"
            cfg = Config(
                openai_api_key=provider.get("api_key", ""),
                openai_base_url=provider.get("base_url", ""),
                model=model,
            )
            gen = Generator(cfg)
            state = _load_state(novel_id)
            if not state:
                raise RuntimeError("State reload failed")

            # Simpler prompt: strip complex context, but keep the core quality contract.
            prev_chapter = None
            try:
                chs = [c for c in state.chapters if c.word_count > 0]
                prev_chapter = chs[-1] if chs else None
            except Exception:
                pass
            simple_direction = _build_recovery_direction(state, prev_chapter)

            chapter, quality = gen.batch_generate(state, n=1, author_input=simple_direction)
            body = chapter.content or chapter.summary

            # Light de-AI only
            try:
                cleaned_body, de_ai_changes = gen.de_ai(body)
                if de_ai_changes > 0:
                    body = cleaned_body
            except Exception:
                pass
            gen.refresh_chapter_content(chapter, body)
            content_error = _legacy_generated_content_error(chapter.content)
            if content_error:
                raise ValueError(content_error)
            q_threshold = gen.get_dynamic_threshold(novel_id, db)
            final_save_error = _final_save_quality_error(quality, q_threshold)
            if final_save_error:
                db.log(novel_id, "generation.recovery_quality_rejected", {"reason": final_save_error})
                raise ValueError(final_save_error)

            # Save chapter
            cid = db.add_chapter(
                novel_id=novel_id, number=chapter.number, title=chapter.title,
                word_count=chapter.word_count, summary=chapter.summary,
                content=body, ending_hook=chapter.ending_hook,
                key_events=json.dumps(chapter.key_events) if chapter.key_events else "[]",
                revelations=json.dumps(chapter.revelations) if chapter.revelations else "[]",
                narrative_facts=json.dumps(chapter.narrative_facts, ensure_ascii=False) if chapter.narrative_facts else "[]",
                quality_score=quality.get("overall", 0.7), model_used=cfg.model,
            )
            try:
                _sync_resolved_foreshadowing(db, novel_id, state, chapter.number)
                _sync_new_foreshadowing(db, novel_id, state, chapter.number)
                _sync_next_plot_points(db, novel_id, state)
            except Exception as sync_exc:
                db.log(novel_id, "story_state.sync_failed", {"error": str(sync_exc)[:200]})

            _set_status(novel_id, "complete",
                        f"第{chapter.number}章完成(自动恢复) — {chapter.word_count}字 — Q:{quality.get('overall', 0):.2f}",
                        100)
            db.log(novel_id, "generation.recovery_success", {
                "chapter": chapter.number,
                "words": chapter.word_count,
                "quality": quality.get("overall", 0),
            })
            print(f"[GEN RECOVERED] {novel_id} ch{chapter.number} — {chapter.word_count}w — Q:{quality.get('overall', 0):.2f}")
        except Exception as retry_e:
            # Retry also failed — mark as error
            retry_msg = str(retry_e)[:200]
            retry_type = type(retry_e).__name__
            retry_tb = traceback.format_exc()[-300:]

            _set_status(novel_id, "error", f"重试也失败 [{retry_type}]: {retry_msg}", 0)
            db.log(novel_id, "error.critical", {
                "error": retry_msg,
                "type": retry_type,
                "phase": phase,
                "traceback": retry_tb,
                "auto_recovery_attempted": True,
                "original_error": err_msg,
            })
            print(f"[GEN ERROR] {novel_id} retry failed: {retry_type}: {retry_msg}", file=sys.stderr)
            print(f"[GEN RETRY TRACEBACK] {retry_tb}", file=sys.stderr)


def _run_autonomous(novel_id: str, target_chapters: int = 30):
    """全自动成书：A/B→生成→管线→书名→报告→导出"""
    from dataclasses import asdict

    from novel_writer.config import Config
    from novel_writer.generator import GENRE_TO_STYLE, STYLE_POOL, Generator
    provider = _get_provider(novel_id)
    cfg = Config(openai_api_key=provider.get("api_key",""), openai_base_url=provider.get("base_url",""),
                 model=provider.get("models","deepseek-v4-pro")[0] if provider.get("models") else "gpt-4o")
    gen = Generator(cfg)

    try:
        # Phase 0: A/B test to find best voice
        _set_status(novel_id, "ab_testing", "测试14种作家声音...")
        novel = db.get_novel(novel_id)
        ab = gen.ab_test_opening(novel.get("synopsis",""), novel.get("genre","玄幻"))
        best_voice = ab.get("best_voice", "爆款网文")
        db.log(novel_id, "autonomous.ab", {"best_voice": best_voice})

        # Save optimal style
        style_key = GENRE_TO_STYLE.get(novel.get("genre","玄幻"), "玄幻")
        style = copy.copy(STYLE_POOL.get(style_key)) if STYLE_POOL.get(style_key) else None
        if style:
            style.novel_id = novel_id
            style.writer_voice = best_voice
            db.save_style_profile(novel_id, asdict(style))

        # Phase 1: Generate all chapters
        _set_status(novel_id, "generating", f"生成{target_chapters}章...")
        state = _load_state(novel_id)
        author_input = build_creation_brief(db, novel_id)
        if state:
            # Add outline
            for i in range(1, target_chapters + 1):
                with db.conn() as c:
                    existing = c.execute("SELECT id FROM chapters WHERE novel_id=? AND number=?",(novel_id,i)).fetchone()
                    if not existing:
                        c.execute("INSERT INTO chapters (novel_id,number,title,summary,word_count) VALUES (?,?,?,'',0)",(novel_id,i,f"第{i}章"))
            gen.generate_chapters(state, n=target_chapters, style=style, author_input=author_input)

        # Phase 2: Revise opening
        _set_status(novel_id, "revising", "基于结局回修前3章...")
        state2 = _load_state(novel_id)
        if state2 and state2.total_chapters >= 5:
            revised = gen.revise_opening(state2, target_chapters=3, style=style)
            for ch in revised:
                if not _legacy_rewrite_is_saveable(novel_id, ch.number, ch.content, "revise_opening"):
                    continue
                update_chapter_content(db, novel_id, ch.number, ch.content, refresh_story_bible=True)

        # Phase 3: Classic regenerate weak chapters
        _set_status(novel_id, "generating", "经典模式重写弱章...")
        novel2 = db.get_novel(novel_id)
        gen_chs = [c for c in novel2.get("chapters",[]) if c.get("word_count",0) > 0]
        if gen_chs:
            scores = [(c["number"], c.get("quality_score",0)) for c in gen_chs]
            scores.sort(key=lambda x: x[1])
            for ch_num, q in scores[:max(1, len(scores)//5)]:
                if q < 0.75:
                    state3 = _load_state(novel_id)
                    if state3:
                        new_ch = gen.generate_chapter_classic(state3, style=style, author_input=author_input)
                        if new_ch:
                            if not _legacy_rewrite_is_saveable(novel_id, ch_num, new_ch.content, "classic_rewrite"):
                                continue
                            update_chapter_content(db, novel_id, ch_num, new_ch.content, refresh_story_bible=True)

        # Phase 4: Generate title + synopsis + cover
        _set_status(novel_id, "packaging", "生成书名/简介/封面...")
        try:
            packaging = generate_packaging(novel_id)
            if packaging.get("title_candidates"):
                with db.conn() as c:
                    c.execute("UPDATE novels SET title=? WHERE id=?", (packaging["title_candidates"][0], novel_id))
            if packaging.get("blurb"):
                with db.conn() as c:
                    c.execute("UPDATE novels SET synopsis=? WHERE id=?", (packaging["blurb"], novel_id))
            # Save packaging data
            import json as _json
            from pathlib import Path
            pkg_dir = Path("data") / "packaging"
            pkg_dir.mkdir(exist_ok=True)
            (pkg_dir / f"{novel_id}.json").write_text(_json.dumps(packaging, ensure_ascii=False, indent=2))
        except Exception:
            pass

        _set_status(novel_id, "complete", f"全自动完成！{target_chapters}章")
        db.log(novel_id, "autonomous.complete", {"chapters": target_chapters})
    except Exception as e:
        _set_status(novel_id, "error", str(e)[:200])


def _safe_json_list(val):
    """Safely parse JSON-ish values to a list."""
    if not val:
        return []
    try:
        parsed = json.loads(val) if isinstance(val, str) else val
        if isinstance(parsed, list):
            return parsed
    except (json.JSONDecodeError, TypeError):
        pass
    if isinstance(val, str):
        return [item.strip() for item in val.replace("；", "\n").replace(";", "\n").splitlines() if item.strip()]
    return []


def _load_state(novel_id: str):
    """Temporary: load state from DB for generator compatibility"""
    from novel_writer.story_state import ChapterMeta, Character, Plot, StoryState, World
    novel = db.get_novel(novel_id)
    if not novel:
        return None
    if hasattr(db, "get_all_foreshadowing"):
        active_foreshadowing = [
            thread.get("description", "")
            for thread in db.get_all_foreshadowing(novel_id)
            if thread.get("description") and thread.get("status", "active") in ("active", "overdue")
        ]
    else:
        active_foreshadowing = [
            thread.get("description", "")
            for thread in db.get_active_foreshadowing(novel_id)
            if thread.get("description")
        ]
    next_plot_points = [
        point.get("content", "")
        for point in novel.get("plot_points", [])
        if point.get("content") and point.get("type", "plot") == "plot" and not point.get("is_resolved")
    ][:8]
    return StoryState(
        novel_id=novel_id, title=novel["title"], author=novel["author"],
        synopsis=novel.get("synopsis",""), genre=novel["genre"],
        world=World(name=novel.get("world_name",""), era=novel.get("world_era",""),
                     geography=novel.get("world_geo",""), power_system=novel.get("power_system","")),
        characters=[Character(id=ch["char_key"], name=ch["name"], role=ch["role"],
                     personality=ch.get("personality",""), background=ch.get("background",""),
                     current_power_level=ch.get("power_level",""),
                     voice_avg_sentence_len=v.get("avg_sentence_len", 0.0),
                     voice_question_ratio=v.get("question_ratio", 0.0),
                     voice_common_words=v.get("common_words", []),
                     voice_sample=v.get("sample", ""))
                     for ch in novel.get("characters", [])
                     for v in [json.loads(ch.get("voice_data", "{}")) if ch.get("voice_data") else {}]],
        plot=Plot(premise=novel.get("synopsis",""), main_arc=novel.get("main_arc",""),
                   current_arc=novel.get("current_arc","开篇"),
                   arc_chapter_start=novel.get("arc_chapter_start",1),
                   next_plot_points=next_plot_points,
                   foreshadowing=active_foreshadowing),
        chapters=[ChapterMeta(number=ch["number"], title=ch["title"],
                     word_count=ch["word_count"], summary=ch.get("summary",""),
                     content=ch.get("content",""),
                     ending_hook=ch.get("ending_hook",""),
                     key_events=_safe_json_list(ch.get("key_events")),
                     revelations=_safe_json_list(ch.get("revelations")),
                     narrative_facts=_safe_json_list(ch.get("narrative_facts")),
                     generated_at=ch.get("generated_at",""))
                     for ch in novel.get("chapters", []) if ch.get("word_count", 0) > 0],
    )


def generate_status(novel_id: str):
    return _get_status(novel_id)


# ═══════════════ Static ═══════════════

# ═══════════════ 7 Agent API (Pure Heuristics — No LLM) ═══════════════

# Genre → expected tropes for reader pre-understanding
GENRE_TROPES: dict[str, list[str]] = {
    "玄幻": ["修炼", "突破", "金丹", "元婴", "灵气", "法宝", "丹药", "战斗", "功法", "境界"],
    "都市": ["总裁", "契约", "复仇", "逆袭", "千金", "豪门", "公司", "谈判", "酒会", "项目"],
    "悬疑": ["线索", "谜题", "反转", "凶手", "秘密", "证据", "推理", "嫌疑人", "真相", "诡计"],
    "科幻": ["科技", "外星", "基因", "意识", "虚拟", "飞船", "人工智能", "数据", "程序", "实验室"],
    "仙侠": ["仙", "魔", "道", "剑", "宗门", "飞升", "天劫", "元气", "法宝", "灵脉"],
    "穿越": ["穿越", "系统", "任务", "奖励", "金手指", "历史", "改变", "预知", "碾压", "打脸"],
    "言情": ["告白", "误会", "分手", "重逢", "心动", "吻", "牵手", "情敌", "约会", "暗恋"],
    "恐怖": ["鬼", "尸体", "诅咒", "噩梦", "死亡", "诡异", "阴森", "血", "尖叫", "逃"],
}
GENRE_TROPES_DEFAULT: list[str] = ["主角", "冲突", "成长", "转折", "结局"]

SUBVERSION_SIGNALS: list[str] = [
    "但", "却", "竟然", "没想到", "并非如此", "反而不是", "出乎意料", "不料", "谁知", "哪知",
]

NARRATIVE_SIGNALS: dict[str, list[str]] = {
    "非线": ["回到了", "那天", "那年", "当时", "之前", "曾经", "回忆", "那时"],
    "留白": ["……", "沉默", "无言", "——"],
    "多视角": ["视角", "眼中", "看来", "心想", "暗想", "寻思"],
}

ATTENTION_HOOKS: list[str] = ["？", "！", "但", "却", "竟然", "突然", "不料", "谁知", "原来"]

WARMTH_SIGNALS: list[str] = ["烫", "热", "暖", "温", "火", "阳光", "灯光", "炉"]
CARE_SIGNALS: list[str] = [
    "等", "做", "给", "留", "帮", "守", "陪", "护", "照顾", "关心", "担心", "想念", "思念",
]
PAIN_SIGNALS: list[str] = [
    "疼", "痛", "伤", "哭", "血", "死", "泪", "恨", "绝望", "崩溃", "挣扎",
]

GENRE_CONTRACT: dict[str, list[str]] = {
    "玄幻": ["修炼", "突破", "法宝", "丹药", "战斗", "功法", "金手指"],
    "都市": ["身份", "逆袭", "打脸", "冲突", "势力", "美女", "金钱"],
    "悬疑": ["谜题", "线索", "死者", "秘密", "嫌疑人", "转折", "伏笔"],
    "科幻": ["科技", "设定", "冲突", "概念", "未来", "危机", "方案"],
    "仙侠": ["修炼", "飞升", "剑", "宗门", "历练", "机缘", "天劫"],
    "穿越": ["穿越", "系统", "身份", "金手指", "碾压", "打脸", "优势"],
    "言情": ["相遇", "冲突", "心动", "误会", "男主", "女主", "告白"],
    "恐怖": ["恐怖", "诡异", "死亡", "规则", "逃生", "怪物", "诅咒"],
}
GENRE_CONTRACT_DEFAULT: list[str] = ["主角", "冲突", "目标", "反转", "成长"]

TIME_MARKERS: dict[str, float] = {
    "秒": 0.016667,
    "分钟": 1,
    "分": 1,
    "小时": 60,
    "时辰": 120,
    "天": 1440,
    "日": 1440,
    "周": 10080,
    "星期": 10080,
    "月": 43200,
    "年": 525600,
    "载": 525600,
}


# ═══════════════ Voice Profile API ═══════════════
