"""Analytics, dashboards, timelines, costs, and lightweight insight endpoints."""

from __future__ import annotations

import html
from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, HTTPException

from novel_writer.routers.deps import get_db

router = APIRouter(tags=["analytics"])


def _db():
    return get_db()


def _get_provider(novel_id: str | None = None):
    db = _db()
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


def _generated_chapters(novel: dict) -> list[dict]:
    return [chapter for chapter in novel.get("chapters", []) if chapter.get("word_count", 0) > 0]


@router.post("/api/novels/{novel_id}/optimize-prompt")
def optimize_prompt(novel_id: str) -> dict:
    """Analyze performance and auto-tune StyleProfile parameters."""
    db = _db()
    novel = db.get_novel(novel_id)
    if not novel:
        raise HTTPException(404, "Novel not found")

    analytics = compute_analytics(novel_id)
    chapters = analytics.get("chapters", [])
    adjustments = []

    from novel_writer.generator import StyleProfile, _get_style_for_genre

    style_data = db.get_style_profile(novel_id)
    if style_data:
        style = StyleProfile(**{key: value for key, value in style_data.items() if key in StyleProfile.__dataclass_fields__})
    else:
        style = _get_style_for_genre(novel.get("genre", "玄幻"))

    old_profile = asdict(style)

    if chapters:
        recent = chapters[-5:]
        avg_hook = sum(chapter.get("hook_score", 0) for chapter in recent) / len(recent)
        if avg_hook < 0.4:
            old_hook = style.hook_interval_words
            style.hook_interval_words = max(400, style.hook_interval_words - 100)
            adjustments.append(f"钩子密度+{int((1 - old_hook / style.hook_interval_words) * 100)}%（{old_hook}→{style.hook_interval_words}字/钩）")
            if "结尾钩子前加一句角色内心独白制造悬念" not in style.special_rules:
                style.special_rules.append("结尾钩子前加一句角色内心独白制造悬念")

        avg_words = sum(chapter["word_count"] for chapter in recent) / len(recent)
        if avg_words < style.target_word_count[0]:
            old_min = style.target_word_count[0]
            style.target_word_count = (max(1200, style.target_word_count[0] - 200), style.target_word_count[1])
            adjustments.append(f"目标字数下限下调 {old_min - style.target_word_count[0]} 字")

        retentions = [chapter.get("retention_to_next", 0) for chapter in chapters[-4:-1] if chapter.get("retention_to_next", 0) > 0]
        if len(retentions) >= 3 and all(retention < 0.7 for retention in retentions):
            if style.pace_pattern != "三强一缓":
                style.pace_pattern = "三强一缓"
                adjustments.append("节奏切换为三强一缓")
            if "本章必须发生一个改变故事走向的事件" not in style.special_rules:
                style.special_rules.append("本章必须发生一个改变故事走向的事件（新角色登场/旧角色死亡/秘密揭露）")

        if len(chapters) >= 5:
            missing_types = [
                climax_type
                for climax_type in style.climax_types
                if not any(climax_type in (chapter.get("title", "") + chapter.get("ending_hook", "")) for chapter in recent)
            ]
            if missing_types:
                adjustments.append(f"爽点类型'{missing_types[0]}'已连续多章未出现")
                if f"本章应包含{missing_types[0]}类型事件" not in style.special_rules:
                    style.special_rules.append(f"本章应包含{missing_types[0]}类型事件")

    try:
        db.save_style_profile(novel_id, asdict(style))
    except Exception:
        db.save_style_profile(novel_id, style.__dict__)

    return {
        "adjustments": adjustments,
        "old_profile": old_profile,
        "new_profile": asdict(style),
        "analytics_summary": {
            "total_chapters": len(chapters),
            "avg_quality": round(sum(chapter["quality_score"] for chapter in chapters[-5:]) / min(5, len(chapters)), 2) if chapters else 0,
            "drop_off_count": len(analytics.get("drop_off_points", [])),
        },
    }


@router.get("/api/novels/{novel_id}/reading-stats")
def reading_stats(novel_id: str) -> dict:
    """Estimated reading time, readability, and chapter length distribution."""
    novel = _db().get_novel(novel_id)
    if not novel:
        raise HTTPException(404)
    chapters = _generated_chapters(novel)
    if not chapters:
        return {"error": "No chapters"}
    total = sum(chapter["word_count"] for chapter in chapters)
    lengths = [chapter["word_count"] for chapter in chapters]
    avg_len = sum(lengths) / len(lengths)
    reading_minutes = total / 400
    variance = sum((length - avg_len) ** 2 for length in lengths) / len(lengths)
    std_dev = variance**0.5
    consistency = "优秀" if std_dev < avg_len * 0.3 else "良好" if std_dev < avg_len * 0.5 else "需改善"
    return {
        "total_words": total,
        "chapters": len(chapters),
        "avg_chapter_length": round(avg_len),
        "std_dev": round(std_dev),
        "consistency": consistency,
        "estimated_reading_time": f"{int(reading_minutes // 60)}小时{int(reading_minutes % 60)}分钟",
        "longest": f"第{lengths.index(max(lengths)) + 1}章({max(lengths)}字)",
        "shortest": f"第{lengths.index(min(lengths)) + 1}章({min(lengths)}字)",
    }


