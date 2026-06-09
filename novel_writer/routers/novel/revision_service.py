"""Background services for chapter revision and polish workflows."""

from __future__ import annotations

import json
import copy
import random
import re
import time
from collections import Counter
from dataclasses import asdict
from pathlib import Path

from novel_writer.routers.deps import get_db, get_gen_state
from novel_writer.routers.novel.chapter_metadata import update_chapter_content
from novel_writer.routers.novel.generation_support_service import build_creation_brief


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


def _generator_for(novel_id: str):
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
    return Generator(cfg)


def _safe_json_list(value):
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


def _load_state(novel_id: str):
    from novel_writer.story_state import ChapterMeta, Character, Plot, StoryState, World

    db = get_db()
    novel = db.get_novel(novel_id)
    if not novel:
        return None
    active_foreshadowing = []
    if hasattr(db, "get_all_foreshadowing"):
        active_foreshadowing = [
            thread.get("description", "")
            for thread in db.get_all_foreshadowing(novel_id)
            if thread.get("description") and thread.get("status", "active") in ("active", "overdue")
        ]
    elif hasattr(db, "get_active_foreshadowing"):
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
        novel_id=novel_id,
        title=novel["title"],
        author=novel["author"],
        synopsis=novel.get("synopsis", ""),
        genre=novel["genre"],
        world=World(
            name=novel.get("world_name", ""),
            era=novel.get("world_era", ""),
            geography=novel.get("world_geo", ""),
            power_system=novel.get("power_system", ""),
        ),
        characters=[
            Character(
                id=character["char_key"],
                name=character["name"],
                role=character["role"],
                personality=character.get("personality", ""),
                background=character.get("background", ""),
                current_power_level=character.get("power_level", ""),
                voice_avg_sentence_len=voice.get("avg_sentence_len", 0.0),
                voice_question_ratio=voice.get("question_ratio", 0.0),
                voice_common_words=voice.get("common_words", []),
                voice_sample=voice.get("sample", ""),
            )
            for character in novel.get("characters", [])
            for voice in [json.loads(character.get("voice_data", "{}")) if character.get("voice_data") else {}]
        ],
        plot=Plot(
            premise=novel.get("synopsis", ""),
            main_arc=novel.get("main_arc", ""),
            current_arc=novel.get("current_arc", "开篇"),
            arc_chapter_start=novel.get("arc_chapter_start", 1),
            next_plot_points=next_plot_points,
            foreshadowing=active_foreshadowing,
        ),
        chapters=[
            ChapterMeta(
                number=chapter["number"],
                title=chapter["title"],
                word_count=chapter["word_count"],
                summary=chapter.get("summary", ""),
                content=chapter.get("content", ""),
                ending_hook=chapter.get("ending_hook", ""),
                key_events=_safe_json_list(chapter.get("key_events")),
                revelations=_safe_json_list(chapter.get("revelations")),
                narrative_facts=_safe_json_list(chapter.get("narrative_facts")),
                generated_at=chapter.get("generated_at", ""),
            )
            for chapter in novel.get("chapters", [])
            if chapter.get("word_count", 0) > 0
        ],
    )


def run_revise_opening(novel_id: str) -> None:
    """Background: revise opening chapters with full-book knowledge."""
    try:
        db = get_db()
        _set_status(novel_id, "revising", "正在基于结局重写前3章…")
        gen = _generator_for(novel_id)
        state = _load_state(novel_id)
        if not state or state.total_chapters < 5:
            _set_status(novel_id, "error", "至少需要5章才能回修开头")
            return
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

        revised = gen.revise_opening(state, target_chapters=3, style=style)
        skipped = 0
        for chapter in revised:
            original_chapter = db.get_chapter(novel_id, chapter.number)
            original = original_chapter.get("content", "") if original_chapter else ""
            rejection = _rewrite_acceptance_error(original, chapter.content, operation="开头回修")
            if rejection:
                skipped += 1
                db.log(novel_id, "chapter.revision_rejected", {"chapter": chapter.number, "reason": rejection})
                continue
            update_chapter_content(db, novel_id, chapter.number, chapter.content, refresh_story_bible=True)
            db.log(novel_id, "chapter.revised", {"chapter": chapter.number})
        suffix = f"，跳过{skipped}章异常输出" if skipped else ""
        _set_status(novel_id, "complete", f"前{len(revised) - skipped}章回修完成{suffix}")
    except Exception as exc:
        _set_status(novel_id, "error", str(exc)[:200])


