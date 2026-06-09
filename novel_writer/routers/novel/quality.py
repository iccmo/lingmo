"""Quality reports, checks, proofreading, and lightweight polish endpoints."""

from __future__ import annotations

import json
import re

from fastapi import APIRouter, Body, HTTPException

from novel_writer.routers.deps import get_db

router = APIRouter(tags=["quality"])

_REVERSE_POLISH_CHUNK_CHARS = 3500


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


def _generator_for(novel_id: str, *, prefer_pro: bool = False):
    from novel_writer.config import Config
    from novel_writer.generator import Generator

    provider = _get_provider(novel_id)
    models = provider.get("models", ["deepseek-v4-pro"])
    if prefer_pro and "deepseek-v4-pro" in str(models):
        model = "deepseek-v4-pro"
    else:
        model = models[0] if isinstance(models, list) and models else "gpt-4o"
    cfg = Config(
        openai_api_key=provider.get("api_key", ""),
        openai_base_url=provider.get("base_url", ""),
        model=model,
    )
    return Generator(cfg)


def _generated_chapters(novel: dict) -> list[dict]:
    return [chapter for chapter in novel.get("chapters", []) if chapter.get("word_count", 0) > 0]


def _chapter_text(db, novel_id: str, chapter: dict) -> str:
    content = chapter.get("content", "")
    if content:
        return content
    full = db.get_chapter(novel_id, chapter["number"])
    return full.get("content", "") if full else ""


def _score_agency_text(text: str) -> float:
    choice_markers = [
        "选择",
        "决定",
        "主动",
        "拒绝",
        "坚持",
        "承担",
        "反击",
        "布局",
        "设局",
        "押上",
        "亲自",
        "站出来",
        "不退",
        "守住",
    ]
    passive_markers = ["被迫", "只能", "不得不", "只好", "任由", "听天由命", "无能为力"]
    choice_hits = sum(text.count(marker) for marker in choice_markers)
    passive_hits = sum(text.count(marker) for marker in passive_markers)
    return max(0.0, min(1.0, 0.45 + choice_hits * 0.12 - passive_hits * 0.10))


def _score_cost_text(text: str) -> float:
    gain_markers = [
        "获得",
        "得到",
        "突破",
        "胜利",
        "赢",
        "成功",
        "掌握",
        "晋升",
        "救下",
        "夺回",
        "拿到",
        "找到",
        "觉醒",
    ]
    cost_markers = [
        "代价",
        "失去",
        "受伤",
        "流血",
        "反噬",
        "后患",
        "追杀",
        "暴露",
        "牺牲",
        "裂痕",
        "误会",
        "欠下",
        "耗尽",
        "昏迷",
        "疼",
        "痛",
        "伤",
    ]
    gains = sum(text.count(marker) for marker in gain_markers)
    costs = sum(text.count(marker) for marker in cost_markers)
    if gains == 0:
        return 0.75 if costs else 0.55
    return max(0.0, min(1.0, 0.50 + min(costs, gains + 2) * 0.12 - max(0, gains - costs) * 0.10))


def _quality_dimension_diagnostics(db, novel_id: str, chapters: list[dict]) -> dict:
    costs = db.get_cost_ledger(novel_id)
    losses_by_chapter: dict[int, int] = {}
    gains_by_chapter: dict[int, int] = {}
    for entry in costs:
        chapter_num = int(entry.get("chapter_num") or 0)
        if entry.get("gain"):
            gains_by_chapter[chapter_num] = gains_by_chapter.get(chapter_num, 0) + 1
        if entry.get("loss"):
            losses_by_chapter[chapter_num] = losses_by_chapter.get(chapter_num, 0) + 1

    chapter_rows = []
    for chapter in chapters:
        number = int(chapter["number"])
        text = _chapter_text(db, novel_id, chapter)
        agency = _score_agency_text(text)
        cost = _score_cost_text(text)
        loss_count = losses_by_chapter.get(number, 0)
        gain_count = gains_by_chapter.get(number, 0)
        if gain_count and not loss_count:
            cost = min(cost, 0.55)
        chapter_rows.append(
            {
                "number": number,
                "title": chapter.get("title", ""),
                "agency": round(agency, 2),
                "cost": round(cost, 2),
                "gain_count": gain_count,
                "loss_count": loss_count,
                "issues": [
                    issue
                    for issue in [
                        "主角主动性不足" if agency < 0.6 else "",
                        "胜利缺少代价" if cost < 0.65 else "",
                    ]
                    if issue
                ],
            }
        )

    avg_agency = sum(row["agency"] for row in chapter_rows) / len(chapter_rows)
    avg_cost = sum(row["cost"] for row in chapter_rows) / len(chapter_rows)
    weak_dimensions = [row for row in chapter_rows if row["issues"]]
    revision_focus = []
    if avg_agency < 0.7:
        revision_focus.append("补主角主动选择：每章至少一个拒绝、押注、反击或承担后果的决定")
    if avg_cost < 0.7:
        revision_focus.append("补胜利代价：获得线索/突破/救人后必须留下伤口、债务、暴露风险或关系裂痕")

    return {
        "avg_agency": round(avg_agency, 2),
        "avg_cost": round(avg_cost, 2),
        "weak_dimensions": weak_dimensions,
        "revision_focus": revision_focus,
    }