@router.post("/api/novels/{novel_id}/compare")
def compare_chapters(novel_id: str, data: dict) -> dict:
    """Compare two chapter versions or chapter snapshots."""
    db = _db()
    ch1_num = data.get("ch1", 0)
    ch2_num = data.get("ch2", 0)
    if not ch1_num:
        raise HTTPException(400, "ch1 required")
    ch1 = db.get_chapter(novel_id, ch1_num)
    if not ch1:
        raise HTTPException(404, f"Chapter {ch1_num} not found")
    if ch2_num:
        ch2 = db.get_chapter(novel_id, ch2_num)
    else:
        versions = db.get_chapter_versions(novel_id, ch1_num)
        if len(versions) >= 2:
            ch2 = {
                "title": ch1["title"],
                "word_count": versions[-1]["word_count"],
                "content": db.get_chapter_version_content(versions[-1]["id"]),
            }
        else:
            ch2 = {"title": ch1["title"], "word_count": ch1["word_count"], "content": ch1.get("content", "")}
    return {
        "left": {
            "number": ch1_num,
            "title": ch1["title"],
            "words": ch1["word_count"],
            "preview": (ch1.get("content", "") or "")[:300],
        },
        "right": {
            "number": ch2_num or f"v{len(db.get_chapter_versions(novel_id, ch1_num))}",
            "title": ch2.get("title", ""),
            "words": ch2.get("word_count", 0),
            "preview": (ch2.get("content", "") or "")[:300],
        },
    }


@router.get("/api/novels/{novel_id}/timeline")
def book_timeline(novel_id: str) -> dict:
    """Creative timeline for a book."""
    db = _db()
    novel = db.get_novel(novel_id)
    if not novel:
        raise HTTPException(404)
    timeline = [
        {
            "event": "created",
            "time": novel.get("created_at", ""),
            "detail": f"创建《{novel['title']}》({novel['genre']})",
        }
    ]
    for chapter in _generated_chapters(novel):
        versions = db.get_chapter_versions(novel_id, chapter["number"])
        timeline.append(
            {
                "event": "chapter_generated",
                "chapter": chapter["number"],
                "title": chapter["title"],
                "words": chapter["word_count"],
                "quality": chapter.get("quality_score", 0),
                "time": chapter.get("generated_at", ""),
                "revisions": len(versions),
            }
        )
    return {"novel_id": novel_id, "title": novel["title"], "timeline": timeline}


@router.get("/api/novels/{novel_id}/packaging")
def generate_packaging(novel_id: str) -> dict:
    """Generate reader-facing blurb, title candidates, and cover concept."""
    db = _db()
    novel = db.get_novel(novel_id)
    if not novel:
        raise HTTPException(404)
    chapters = _generated_chapters(novel)
    synopsis = novel.get("synopsis", "")
    titles = [chapter.get("title", "") for chapter in chapters[:5]]

    from novel_writer.config import Config
    from novel_writer.generator import Generator

    provider = _get_provider(novel_id)
    cfg = Config(
        openai_api_key=provider.get("api_key", ""),
        openai_base_url=provider.get("base_url", ""),
        model=provider.get("models", "deepseek-v4-pro")[0] if provider.get("models") else "gpt-4o",
    )
    generator = Generator(cfg)

    blurb = ""
    try:
        style = db.get_style_profile(novel_id)
        central_question = style.get("central_question", "") if style else ""
        blurb = generator._call_llm_with_retry(
            [
                {"role": "system", "content": "你是出版编辑，写简介要让人3秒内想点开。"},
                {
                    "role": "user",
                    "content": f"""你是顶级出版编辑。为以下小说写一段200字以内的简介，让读者在3秒内想点开看。
简介不能剧透关键转折，但要暗示核心冲突。要有节奏感——短句+悬念。

书名：{novel.get('title', '')}
设定：{synopsis[:300]}
核心追问：{central_question}
已有章节：{'、'.join(titles)}

简介：""",
                },
            ],
            max_tokens=300,
        )
    except Exception:
        pass

    titles_raw = ""
    try:
        titles_raw = generator._call_llm_with_retry(
            [
                {"role": "system", "content": "生成5个2-6字的小说书名。有意象感，不拗口。只输出书名。"},
                {"role": "user", "content": f"简介：{synopsis}\n已有章名：{'、'.join(titles[:5])}"},
            ],
            max_tokens=128,
        )
    except Exception:
        pass

    cover_prompt = ""
    try:
        cover_prompt = generator._call_llm_with_retry(
            [
                {"role": "system", "content": "你是封面设计师。用一段英文描述这本书的封面设计方案，用于AI绘图工具。"},
                {
                    "role": "user",
                    "content": f"""书名：{novel.get('title', '')}
简介：{synopsis[:200]}
风格：{novel.get('genre', '')}

请输出英文封面描述（用于Midjourney/DALL-E），包含：色调、构图、关键元素、情绪氛围。50-100 words。""",
                },
            ],
            max_tokens=200,
        )
    except Exception:
        pass

    return {
        "blurb": blurb.strip() if blurb else "",
        "title_candidates": [
            title.strip() for title in titles_raw.split("\n") if title.strip() and 2 <= len(title.strip()) <= 10
        ][:5]
        if titles_raw
        else [],
        "cover_concept": cover_prompt.strip() if cover_prompt else "",
        "stats": {"chapters": len(chapters), "words": novel.get("total_words", 0)},
    }