def run_final_polish(novel_id: str) -> None:
    """Background: final full-book polish before publication."""
    db = get_db()
    gen = _generator_for(novel_id)
    novel = db.get_novel(novel_id)
    generated_chapters = [
        chapter for chapter in novel.get("chapters", []) if chapter.get("word_count", 0) > 0
    ] if novel else []
    if not generated_chapters:
        return

    total = len(generated_chapters)
    _set_status(novel_id, "polishing", f"终极打磨 {total}章…")

    first_chapter = generated_chapters[0]
    last_chapter = generated_chapters[-1]
    _set_status(novel_id, "polishing", "检查首尾呼应…")
    echo_check = gen._call_llm_with_retry(
        [
            {"role": "system", "content": "分析第一章和最后一章是否形成呼应。"},
            {
                "role": "user",
                "content": (
                    f"第一章：{first_chapter.get('content', '')[:500]}\n"
                    f"最后一章：{last_chapter.get('content', '')[:500]}\n"
                    "是否有画面、对话或主题的呼应？有的话描述，没有的话建议3处可以加入的呼应。"
                ),
            },
        ],
        max_tokens=512,
    )
    db.log(novel_id, "final_polish.echo", {"result": echo_check[:200]})

    _set_status(novel_id, "polishing", "扫描全本重复短语…")
    all_text = " ".join(chapter.get("content", "") for chapter in generated_chapters)
    phrases = re.findall(r"[一-鿿]{2,4}", all_text[:50000])
    frequency = Counter(phrases)
    overused = [
        (phrase, count)
        for phrase, count in frequency.most_common(20)
        if count > len(generated_chapters) * 3
    ]
    if overused:
        db.log(novel_id, "final_polish.repetition", {"phrases": str(overused[:5])})

    _set_status(novel_id, "complete", f"终极打磨完成({total}章)")


def run_polish(novel_id: str) -> None:
    """Background: polish all generated chapters."""
    db = get_db()
    gen = _generator_for(novel_id)
    novel = db.get_novel(novel_id)
    generated_chapters = [
        chapter for chapter in novel.get("chapters", []) if chapter.get("word_count", 0) > 0
    ] if novel else []
    if not generated_chapters:
        _set_status(novel_id, "error", "No chapters to polish")
        return

    lengths = [chapter.get("word_count", 0) for chapter in generated_chapters]
    avg_len = sum(lengths) / len(lengths)
    outliers = [
        (chapter["number"], chapter["word_count"])
        for chapter in generated_chapters
        if abs(chapter["word_count"] - avg_len) > avg_len * 0.5
    ]
    if outliers:
        print(f"[POLISH] ⚠️ Length outliers: {outliers}")
        db.log(novel_id, "polish.outliers", {"chapters": [str(outlier) for outlier in outliers]})

    total = len(generated_chapters)
    polish_prompt = """精修以下章节——只做微调，不改剧情：

1. 修正角色称呼不一致（如果同一角色在本章内被叫了不同名字，统一）
2. 平滑场景切换处的过渡（如果两段之间跳得太快，加半句过渡）
3. 删除本章内重复出现的形容词/比喻（同一意象出现≥2次，只保留最好的那一次）
4. 检查章节标题和正文内容是否匹配——如果标题暗示的内容没出现，则调整标题
5. 不得删除或淡化主角主动选择、拒绝、承担、冒险、伤口、代价、后果、身份暴露、关系裂痕、后续麻烦

输出修改后的完整章节正文。保持字数±5%。"""

    for index, chapter in enumerate(generated_chapters):
        _set_status(novel_id, "polishing", f"精修第{chapter['number']}章 ({index + 1}/{total})...")
        content = chapter.get("content", "")
        if not content:
            continue
        polished = gen._call_llm_with_retry(
            [
                {"role": "system", "content": "你是专业校对编辑。只做微调，不改剧情，不删除主角主动选择、代价、风险或后果。"},
                {"role": "user", "content": f"{polish_prompt}\n\n原稿：\n{content}"},
            ],
            max_tokens=8192,
        )
        rejection = _rewrite_acceptance_error(content, polished, operation="精修")
        if rejection:
            db.log(novel_id, "polish.rejected", {"chapter": chapter["number"], "reason": rejection})
            continue
        db.save_chapter_version(novel_id, chapter["number"], content, "pre-polish")
        update_chapter_content(db, novel_id, chapter["number"], polished.strip(), refresh_story_bible=True)

    _set_status(novel_id, "complete", f"全本精修完成({total}章)")