def _chunk_for_reverse_polish(content: str, max_chars: int = _REVERSE_POLISH_CHUNK_CHARS) -> list[str]:
    """Split chapter text without dropping any tail content."""
    if len(content) <= max_chars:
        return [content]

    chunks: list[str] = []
    current = ""
    for paragraph in content.split("\n\n"):
        piece = paragraph if not current else f"\n\n{paragraph}"
        if len(piece) > max_chars:
            if current:
                chunks.append(current)
                current = ""
            for start in range(0, len(paragraph), max_chars):
                chunks.append(paragraph[start : start + max_chars])
            continue
        if current and len(current) + len(piece) > max_chars:
            chunks.append(current)
            current = paragraph
        else:
            current += piece
    if current:
        chunks.append(current)
    return chunks


def _build_reverse_polish_prompt(chunk: str, index: int, total: int) -> str:
    position = f"第{index}/{total}段" if total > 1 else "全文"
    return f"""以下是小说正文的{position}。你的任务是删减——只删不加，不改写。

删减规则（严格按顺序）：
1. 删掉所有「突然」「竟然」「似乎」「有些」「其实」「不由得」「仿佛」
2. 删掉所有解释情绪的句子（让动作和对话自己说话）
3. 如果上一段已经暗示的信息，下一段不要再明说——删掉重复的
4. 删掉所有「说道」「问道」「答道」中的「道」——改成「说」「问」「答」
5. 删掉所有不必要的「的」「地」「得」
6. 如果删完某段不足原来一半字数——那段不需要删，恢复原样
7. 绝对不要删除或淡化主角主动选择、拒绝、承担、冒险、伤口、代价、后果、身份暴露、关系裂痕、后续麻烦；这些不是冗余

直接返回删减后的正文片段。不要加任何解释。

原文：
{chunk}
"""


@router.get("/api/novels/{novel_id}/quality-gate")
def get_quality_gate(novel_id: str) -> dict:
    """Brain Agent quality gate for the latest chapter."""
    db = _db()
    if not db.get_novel(novel_id):
        raise HTTPException(404)

    from novel_writer.brain_agent import BrainAgent

    report = BrainAgent(db).get_quality_report(novel_id)
    errors = report.get("errors", 0)
    if errors >= 3:
        gate = "🔴 需修复"
    elif errors >= 1 or report.get("warnings", 0) >= 3:
        gate = "⚠️ 注意"
    else:
        gate = "✅ 良好"
    return {"gate": gate, **report}