@router.get("/api/analytics-dashboard")
def analytics_dashboard() -> dict:
    """Global analytics dashboard."""
    db = _db()
    novels = db.list_novels()
    costs = db.get_cost_summary()
    novel_stats = []
    for novel in novels:
        chapters = novel.get("chapters", [])
        generated = [chapter for chapter in chapters if chapter.get("word_count", 0) > 0]
        scores = [chapter.get("quality_score", 0) for chapter in generated if chapter.get("quality_score")]
        novel_stats.append(
            {
                "id": novel["id"],
                "title": novel["title"],
                "genre": novel.get("genre", "?"),
                "chapters": len(generated),
                "words": novel.get("total_words", 0),
                "avg_quality": round(sum(scores) / len(scores), 2) if scores else 0,
                "status": "活跃" if generated else "空",
            }
        )
    return {
        "global": {
            "novels": len(novels),
            "chapters": sum(novel.get("total_chapters", 0) for novel in novels),
            "words": sum(novel.get("total_words", 0) for novel in novels),
            "total_cost": round(costs.get("total_cost", 0), 4),
            "total_llm_calls": costs.get("total_calls", 0),
        },
        "novels": sorted(novel_stats, key=lambda item: item["words"], reverse=True),
    }


@router.get("/api/publishing-dashboard")
def publishing_dashboard() -> dict:
    """Publishing status dashboard."""
    db = _db()
    dashboard = []
    for novel in db.list_novels():
        generated = [chapter for chapter in novel.get("chapters", []) if chapter.get("word_count", 0) > 0]
        published = []
        failed = []
        with db.conn() as conn:
            for chapter in generated:
                chapter_id = chapter.get("id")
                if chapter_id is None:
                    row = conn.execute(
                        "SELECT id FROM chapters WHERE novel_id=? AND number=?",
                        (novel["id"], chapter["number"]),
                    ).fetchone()
                    chapter_id = row["id"] if row else None
                if chapter_id is None:
                    continue
                record = conn.execute(
                    "SELECT success,error FROM publish_records WHERE chapter_id=? ORDER BY id DESC LIMIT 1",
                    (chapter_id,),
                ).fetchone()
                if record and record["success"]:
                    published.append(chapter["number"])
                elif record:
                    failed.append({"chapter": chapter["number"], "error": record["error"] or "unknown"})
        dashboard.append(
            {
                "novel_id": novel["id"],
                "title": novel["title"],
                "total": len(generated),
                "published": sorted(published),
                "pending": [chapter["number"] for chapter in generated if chapter["number"] not in published],
                "failed": failed,
            }
        )
    return {"novels": dashboard}


@router.get("/api/daily")
def daily_digest() -> dict:
    """Daily system digest."""
    db = _db()
    novels = db.list_novels()
    costs = db.get_cost_summary()
    logs = db.get_logs(20)
    today_logs = [log for log in logs if "today" in str(log.get("created_at", ""))[:10] or True][:5]
    return {
        "novels": len(novels),
        "total_chapters": sum(novel.get("total_chapters", 0) for novel in novels),
        "total_words": sum(novel.get("total_words", 0) for novel in novels),
        "total_cost": round(costs.get("total_cost", 0), 4),
        "total_llm_calls": costs.get("total_calls", 0),
        "recent_events": [
            {"event": log.get("event", ""), "detail": (log.get("detail", "") or "")[:80]} for log in today_logs
        ],
    }


@router.get("/api/novels/{novel_id}/diffs")
def chapter_diffs(novel_id: str) -> dict:
    """Chapter revision history summary."""
    db = _db()
    novel = db.get_novel(novel_id)
    if not novel:
        raise HTTPException(404)
    diffs = []
    for chapter in _generated_chapters(novel):
        versions = db.get_chapter_versions(novel_id, chapter["number"])
        if len(versions) >= 2:
            diffs.append(
                {
                    "chapter": chapter["number"],
                    "title": chapter["title"],
                    "original_words": versions[-1]["word_count"],
                    "revised_words": versions[0]["word_count"],
                    "versions": len(versions),
                }
            )
    return {"diffs": diffs}


@router.get("/api/novels/{novel_id}/ask")
def ask_novel(novel_id: str, q: str = "") -> dict:
    """Ask a question about the novel using chapter-summary retrieval."""
    if not q:
        raise HTTPException(400, "q required")
    from novel_writer.config import Config
    from novel_writer.generator import Generator

    provider = _get_provider(novel_id)
    cfg = Config(
        openai_api_key=provider.get("api_key", ""),
        openai_base_url=provider.get("base_url", ""),
        model=provider.get("models", "deepseek-v4-pro")[0] if provider.get("models") else "gpt-4o",
    )
    generator = Generator(cfg)
    context = generator.retrieve_relevant_context(q, novel_id, top_k=5)
    if not context:
        return {"answer": "未找到相关信息", "sources": []}
    ctx_text = "\n".join(
        f"第{item.get('chapter_number', '?')}章：{item.get('chunk_text', '')[:300]}" for item in context
    )
    answer = generator._call_llm_with_retry(
        [
            {"role": "system", "content": "你正在回答关于你自己写的小说的问题。基于以下章节内容回答。如果信息不足，诚实说不知道。"},
            {"role": "user", "content": f"问题：{q}\n\n相关章节：\n{ctx_text[:3000]}\n\n回答："},
        ],
        max_tokens=512,
    )
    return {"answer": answer, "sources": [{"chapter": item.get("chapter_number"), "title": item.get("title")} for item in context]}