def run_evolve(novel_id: str) -> None:
    """Background: iteratively regenerate opening chapters until classic potential improves."""
    db = get_db()
    try:
        from novel_writer.generator import GENRE_TO_STYLE, STYLE_POOL, WRITER_VOICES

        gen = _generator_for(novel_id)
        novel = db.get_novel(novel_id)
        max_iter = 3
        timeout_per_iter = 600
        voices = list(WRITER_VOICES.keys())
        random.shuffle(voices)
        best_avg = 0
        best_iter = 0
        tried_voices: list[str] = []

        for iteration in range(1, max_iter + 1):
            start_time = time.time()
            _set_status(novel_id, "evolving", f"第{iteration}/{max_iter}次迭代（最多{max_iter}次，约¥0.10/次）...")

            available = [voice for voice in voices if voice not in tried_voices] or voices
            voice = random.choice(available)
            tried_voices.append(voice)

            with db.conn() as conn:
                conn.execute("DELETE FROM chapters WHERE novel_id=? AND word_count>0", (novel_id,))

            style_key = GENRE_TO_STYLE.get(novel.get("genre", "玄幻"), "玄幻")
            style = copy.copy(STYLE_POOL.get(style_key)) if STYLE_POOL.get(style_key) else None
            if style:
                style.novel_id = novel_id
                style.writer_voice = voice
                db.save_style_profile(novel_id, asdict(style))

            state = _load_state(novel_id)
            if state:
                author_input = build_creation_brief(db, novel_id)
                for chapter_num in range(1, 6):
                    with db.conn() as conn:
                        existing = conn.execute(
                            "SELECT id FROM chapters WHERE novel_id=? AND number=?",
                            (novel_id, chapter_num),
                        ).fetchone()
                        if not existing:
                            conn.execute(
                                "INSERT INTO chapters (novel_id,number,title,summary,word_count) VALUES (?,?,?,'',0)",
                                (novel_id, chapter_num, f"第{chapter_num}章"),
                            )
                gen.generate_chapters(state, n=5, style=style, author_input=author_input)

            elapsed = time.time() - start_time
            if elapsed > timeout_per_iter:
                db.log(novel_id, "evolve.timeout", {"iteration": iteration, "elapsed": int(elapsed)})
                _set_status(novel_id, "evolving", f"第{iteration}次超时({elapsed:.0f}s)——跳过")
                continue

            novel_after = db.get_novel(novel_id)
            generated = [
                chapter for chapter in novel_after.get("chapters", []) if chapter.get("word_count", 0) > 0
            ]
            avg_q = 0
            if len(generated) >= 5:
                first5 = generated[:5]
                avg_q = sum(chapter.get("quality_score", 0) for chapter in first5) / 5
                db.log(
                    novel_id,
                    "evolve.iteration",
                    {"iteration": iteration, "voice": voice, "avg_q": avg_q, "cost_est": "~$0.10"},
                )

                if avg_q > best_avg:
                    best_avg = avg_q
                    best_iter = iteration

                if avg_q >= 0.78:
                    _set_status(novel_id, "complete", f"第{iteration}次迭代达标！声音={voice} 均分={avg_q:.2f} 花费~$0.{iteration}0")
                    return

                if iteration >= 2 and avg_q < best_avg - 0.05:
                    db.log(novel_id, "evolve.dead_end", {"iteration": iteration, "avg_q": avg_q, "best": best_avg})
                    _set_status(novel_id, "complete", f"质量下降({avg_q:.2f}<{best_avg:.2f})——提前终止，保留第{best_iter}次版本")
                    return

            _set_status(novel_id, "evolving", f"第{iteration}次未达标({avg_q:.2f})，换声音...")

        _set_status(novel_id, "complete", f"完成{max_iter}次迭代，最优=第{best_iter}次(均分{best_avg:.2f})，总花费~$0.{max_iter * 10}")
    except Exception as exc:
        _set_status(novel_id, "error", str(exc)[:200])


def run_ab_test(synopsis: str, genre: str, voices: list[str] | None = None) -> None:
    """Background: run A/B test across multiple writer voices."""
    db = get_db()
    gen = _generator_for(None)
    result = gen.ab_test_opening(synopsis, genre, voices)
    log_dir = Path("data") / "ab_tests"
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / f"ab_{int(time.time())}.json"
    log_file.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    best = result.get("best_voice", "?")
    best_quality = result.get("best_chapter", {}).get("quality", 0)
    db.log("ab_test", "ab.completed", {"best": best, "quality": best_quality})
    print(f"[AB] Best voice: {best} (Q={best_quality}) -> saved to {log_file}")