@router.get("/api/novels/{novel_id}/report")
def quality_report(novel_id: str) -> dict:
    """Generate a pre-publication quality report."""
    db = _db()
    novel = db.get_novel(novel_id)
    if not novel:
        raise HTTPException(404)
    chapters = _generated_chapters(novel)
    if len(chapters) < 3:
        return {"error": "至少需要3章才能生成报告"}

    scores = [chapter.get("quality_score", 0) for chapter in chapters]
    titles = [chapter.get("title", "") for chapter in chapters]
    avg_quality = sum(scores) / len(scores)
    min_idx = min(range(len(scores)), key=lambda index: scores[index])
    max_idx = max(range(len(scores)), key=lambda index: scores[index])
    trend = "上升" if scores[-1] > scores[0] else "下降" if scores[-1] < scores[0] else "平稳"
    weak = [
        (chapter["number"], chapter.get("quality_score", 0), chapter.get("title", ""))
        for chapter in chapters
        if chapter.get("quality_score", 0) < 0.7
    ]
    strong = [
        (chapter["number"], chapter.get("quality_score", 0), chapter.get("title", ""))
        for chapter in chapters
        if chapter.get("quality_score", 0) >= 0.82
    ]
    dimension_diagnostics = _quality_dimension_diagnostics(db, novel_id, chapters)

    try:
        style = db.get_style_profile(novel_id)
        titles_raw = _generator_for(novel_id)._call_llm_with_retry(
            [
                {"role": "system", "content": "你是一位出版编辑。基于小说内容生成5个备选书名，每个2-6字，有意象感。只输出书名，每行一个。"},
                {
                    "role": "user",
                    "content": f"小说简介：{novel.get('synopsis', '')}\n核心追问：{style.get('central_question', '') if style else ''}\n已有章节标题：{'、'.join(titles[:10])}",
                },
            ],
            max_tokens=256,
        )
    except Exception:
        titles_raw = ""

    return {
        "overview": {
            "total_chapters": len(chapters),
            "total_words": novel.get("total_words", 0),
            "avg_quality": round(avg_quality, 2),
            "trend": trend,
        },
        "strongest": f"第{chapters[max_idx]['number']}章「{titles[max_idx]}」(评分{scores[max_idx]:.2f})",
        "weakest": f"第{chapters[min_idx]['number']}章「{titles[min_idx]}」(评分{scores[min_idx]:.2f})",
        "weak_chapters": weak,
        "strong_chapters": strong,
        "dimension_diagnostics": dimension_diagnostics,
        "title_candidates": [
            title.strip() for title in titles_raw.split("\n") if title.strip() and len(title.strip()) <= 10
        ][:5]
        if titles_raw
        else [],
        "recommendation": "建议发布"
        if avg_quality >= 0.75
        else "建议经典模式重写弱章后再发布"
        if avg_quality >= 0.65
        else "建议大面积重写——整体质量不达标",
        "revision_focus": dimension_diagnostics["revision_focus"],
        "pipeline_ready": avg_quality >= 0.7 and len(chapters) >= 10,
    }


@router.get("/api/novels/{novel_id}/classic-assessment")
def classic_assessment(novel_id: str) -> dict:
    """Assess first five chapters for classic potential."""
    novel = _db().get_novel(novel_id)
    if not novel:
        raise HTTPException(404)
    chapters = _generated_chapters(novel)
    if len(chapters) < 5:
        return {"ready": False, "reason": f"需要至少5章(当前{len(chapters)})"}

    first_five = chapters[:5]
    scores = [chapter.get("quality_score", 0) for chapter in first_five]
    avg_quality = sum(scores) / len(scores)
    min_quality = min(scores)
    titles = [chapter.get("title", "") for chapter in first_five]
    has_variety = len(set(titles[:3])) >= 2

    from novel_writer.config import Config
    from novel_writer.generator import Generator

    opener_check = (
        Generator._classic_check.__func__(None, first_five[0].get("content", "")[:500], None, None)
        if first_five[0].get("content")
        else (True, [])
    )
    opening_ok = opener_check[0] if isinstance(opener_check, tuple) else True
    opening_issues = opener_check[1] if isinstance(opener_check, tuple) and len(opener_check) > 1 else []
    threshold = 0.78
    passed = avg_quality >= threshold and min_quality >= 0.65 and has_variety and opening_ok

    return {
        "passed": passed,
        "avg_quality": round(avg_quality, 2),
        "min_quality": round(min_quality, 2),
        "title_variety": has_variety,
        "opening_ok": opening_ok,
        "opening_issues": opening_issues,
        "threshold": threshold,
        "recommendation": "✅ 经典潜质达标，可以继续"
        if passed
        else f"❌ 建议推倒重来（均分{avg_quality:.2f}<{threshold}）"
        if avg_quality < threshold
        else "⚠️ 部分指标不达标，建议针对性修改",
    }


@router.get("/api/novels/{novel_id}/spellcheck")
def spellcheck_novel(novel_id: str) -> dict:
    """Basic spelling, repetition, and AI-cliche checks."""
    novel = _db().get_novel(novel_id)
    if not novel:
        raise HTTPException(404)
    chapters = _generated_chapters(novel)
    issues = []
    all_text = " ".join(chapter.get("content", "") for chapter in chapters[-5:])
    for cliche in ["在这个世界", "随着时间", "不仅如此", "总而言之", "毫无疑问", "值得注意的是", "换句话说"]:
        if cliche in all_text:
            issues.append({"type": "cliche", "text": cliche, "count": all_text.count(cliche)})

    word_freq: dict[str, int] = {}
    for word in re.findall(r"[一-鿿]{2}", all_text[:5000]):
        word_freq[word] = word_freq.get(word, 0) + 1
    for word, count in word_freq.items():
        if count >= 8:
            issues.append({"type": "repetition", "text": word, "count": count})
    return {"issues": issues, "total_chapters_checked": len(chapters)}