@router.get("/api/insights")
def cross_novel_insights() -> dict:
    """Cross-novel adaptive learning summary."""
    db = _db()
    novels = db.list_novels()
    insights: dict[str, Any] = {
        "total_novels": len(novels),
        "total_chapters": 0,
        "total_words": 0,
        "best_genres": [],
        "avg_quality_by_genre": {},
        "cost_summary": db.get_cost_summary(),
    }
    genre_scores: dict[str, list[float]] = {}
    for novel in novels:
        generated = [chapter for chapter in novel.get("chapters", []) if chapter.get("word_count", 0) > 0]
        insights["total_chapters"] += len(generated)
        insights["total_words"] += sum(chapter.get("word_count", 0) for chapter in generated)
        genre = novel.get("genre", "其他")
        scores = [chapter.get("quality_score", 0) for chapter in generated if chapter.get("quality_score")]
        if scores:
            genre_scores.setdefault(genre, []).extend(scores)
    for genre, scores in genre_scores.items():
        insights["avg_quality_by_genre"][genre] = round(sum(scores) / len(scores), 2)
    best = max(genre_scores.items(), key=lambda item: sum(item[1]) / len(item[1])) if genre_scores else ("N/A", [])
    insights["best_genre"] = best[0]
    insights["best_genre_avg"] = round(sum(best[1]) / len(best[1]), 2) if best[1] else 0
    insights["recommendation"] = f"当前最优体裁: {best[0]}(均分{insights['best_genre_avg']})。建议新书优先选择此体裁。"
    return insights


def compute_analytics(novel_id: str) -> dict:
    """Compute retention curve and insights from performance_logs + chapters."""
    db = _db()
    chapters_data = []
    with db.conn() as conn:
        rows = conn.execute(
            """
            SELECT c.number, c.title, c.word_count, c.quality_score,
                   c.ending_hook,
                   COALESCE(p.views, 0) as views,
                   COALESCE(p.comments, 0) as comments
            FROM chapters c
            LEFT JOIN performance_logs p ON p.novel_id = c.novel_id AND p.chapter_number = c.number
            WHERE c.novel_id = ? AND c.word_count > 0
            ORDER BY c.number
            """,
            (novel_id,),
        ).fetchall()

    if not rows:
        return {"chapters": [], "drop_off_points": [], "insights": []}

    hook_keywords = ["？", "！", "突然", "竟然", "难道", "什么", "怎么", "为何", "……"]
    for row in rows:
        hook = row["ending_hook"] or ""
        hook_score = sum(1 for keyword in hook_keywords if keyword in hook) / max(len(hook_keywords), 1)
        chapters_data.append(
            {
                "number": row["number"],
                "title": row["title"],
                "word_count": row["word_count"],
                "quality_score": round(row["quality_score"] or 0, 2),
                "hook_score": round(min(hook_score * 2, 1.0), 2),
                "views": row["views"] or 0,
                "comments": row["comments"] or 0,
            }
        )

    drop_off_points = []
    quality_scores = []
    retention_rates = []
    for index in range(len(chapters_data) - 1):
        current = chapters_data[index]
        next_chapter = chapters_data[index + 1]
        current_views = max(current["views"], 1)
        next_views = next_chapter["views"]
        retention = round(next_views / current_views, 2) if current_views > 0 else 0
        current["retention_to_next"] = retention
        if next_views > 0 and retention < 0.5:
            drop_off_points.append(next_chapter["number"])
        if next_views > 0:
            quality_scores.append(next_chapter["quality_score"])
            retention_rates.append(retention)

    correlation = 0
    if len(quality_scores) >= 3:
        n = len(quality_scores)
        mean_q = sum(quality_scores) / n
        mean_r = sum(retention_rates) / n
        cov = sum((quality_scores[i] - mean_q) * (retention_rates[i] - mean_r) for i in range(n))
        var_q = sum((score - mean_q) ** 2 for score in quality_scores)
        var_r = sum((rate - mean_r) ** 2 for rate in retention_rates)
        if var_q > 0 and var_r > 0:
            correlation = round(cov / ((var_q * var_r) ** 0.5), 2)

    insights = []
    for drop_point in drop_off_points[:5]:
        chapter = next((item for item in chapters_data if item["number"] == drop_point), None)
        if chapter and chapter["quality_score"] < 0.6:
            insights.append(f"第{drop_point}章质量分{chapter['quality_score']}，读者流失——建议重写或加强钩子")
        elif chapter:
            insights.append(f"第{drop_point}章读者流失，质量分{chapter['quality_score']}正常，检查开头是否吸引力不足")

    low_hook_chapters = [chapter for chapter in chapters_data[-5:] if chapter.get("hook_score", 0) < 0.4]
    if low_hook_chapters:
        nums = ", ".join(str(chapter["number"]) for chapter in low_hook_chapters)
        insights.append(f"第{nums}章钩子评分偏低，建议加强结尾悬念")

    short_chapters = [chapter for chapter in chapters_data[-5:] if chapter["word_count"] < 1800]
    if short_chapters:
        nums = ", ".join(str(chapter["number"]) for chapter in short_chapters)
        insights.append(f"第{nums}章字数<1800，章节过短可能导致留存下降")

    if correlation != 0:
        direction = "正" if correlation > 0 else "负"
        insights.append(f"质量分与留存相关系数：{correlation}（{direction}相关）")

    return {
        "chapters": chapters_data,
        "drop_off_points": drop_off_points,
        "quality_vs_retention_correlation": correlation,
        "insights": insights,
    }