def run_humanize(novel_id: str, chapter_num: int) -> None:
    """Background: deep-humanize a chapter."""
    try:
        db = get_db()
        _set_status(novel_id, "humanizing", f"正在去AI味第{chapter_num}章…")
        gen = _generator_for(novel_id)
        chapter = db.get_chapter(novel_id, chapter_num)
        if not chapter:
            raise RuntimeError("Chapter not found")
        content = chapter.get("content", "")
        if not content:
            raise RuntimeError("Chapter content is empty")
        humanized = gen.humanize(content)
        rejection = _rewrite_acceptance_error(content, humanized, operation="去AI味")
        if rejection:
            raise ValueError(rejection)
        db.save_chapter_version(novel_id, chapter_num, content, "pre-humanize")
        update_chapter_content(db, novel_id, chapter_num, humanized.strip(), refresh_story_bible=True)
        db.log(novel_id, "chapter.humanized", {"chapter": chapter_num})
        _set_status(novel_id, "complete", f"第{chapter_num}章去AI味完成")
    except Exception as exc:
        _set_status(novel_id, "error", str(exc)[:200])


def _rewrite_acceptance_error(original: str, revised: str | None, *, operation: str) -> str:
    """Return a rejection reason when a chapter rewrite should not overwrite the draft."""
    if not isinstance(revised, str) or not revised.strip():
        return f"{operation}失败：模型返回空正文，已保留原章"

    revised_text = revised.strip()
    original_text = (original or "").strip()
    original_len = len(original_text)
    revised_len = len(revised_text)

    if original_len and revised_len < max(20, int(original_len * 0.55)):
        return f"{operation}失败：模型返回内容过短，已保留原章"
    if original_len >= 80 and revised_len > int(original_len * 1.8):
        return f"{operation}失败：模型返回内容异常变长，已保留原章"

    opening = revised_text[:160].lstrip()
    explanation_pattern = re.compile(
        r"^(好的|当然|可以|以下是|下面是|这是|我已|已根据|根据你的|修改说明|修订说明|改动说明|说明[:：])"
    )
    if explanation_pattern.search(opening):
        return f"{operation}失败：模型返回了说明文字而不是章节正文，已保留原章"
    if re.search(r"(修改如下|修订如下|改动如下|以下为修订|以下为修改)", opening):
        return f"{operation}失败：模型返回了说明文字而不是章节正文，已保留原章"
    if "```" in revised_text[:400] or re.search(r"^#{1,3}\s*(修改|修订|说明)", opening, re.M):
        return f"{operation}失败：模型返回了非正文格式，已保留原章"

    compact_original = re.sub(r"\s+", "", original_text)
    compact_revised = re.sub(r"\s+", "", revised_text)
    if len(compact_original) >= 80 and len(compact_revised) >= 80:
        anchors = {
            compact_original[index : index + 12]
            for index in range(0, max(1, len(compact_original) - 11), 8)
            if len(compact_original[index : index + 12]) == 12
        }
        if anchors:
            kept = sum(1 for anchor in anchors if anchor in compact_revised)
            if kept / len(anchors) < 0.08:
                return f"{operation}失败：模型输出与原章关联过低，已保留原章"

    return ""


def run_revise_chapter(novel_id: str, chapter_num: int, critique: str) -> None:
    """Background: revise a chapter based on natural-language critique."""
    try:
        db = get_db()
        _set_status(novel_id, "revising", f"正在根据批评重写第{chapter_num}章…")
        gen = _generator_for(novel_id)
        state = _load_state(novel_id)
        chapter = db.get_chapter(novel_id, chapter_num)
        if not chapter or not state:
            raise RuntimeError("Chapter or state not found")
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

        original = chapter.get("content", "")
        revised = gen.revise_chapter(original, critique, state, style)
        rejection = _rewrite_acceptance_error(original, revised, operation="修订")
        if rejection:
            raise ValueError(rejection)
        db.save_chapter_version(novel_id, chapter_num, original, "pre-critique-revision")
        update_chapter_content(db, novel_id, chapter_num, revised.strip(), refresh_story_bible=True)
        db.log(
            novel_id,
            "chapter.revised_by_critique",
            {"chapter": chapter_num, "critique": critique[:100]},
        )
        _set_status(novel_id, "complete", f"第{chapter_num}章已按批评重写")
    except Exception as exc:
        _set_status(novel_id, "error", str(exc)[:200])