@router.get("/api/novels/{novel_id}/algorithm-optimize")
def algorithm_optimize(novel_id: str) -> dict:
    """Platform recommendation optimization suggestions."""
    novel = _db().get_novel(novel_id)
    if not novel:
        raise HTTPException(404)
    chapters = _generated_chapters(novel)
    issues = []
    tips = []

    if chapters:
        lengths = [chapter["word_count"] for chapter in chapters]
        avg = sum(lengths) / len(lengths)
        if max(lengths) > avg * 1.8 or min(lengths) < avg * 0.5:
            issues.append("章节长度波动过大——算法会降低推荐权重。建议每章控制在均长±30%以内。")
        if avg < 1800:
            tips.append("章节偏短(<1800字)——番茄算法优先推荐2000+字的章节")
        elif avg > 3500:
            tips.append("章节偏长(>3500字)——手机阅读最佳体验是1500-2500字，过长降低完读率")

    tips.append("每天固定时间发布2章=算法加权20-30%。建议设置自动日更。")
    if len(chapters) >= 3:
        first3_scores = [chapter.get("quality_score", 0) for chapter in chapters[:3]]
        if sum(first3_scores) / 3 < 0.75:
            issues.append("前3章质量不达标(均分<0.75)——番茄首秀流量取决于前3章完读率。建议经典模式重写前3章")
    if chapters:
        hooks = [chapter.get("ending_hook", "") for chapter in chapters[-5:]]
        strong_hooks = sum(1 for hook in hooks if len(hook) > 30 and ("？" in hook or "！" in hook or "……" in hook))
        if strong_hooks < 3:
            issues.append(f"最近5章有{5 - strong_hooks}章结尾钩子偏弱——追读率会下降，算法会减少推荐")

    tips.append("每5章在结尾加一句'读者提问'——如'你觉得他做得对吗？评论区见'——提升互动率=算法加权")
    genre = novel.get("genre", "玄幻")
    genre_tips = {
        "玄幻": "玄幻读者偏好每章1个修炼突破/丹药获得/打脸场景——缺这个完读率直接降",
        "都市": "都市读者偏好现实冲突——权力博弈、金钱交易、人际关系暗流",
        "悬疑": "悬疑读者偏好信息差——每章给一点但又不够，让他们一直猜",
        "科幻": "科幻读者偏好概念的深度——不要用'量子'糊弄，用数据和逻辑",
    }
    if genre in genre_tips:
        tips.append(genre_tips[genre])

    return {
        "novel_id": novel_id,
        "genre": genre,
        "chapters": len(chapters),
        "words": novel.get("total_words", 0),
        "critical_issues": issues,
        "optimization_tips": tips,
        "algorithm_factors": {
            "完读率权重": "最高——每章开头300字和结尾钩子决定",
            "追读率权重": "高——连续5章追读率低于20%则降权",
            "更新频率权重": "中——日更2章比周更10章有效3倍",
            "互动率权重": "中——评论/收藏/打赏提升分发",
            "首秀窗口": "前3章完成数据采集，第4章开始正式推荐",
        },
        "next_action": "建议完成50章后申请推荐位（平台给50章以上作品单独流量池）",
    }


@router.get("/api/novels/{novel_id}/freshness-check")
def freshness_check(novel_id: str) -> dict:
    """Check whether story premise feels too similar to existing hits."""
    novel = _db().get_novel(novel_id)
    if not novel:
        raise HTTPException(404)
    chapters = _generated_chapters(novel)
    generator = _generator_for(novel_id)
    check = generator._call_llm_with_retry(
        [
            {"role": "system", "content": "你是网文市场分析师。判断这个故事的设定和核心冲突是否太像已知爆款。给出1-10的新鲜度评分。"},
            {
                "role": "user",
                "content": f"体裁：{novel.get('genre', '')}\n简介：{novel.get('synopsis', '')}\n已有章节标题：{'、'.join(chapter['title'] for chapter in chapters[:5])}\n\n分析：这个设定和哪些已知爆款相似？相似度多高？有什么可以调整让它更独特？",
            },
        ],
        max_tokens=512,
    )
    return {
        "synopsis": novel.get("synopsis", ""),
        "analysis": check,
        "tip": "如果新鲜度<6，建议调整核心设定——换一个不同类型的'金手指'或改变主角的起点，可以大幅提升新鲜感",
    }