@router.get("/api/novels/{novel_id}/analytics")
def get_analytics(novel_id: str) -> dict:
    """Get chapter analytics."""
    if not _db().get_novel(novel_id):
        raise HTTPException(404, "Novel not found")
    return compute_analytics(novel_id)


@router.get("/api/novels/{novel_id}/continuity")
def chapter_continuity(novel_id: str) -> dict:
    """Continuity heatmap between adjacent chapters."""
    novel = _db().get_novel(novel_id)
    if not novel:
        raise HTTPException(404)
    chapters = _generated_chapters(novel)
    if len(chapters) < 2:
        return {"pairs": [], "issues": []}
    pairs = []
    issues = []
    for index in range(len(chapters) - 1):
        current, next_chapter = chapters[index], chapters[index + 1]
        current_end = (current.get("ending_hook") or "")[-100:]
        next_start = (next_chapter.get("content") or "")[:100]
        hook_keywords = ["？", "！", "……", "突然", "竟然", "发现", "知道", "原来"]
        hook_hits = sum(1 for keyword in hook_keywords if keyword in current_end)
        addressed = any(keyword in next_start for keyword in ["？", "！", "但", "可是", "然后", "于是"])
        continuity = min(1.0, hook_hits * 0.3 + (1 if addressed else 0) * 0.5 + 0.2)
        pairs.append(
            {
                "from": current["number"],
                "to": next_chapter["number"],
                "continuity": round(continuity, 2),
                "hook_present": hook_hits > 0,
                "hook_addressed": addressed,
            }
        )
        if continuity < 0.5:
            issues.append(f"第{current['number']}→{next_chapter['number']}章连续性弱({continuity:.2f})")
    return {"pairs": pairs, "issues": issues}


@router.get("/api/costs")
def get_costs(novel_id: str = "") -> dict:
    """Get cost summary for a novel or all novels."""
    return _db().get_cost_summary(novel_id)


@router.get("/api/costs/summary")
def costs_summary() -> dict:
    """Get full cost summary with by-novel breakdown."""
    db = _db()
    summary = db.get_cost_summary()
    if summary["total_cost"] == 0:
        with db.conn() as conn:
            rows = conn.execute(
                """SELECT novel_id, COUNT(*) as chapters,
                SUM(cost) as cost FROM chapters WHERE cost > 0 GROUP BY novel_id"""
            ).fetchall()
            if rows:
                summary["by_novel"] = [dict(row) for row in rows]
                summary["total_cost"] = round(sum(row["cost"] for row in rows), 4)
    return summary