@router.get("/api/novels/{novel_id}/chapters/{chapter_num}/fact-check")
def fact_check_chapter(novel_id: str, chapter_num: int) -> dict:
    """Audit factual claims in a chapter."""
    db = _db()
    chapter = db.get_chapter(novel_id, chapter_num)
    if not chapter:
        raise HTTPException(404)
    novel = db.get_novel(novel_id)
    return _generator_for(novel_id).fact_check(chapter.get("content", ""), novel.get("genre", "") if novel else "")


@router.post("/api/novels/{novel_id}/chapters/{chapter_num}/proofread")
def proofread_chapter(novel_id: str, chapter_num: int) -> dict:
    """AI proofreading for typos, repetition, logic, and punctuation."""
    chapter = _db().get_chapter(novel_id, chapter_num)
    if not chapter:
        raise HTTPException(404, "Chapter not found")
    content = chapter.get("content", "")
    if not content:
        raise HTTPException(400, "Chapter has no content")

    generator = _generator_for(novel_id)
    chunks = [content[index : index + 3000] for index in range(0, len(content), 3000)]
    all_issues: list[dict] = []
    for chunk in chunks:
        prompt = f"""请校对以下小说段落，找出：
1. 错别字（含形近字、同音字错误）
2. 重复用词（同一句内重复3次以上的词）
3. 逻辑不连贯（前后矛盾、时间线混乱、行为不合理）
4. 标点错误（中英文标点混用、缺失、多余）

对每一处问题，用JSON格式返回数组，每个元素包含：
- type: "typo" | "repetition" | "inconsistency" | "punctuation"
- original: 原文中的问题文本
- suggestion: 修改建议
- reason: 修改理由（简短说明）

只返回JSON数组，不要任何其他文字。如果没有问题，返回空数组[]。

段落内容：
{chunk}"""
        result = generator._call_llm_with_retry(
            [
                {"role": "system", "content": "你是一位专业的中文校对编辑。你只返回JSON数组，不返回任何其他内容。"},
                {"role": "user", "content": prompt},
            ],
            max_tokens=4096,
        )
        try:
            json_str = result.strip()
            if json_str.startswith("```"):
                json_str = re.sub(r"^```(?:json)?\s*", "", json_str)
                json_str = re.sub(r"\s*```$", "", json_str)
            issues = json.loads(json_str)
            if isinstance(issues, list):
                all_issues.extend(issues)
        except (json.JSONDecodeError, TypeError):
            match = re.search(r"\[.*\]", result, re.DOTALL)
            if match:
                try:
                    issues = json.loads(match.group())
                    if isinstance(issues, list):
                        all_issues.extend(issues)
                except (json.JSONDecodeError, TypeError):
                    pass

    return {"novel_id": novel_id, "chapter": chapter_num, "issues": all_issues, "total": len(all_issues)}


@router.post("/api/novels/{novel_id}/chapters/{chapter_num}/polish-reverse")
def reverse_polish(novel_id: str, chapter_num: int, data: dict | None = Body(default=None)) -> dict:
    """Restrained edit: delete redundant words and phrases without adding content."""
    chapter = _db().get_chapter(novel_id, chapter_num)
    content = data.get("content") if isinstance(data, dict) else None
    if not isinstance(content, str) or not content.strip():
        content = chapter.get("content") if chapter else ""
    if not chapter or not content:
        raise HTTPException(400, "No content")
    try:
        generator = _generator_for(novel_id, prefer_pro=True)
        chunks = _chunk_for_reverse_polish(content)
        polished_chunks = []
        for index, chunk in enumerate(chunks, start=1):
            prompt = _build_reverse_polish_prompt(chunk, index, len(chunks))
            result = generator._call_llm_with_retry([{"role": "user", "content": prompt}], max_tokens=4096)
            if not result:
                raise HTTPException(500, f"LLM returned empty for chunk {index}")
            polished_chunks.append(result.strip())
        polished = "\n\n".join(polished_chunks)
        return {
            "polished": polished,
            "original_length": len(content),
            "polished_length": len(polished),
            "chunks": len(chunks),
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, str(exc)[:200])