def revenue_estimate(novel_id: str) -> dict:
    """Estimate platform revenue and milestone readiness."""
    novel = _db().get_novel(novel_id)
    if not novel:
        raise HTTPException(404)
    chapters = _generated_chapters(novel)
    words = novel.get("total_words", 0)
    genre = novel.get("genre", "玄幻")
    rpm = {
        "玄幻": 2.5,
        "都市": 3.0,
        "悬疑": 3.5,
        "科幻": 2.8,
        "系统流": 2.2,
        "女频": 3.2,
        "历史": 2.0,
        "游戏": 3.0,
        "官场": 1.8,
    }.get(genre, 2.5)
    milestones = []
    for total, reward in [(20, "签约资格"), (50, "推荐位"), (100, "全勤奖"), (200, "精品频道"), (500, "大神约")]:
        if len(chapters) < total:
            milestones.append({"need": total - len(chapters), "chapters_total": total, "reward": reward})
    daily_readers_low = max(100, words // 500)
    daily_readers_high = daily_readers_low * 5
    monthly_low = round(daily_readers_low * rpm / 1000 * 30, 0)
    monthly_high = round(daily_readers_high * rpm / 1000 * 30, 0)
    return {
        "genre": genre,
        "rpm_per_1k_reads": rpm,
        "words": words,
        "chapters": len(chapters),
        "milestones": milestones,
        "revenue_projection": f"¥{monthly_low}~{monthly_high}/月（基于{words}字、体裁{genre}）",
        "tip": "达到50章后平台推荐位可提升5-10倍曝光",
        "publish_cadence": "建议每日发布2章，保持稳定更新节奏以获得全勤奖励",
    }


@router.get("/api/novels/{novel_id}/acquisition-review")
def acquisition_review(novel_id: str) -> dict:
    """Simulated acquisition-editor assessment."""
    novel = _db().get_novel(novel_id)
    if not novel:
        raise HTTPException(404)
    chapters = _generated_chapters(novel)
    if len(chapters) < 10:
        return {"error": "至少需要10章才能做买断评估"}

    scores = [chapter.get("quality_score", 0) for chapter in chapters]
    avg_quality = sum(scores) / len(scores)
    criteria: dict[str, dict[str, Any]] = {
        "结构完整度": {
            "score": min(10, len(chapters) // 5 + 5),
            "max": 10,
            "note": f"{len(chapters)}章——{'结构完整，弧线清晰' if len(chapters) >= 20 else '章节偏少，故事弧线尚不完整'}",
        },
        "语言成熟度": {
            "score": min(10, int(avg_quality * 12)),
            "max": 10,
            "note": f"均分{avg_quality:.2f}——{'文笔成熟，接近出版级别' if avg_quality >= 0.8 else '文笔达标，可出版但需要编辑加工' if avg_quality >= 0.7 else '需要大幅修改'}",
        },
        "人物塑造": {
            "score": min(10, len(novel.get("characters", [])) * 2 + 3),
            "max": 10,
            "note": f"{len(novel.get('characters', []))}个角色——{'角色群像丰满' if len(novel.get('characters', [])) >= 3 else '建议增加配角深度'}",
        },
        "商业潜力": {
            "score": min(10, 5 + int(novel.get("total_words", 0) / 10000)),
            "max": 10,
            "note": f"{novel.get('total_words', 0)}字——{'已达到商业出版字数' if novel.get('total_words', 0) >= 50000 else '建议扩充'}，体裁{novel.get('genre', '')}",
        },
        "原创性": {"score": 7, "max": 10, "note": f"体裁{novel.get('genre', '')}——需人工判断创新度"},
    }

    total = sum(int(item["score"]) for item in criteria.values())
    max_total = sum(int(item["max"]) for item in criteria.values())
    rating = total / max_total
    if rating >= 0.85:
        verdict = "✅ 推荐买断——达到出版级别，建议提交出版社"
        offer_range = "¥5,000-50,000（根据体裁和平台）"
    elif rating >= 0.7:
        verdict = "📝 建议签约——质量良好，需要1-2轮编辑加工后可出版"
        offer_range = "¥1,000-10,000（需编辑投入）"
    elif rating >= 0.5:
        verdict = "🔧 需要打磨——核心故事有潜力，但需要重大修改"
        offer_range = "暂不建议报价"
    else:
        verdict = "❌ 不建议出版——需要重新构思或大面积重写"
        offer_range = "不适用"

    return {
        "verdict": verdict,
        "rating": f"{rating:.0%}",
        "offer_range": offer_range,
        "criteria": criteria,
        "acquisition_note": f"经过{len(chapters)}章的系统评估，该书{'已经达到出版水准' if rating >= 0.7 else '还需要编辑打磨'}。{'建议提交出版社编辑部做最终审读。' if rating >= 0.8 else '建议在提交前先解决上述问题。'}",
    }


@router.get("/api/novels/{novel_id}/cockpit")
def writers_cockpit(novel_id: str) -> dict:
    """Writer cockpit with quality, revenue, retention, actions, and risks."""
    novel = _db().get_novel(novel_id)
    if not novel:
        raise HTTPException(404)
    chapters = _generated_chapters(novel)
    scores = [chapter.get("quality_score", 0) for chapter in chapters]
    avg_quality = sum(scores) / len(scores) if scores else 0

    alerts = []
    if len(chapters) >= 5:
        last5 = scores[-5:]
        if sum(last5) / 5 < avg_quality - 0.1:
            alerts.append({"level": "warning", "msg": f"最近5章质量下降(均{sum(last5) / 5:.2f} vs 总均{avg_quality:.2f})——建议检查并重写弱章"})
    if len(chapters) >= 3:
        hooks = [chapter.get("ending_hook", "") for chapter in chapters[-5:]]
        weak = sum(1 for hook in hooks if len(hook) < 30) if hooks else 0
        if weak >= 3:
            alerts.append({"level": "critical", "msg": f"最近5章{weak}章钩子偏弱——追读率会下降"})
    if novel.get("total_words", 0) > 0 and chapters:
        avg_len = novel["total_words"] / len(chapters)
        if avg_len > 3500:
            alerts.append({"level": "info", "msg": f"章节均长{avg_len:.0f}字——手机阅读建议控制在2500字以内"})

    milestones = []
    for total, reward in [(20, "签约资格"), (50, "推荐位"), (100, "全勤奖"), (200, "精品频道")]:
        if len(chapters) < total:
            milestones.append({"need": total - len(chapters), "total": total, "reward": reward})

    actions = []
    if len(chapters) < 3:
        actions.append("📝 生成至少3章以完成首秀数据采集")
    elif avg_quality < 0.7:
        actions.append("⚠️ 经典模式重写弱章")
    elif len(chapters) < 20:
        actions.append("📖 继续生成至20章以申请签约")
    elif len(chapters) < 50:
        actions.append("🚀 继续生成至50章以获取推荐位")
    else:
        actions.append("✅ 书籍已进入稳定运营阶段")

    return {
        "novel": novel["title"],
        "genre": novel.get("genre", "?"),
        "chapters": len(chapters),
        "words": novel.get("total_words", 0),
        "avg_quality": round(avg_quality, 2),
        "alerts": alerts,
        "milestones": milestones,
        "next_actions": actions,
        "retention": retention_score(novel_id) if len(chapters) >= 3 else {},
        "revenue": revenue_estimate(novel_id),
        "publish_status": {"published": 0, "pending": len(chapters)},
    }


@router.get("/api/novels/{novel_id}/retention-score")
def retention_score(novel_id: str) -> dict:
    """Predict retention from chapter quality, hooks, and update cadence."""
    novel = _db().get_novel(novel_id)
    if not novel:
        raise HTTPException(404)
    chapters = _generated_chapters(novel)
    if len(chapters) < 3:
        return {"error": "至少需要3章"}

    scores = [chapter.get("quality_score", 0) for chapter in chapters]
    hooks = [chapter.get("ending_hook", "") for chapter in chapters]
    strong_hooks = sum(1 for hook in hooks[-10:] if len(hook) > 30 and any(keyword in hook for keyword in ["？", "！", "……"]))
    quality_trend = "up" if scores[-3:] and scores[-1] > scores[0] else "down" if scores[-1] < scores[0] else "flat"
    avg_quality = sum(scores) / len(scores)
    weak = [(chapter["number"], chapter.get("quality_score", 0)) for chapter in chapters if chapter.get("quality_score", 0) < 0.65]
    return {
        "estimated_retention": f"{min(95, int(avg_quality * 100))}%",
        "strong_hook_ratio": f"{strong_hooks}/{min(10, len(hooks[-10:]))}章",
        "quality_trend": quality_trend,
        "drop_off_risk_chapters": weak if weak else "无",
        "platform_revenue_impact": "高质量→高留存→算法给量→广告分成增加" if avg_quality >= 0.75 else "质量不稳定→留存下降→算法降权→收入减少",
        "daily_readers_estimate": max(100, int(novel.get("total_words", 0) / 500 * (avg_quality / 0.8))),
    }


@router.get("/api/novels/{novel_id}/monetization-status")
def monetization_status(novel_id: str) -> dict:
    """VIP conversion dashboard for free-to-paid chapter quality."""
    novel = _db().get_novel(novel_id)
    if not novel:
        raise HTTPException(404)
    chapters = _generated_chapters(novel)
    total = len(chapters)
    free_chapters = min(total, 20)
    vip_chapters = max(0, total - free_chapters)
    free_quality = sum(chapter.get("quality_score", 0) for chapter in chapters[:free_chapters]) / max(free_chapters, 1)
    vip_quality = sum(chapter.get("quality_score", 0) for chapter in chapters[free_chapters:]) / max(vip_chapters, 1) if vip_chapters > 0 else 0
    return {
        "total_chapters": total,
        "free_chapters": free_chapters,
        "vip_chapters": vip_chapters,
        "paywall_position": 20,
        "free_avg_quality": round(free_quality, 2),
        "vip_avg_quality": round(vip_quality, 2),
        "conversion_ready": free_quality >= 0.75 and total >= 15,
        "vip_quality_warning": vip_quality < free_quality and vip_chapters > 0,
        "tips": [
            "付费墙前的最后一章(第20章)必须是全书最强钩子——读者在这一点'购买下一章'",
            f"当前免费章均分{free_quality:.2f}, 付费章均分{vip_quality:.2f}" + ("——⚠️ 付费章质量低于免费章，读者会觉得自己上当了" if vip_quality < free_quality and vip_chapters > 0 else "——✅ 付费内容对得起读者的钱"),
            "每50章建议插入一章'付费读者专属番外'——提升续费率",
        ]
        if total > 0
        else [],
    }


@router.get("/api/novels/{novel_id}/optimal-publish-time")
def optimal_publish_time(novel_id: str) -> dict:
    """Recommend stable publication times."""
    return {
        "best_times": ["12:00-13:00（午休阅读高峰）", "18:00-20:00（通勤+晚饭后）", "21:00-23:00（睡前黄金档）"],
        "worst_times": ["02:00-06:00（没人醒着）", "09:00-11:00（工作时间）"],
        "recommendation": "每天固定18:00和21:00各发1章——培养读者追更习惯",
        "weekend_bonus": "周末多发1章——读者周末阅读时长是工作日2倍",
    }


@router.get("/api/novels/{novel_id}/estimate")
def estimate_cost(novel_id: str) -> dict:
    """Estimate generation cost for future chapters."""
    novel = _db().get_novel(novel_id)
    if not novel:
        raise HTTPException(404)
    chapters = _generated_chapters(novel)
    avg_words = sum(chapter["word_count"] for chapter in chapters) / len(chapters) if chapters else 2500
    provider = _get_provider(novel_id)
    models = provider.get("models", ["deepseek-v4-pro"]) if provider else ["gpt-4o"]
    model = models[0] if isinstance(models, list) and models else "gpt-4o"
    from novel_writer.generator import Generator

    per_chapter = Generator._calc_cost(model, 20000, int(avg_words * 2.5))
    return {
        "model": model,
        "avg_words_per_chapter": round(avg_words),
        "estimated_cost_per_chapter": round(per_chapter, 4),
        "estimated_10_chapters": round(per_chapter * 10, 2),
        "estimated_50_chapters": round(per_chapter * 50, 2),
    }


@router.get("/api/novels/{novel_id}/resume")
def resume_generation(novel_id: str) -> dict:
    """Detect last complete chapter and suggest resume action."""
    novel = _db().get_novel(novel_id)
    if not novel:
        raise HTTPException(404)
    chapters = _generated_chapters(novel)
    last_complete = max(chapter["number"] for chapter in chapters) if chapters else 0
    if chapters:
        content = chapters[-1].get("content", "")
        truncated = len(content) < 200 or content.endswith("...") or "未完" in content[-50:]
    else:
        truncated = False
    return {
        "last_complete_chapter": last_complete,
        "next_chapter": last_complete + 1,
        "last_chapter_truncated": truncated,
        "action": "regenerate_last" if truncated else "generate_next",
        "total_chapters": len(chapters),
    }


@router.post("/api/novels/{novel_id}/generate-cover")
def generate_cover(novel_id: str) -> dict:
    """Generate an AI image prompt and placeholder SVG cover."""
    novel = _db().get_novel(novel_id)
    if not novel:
        raise HTTPException(404, "Novel not found")

    title = novel.get("title", "未命名")
    synopsis = novel.get("synopsis", "")
    genre = novel.get("genre", "玄幻")
    author = novel.get("author", "AI")

    try:
        from novel_writer.config import Config
        from novel_writer.generator import Generator

        provider = _get_provider(novel_id)
        models = provider.get("models", ["deepseek-v4-pro"])
        cfg = Config(
            openai_api_key=provider.get("api_key", ""),
            openai_base_url=provider.get("base_url", ""),
            model=models[0] if isinstance(models, list) and models else "gpt-4o",
        )
        gen = Generator(cfg)
        prompt_text = f"""你是一个小说封面设计师。为以下小说生成一个AI绘图提示词（英文，50词以内），用于生成封面图。

小说名：《{title}》
类型：{genre}
简介：{synopsis}

要求：风格适配{genre}类型，有意境，适合做封面。只输出英文提示词。"""
        img_prompt = gen._call_llm_with_retry([{"role": "user", "content": prompt_text}], max_tokens=128)
    except Exception:
        img_prompt = f"A mystical {genre} novel cover with atmospheric lighting, cinematic composition"

    genre_colors = {
        "玄幻": ("#1a1a2e", "#e94560"),
        "都市": ("#2d3436", "#00b894"),
        "悬疑": ("#0c0c0c", "#fdcb6e"),
        "科幻": ("#0a192f", "#64ffda"),
        "武侠": ("#2c1810", "#d4a574"),
        "历史": ("#3e2723", "#ffcc80"),
        "仙侠": ("#1a1a3e", "#a78bfa"),
        "系统流": ("#1b1b2f", "#e94560"),
        "官场": ("#1a1a1a", "#c0392b"),
        "末世": ("#1c1c1c", "#ff6b6b"),
    }
    bg, accent = genre_colors.get(genre, ("#1a1a2e", "#e94560"))
    display_title = title if len(title) <= 8 else title[:8] + "..."
    svg_cover = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 600" width="400" height="600">
  <defs>
    <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:{bg}"/>
      <stop offset="100%" style="stop-color:{accent}33"/>
    </linearGradient>
    <linearGradient id="shine" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" style="stop-color:#ffffff10"/>
      <stop offset="50%" style="stop-color:#ffffff00"/>
      <stop offset="100%" style="stop-color:#00000020"/>
    </linearGradient>
  </defs>
  <rect width="400" height="600" fill="url(#bg)"/>
  <rect width="400" height="600" fill="url(#shine)"/>
  <line x1="30" y1="40" x2="37" y2="40" stroke="{accent}" stroke-width="0.5" opacity="0.3"/>
  <line x1="28" y1="0" x2="28" y2="600" stroke="{accent}" stroke-width="0.3" opacity="0.1"/>
  <line x1="372" y1="0" x2="372" y2="600" stroke="{accent}" stroke-width="0.3" opacity="0.1"/>
  <rect x="35" y="180" width="330" height="2" fill="{accent}" opacity="0.3"/>
  <rect x="35" y="420" width="330" height="1" fill="{accent}" opacity="0.15"/>
  <text x="200" y="230" text-anchor="middle" font-family="SimSun, STSong, serif" font-size="32" fill="{accent}" font-weight="bold" letter-spacing="4">{html.escape(display_title)}</text>
  <text x="200" y="340" text-anchor="middle" font-family="SimSun, STSong, serif" font-size="14" fill="#ffffff99" letter-spacing="8">{html.escape(genre)}</text>
  <text x="200" y="460" text-anchor="middle" font-family="SimSun, STSong, serif" font-size="12" fill="#ffffff60" letter-spacing="3">{html.escape(author)}</text>
  <text x="200" y="560" text-anchor="middle" font-family="SimSun, STSong, serif" font-size="10" fill="#ffffff30">AI Lingmo</text>
</svg>'''
    return {"prompt": img_prompt.strip(), "svg_cover": svg_cover, "title": title, "genre": genre}
