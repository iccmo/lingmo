"""小说路由 — CRUD、写作生成、质量分析、导出发布。"""

import json
import re
import sys
from typing import Any
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile

from ..brain_agent import BrainAgent
from ..stations.novel.constraint_compressor import ConstraintCompressor
from .deps import get_db

router = APIRouter(tags=["novel"])

# 兼容：路由函数直接用 db 访问
db = get_db()

# Agent pipeline results cache
_agent_memos: dict[str, dict] = {}


def _get_provider(novel_id: str | None = None):
    """Get configured model provider — default to DeepSeek."""
    provider_id = "deepseek"  # Default: DeepSeek (fast, cheap, no timeout)
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


# ═══════════════════ Generation Status ═══════════════════
import threading

_gen_status: dict[str, dict] = {}
_gen_lock = threading.Lock()

def _set_status(novel_id: str, status: str, message: str = "", progress: int = 0, overall: float = 0):
    with _gen_lock:
        _gen_status[novel_id] = {"status": status, "message": message, "progress": progress}
        if overall > 0:
            _gen_status[novel_id]["overall"] = round(overall, 2)

def _get_status(novel_id: str) -> dict:
    return _gen_status.get(novel_id, {"status": "idle", "message": "", "progress": 0})


# ═══════════════════ Generation Queue ═══════════════════
import uuid

_job_queue: dict[str, dict] = {}
_job_lock = threading.Lock()


def _get_queue_status(novel_id: str) -> dict | None:
    """Return the active job for a novel, or None if no job queued/running."""
    with _job_lock:
        for job in _job_queue.values():
            if job["novel_id"] == novel_id and job["status"] in ("queued", "running"):
                return {
                    "job_id": job["job_id"],
                    "status": job["status"],
                    "progress": job["progress"],
                    "last_error": job.get("last_error"),
                }
    return None


def _run_queue_job(job: dict):
    """Run a batch generation job in a background thread, updating queue status."""
    novel_id = job["novel_id"]
    count = job["count"]
    quality_threshold = job.get("quality_threshold", 0.8)
    try:
        with _job_lock:
            job["status"] = "running"
        # Set the quality threshold for _run_batch_generation
        _gen_directions[novel_id + "_qthreshold"] = str(quality_threshold)
        _run_batch_generation(novel_id, count)
        with _job_lock:
            job["status"] = "done"
            job["progress"]["current"] = job["progress"]["total"]
    except Exception as e:
        with _job_lock:
            job["status"] = "error"
            job["last_error"] = str(e)[:500]


# ═══════════════ Helpers ═══════════════

def _random_name(genre: str = "玄幻") -> str:
    from ..generator import random_protagonist_name
    name, _ = random_protagonist_name(genre)
    return name

def _summary(novel: dict) -> dict:
    return {
        "id": novel["id"], "title": novel["title"], "author": novel["author"],
        "genre": novel["genre"], "synopsis": novel["synopsis"] or "",
        "total_chapters": novel.get("total_chapters", 0),
        "total_words": novel.get("total_words", 0),
        "latest_chapter": novel.get("latest_chapter"),
    }


# ═══════════════ Novels ═══════════════

@router.get("/api/novels")
def list_novels() -> list:
    return [_summary(n) for n in db.list_novels()]


@router.post("/api/novels")
def create_novel(data: dict) -> dict:
    nid = data.get("id", "").strip()
    if not nid:
        raise HTTPException(400, "id required")
    if not re.match(r'^[a-z0-9][a-z0-9-]*$', nid):
        raise HTTPException(400, "id must be lowercase alphanumeric with hyphens")
    if len(nid) > 50:
        raise HTTPException(400, "id too long (max 50)")
    if db.get_novel(nid):
        raise HTTPException(409, f"'{nid}' already exists")
    novel = db.create_novel(
        id=nid,
        title=data.get("title", nid),
        author=data.get("author", "AI"),
        synopsis=data.get("synopsis", ""),
        genre=data.get("genre", "玄幻"),
        world_name=data.get("world_name", ""),
        world_era=data.get("era", ""),
        world_geo=data.get("geography", ""),
        power_system=data.get("power_system", ""),
        world_rules=json.dumps(data.get("rules", [])),
        main_arc=data.get("main_arc", ""),
        current_arc=data.get("current_arc", "开篇"),
        tags=data.get("tags", []),
        char_key="protagonist",
        name=data.get("protagonist_name", "").strip() or _random_name(data.get("genre", "玄幻")),
        role="主角",
        personality=data.get("protagonist_personality", ""),
        background=data.get("protagonist_background", ""),
        power_level=data.get("protagonist_power", ""),
    )
    # Auto-assign initial style profile based on genre
    try:
        from dataclasses import asdict
        from ..generator import GENRE_TO_STYLE, STYLE_POOL
        style_key = GENRE_TO_STYLE.get(data.get("genre", "玄幻"), "玄幻")
        base_style = STYLE_POOL.get(style_key)
        if base_style:
            profile = base_style
            profile.novel_id = nid
            profile.writer_voice = data.get("writer_voice", "爆款网文")
            profile.knowledge_base = data.get("knowledge_base", "")
            profile.thought_system = data.get("thought_system", "")
            profile.central_question = data.get("central_question", "")
            db.save_style_profile(nid, asdict(profile))
    except Exception:
        pass
    return _summary(novel)


@router.get("/api/novels/{novel_id}")
def get_novel(novel_id: str) -> dict:
    novel = db.get_novel(novel_id)
    if not novel:
        raise HTTPException(404, "Not found")
    d = _summary(novel)
    d["chapters"] = novel.get("chapters", [])
    d["world"] = {
        "name": novel.get("world_name",""), "era": novel.get("world_era",""),
        "geography": novel.get("world_geo",""), "power_system": novel.get("power_system",""),
        "rules": novel.get("world_rules","") if isinstance(novel.get("world_rules"), list)
                else (json.loads(novel.get("world_rules","[]")) if novel.get("world_rules") else []),
        "main_arc": novel.get("main_arc",""), "current_arc": novel.get("current_arc","开篇"),
        "arc_chapter_start": novel.get("arc_chapter_start",1),
    }
    d["characters"] = novel.get("characters", [])
    d["factions"] = novel.get("factions", [])
    d["plot_points"] = novel.get("plot_points", [])
    d["character_relations"] = novel.get("character_relations", [])
    return d


@router.delete("/api/novels/{novel_id}")
def delete_novel(novel_id: str) -> dict:
    if not db.get_novel(novel_id):
        raise HTTPException(404, "Not found")
    db.soft_delete_novel(novel_id)
    return {"ok": True}


# ═══════════════ Chapters ═══════════════

@router.get("/api/novels/{novel_id}/chapters/{chapter_num}")
def get_chapter(novel_id: str, chapter_num: int) -> dict:
    ch = db.get_chapter(novel_id, chapter_num)
    if not ch:
        raise HTTPException(404, "Not found")
    key_events = ch.get("key_events", "[]")
    if isinstance(key_events, str):
        try:
            key_events = json.loads(key_events)
        except (json.JSONDecodeError, TypeError):
            key_events = []
    return {
        "number": ch["number"],
        "content": ch.get("content", ""),
        "title": ch.get("title", ""),
        "ending_hook": ch.get("ending_hook", ""),
        "key_events": key_events,
        "summary": ch.get("summary", ""),
    }


@router.put("/api/novels/{novel_id}/chapters/{chapter_num}")
def save_chapter(novel_id: str, chapter_num: int, data: dict) -> dict:
    if not db.get_novel(novel_id):
        raise HTTPException(404, "Not found")
    new_content = data.get("content", "")
    # Track edit for Voice Profile learning
    try:
        old = db.get_chapter(novel_id, chapter_num)
        if old and old.get("content") and old["content"] != new_content:
            db.save_voice_sample(novel_id, chapter_num, old["content"][:500], new_content[:500])
    except Exception:
        pass
    db.update_chapter(novel_id, chapter_num, content=new_content,
                      edit_ratio=data.get("edit_ratio", 0))
    return {"ok": True}


# ═══════════════ Generate ═══════════════

# In-memory store for chapter generation directions
_gen_directions: dict[str, str] = {}

# In-memory store for agent pipeline results (keyed by novel_id)
_constraints_cache: dict[str, str] = {}

@router.post("/api/novels/{novel_id}/generate")
def trigger_generate(novel_id: str, background: BackgroundTasks, data: dict = {}) -> dict:
    if not db.get_novel(novel_id):
        raise HTTPException(404)
    direction = (data or {}).get("direction", "").strip()
    if direction:
        _gen_directions[novel_id] = direction
    # Soul injection
    soul_injection = (data or {}).get("soul_injection", "").strip()
    if soul_injection:
        _gen_directions[novel_id + "_soul"] = soul_injection
    # Quality threshold
    quality_threshold = float((data or {}).get("quality_threshold", 0.8))
    _gen_directions[novel_id + "_qthreshold"] = str(quality_threshold)
    # Model override
    model_override = (data or {}).get("model", "").strip()
    if model_override:
        _gen_directions[novel_id + "_model"] = model_override
    # Constraint compression level (L0/L1/L2/L3/none, default L1)
    compression = (data or {}).get("compression", "").strip().upper()
    if compression in ("L0", "L1", "L2", "L3", "NONE"):
        _gen_directions[novel_id + "_compression"] = compression
    background.add_task(_run_generation, novel_id)
    ch_count = len(db.get_novel(novel_id).get("chapters", []))
    return {"status": "generating", "novel_id": novel_id, "next_chapter": ch_count + 1}


@router.get("/api/novels/{novel_id}/report")
def quality_report(novel_id: str) -> dict:
    """生成出版前质检报告：整体评估、强项、弱项、出版建议。"""
    novel = db.get_novel(novel_id)
    if not novel: raise HTTPException(404)
    gen_chs = [c for c in novel.get("chapters",[]) if c.get("word_count",0) > 0]
    if len(gen_chs) < 3: return {"error": "至少需要3章才能生成报告"}

    scores = [c.get("quality_score",0) for c in gen_chs]
    titles = [c.get("title","") for c in gen_chs]
    avg_q = sum(scores)/len(scores)
    min_ch = min(range(len(scores)), key=lambda i: scores[i])
    max_ch = max(range(len(scores)), key=lambda i: scores[i])
    trend = "上升" if scores[-1] > scores[0] else "下降" if scores[-1] < scores[0] else "平稳"

    # Weak chapter analysis
    weak = [(c["number"], c.get("quality_score",0), c.get("title","")) for c in gen_chs if c.get("quality_score",0) < 0.7]
    strong = [(c["number"], c.get("quality_score",0), c.get("title","")) for c in gen_chs if c.get("quality_score",0) >= 0.82]

    # Title candidates
    try:
        from ..config import Config
        from ..generator import Generator
        provider = _get_provider(novel_id)
        cfg = Config(openai_api_key=provider.get("api_key",""), openai_base_url=provider.get("base_url",""),
                     model=provider.get("models","deepseek-v4-pro")[0] if provider.get("models") else "gpt-4o")
        gen = Generator(cfg)
        titles_raw = gen._call_llm_with_retry([
            {"role":"system","content":"你是一位出版编辑。基于小说内容生成5个备选书名，每个2-6字，有意象感。只输出书名，每行一个。"},
            {"role":"user","content": f"小说简介：{novel.get('synopsis','')}\n核心追问：{db.get_style_profile(novel_id).get('central_question','') if db.get_style_profile(novel_id) else ''}\n已有章节标题：{'、'.join(titles[:10])}"}
        ], max_tokens=256)
    except Exception:
        titles_raw = ""

    return {
        "overview": {"total_chapters": len(gen_chs), "total_words": novel.get("total_words",0),
                     "avg_quality": round(avg_q,2), "trend": trend},
        "strongest": f"第{gen_chs[max_ch]['number']}章「{titles[max_ch]}」(评分{scores[max_ch]:.2f})",
        "weakest": f"第{gen_chs[min_ch]['number']}章「{titles[min_ch]}」(评分{scores[min_ch]:.2f})",
        "weak_chapters": weak,
        "strong_chapters": strong,
        "title_candidates": [t.strip() for t in titles_raw.split('\n') if t.strip() and len(t.strip())<=10][:5] if titles_raw else [],
        "recommendation": "建议发布" if avg_q >= 0.75 else "建议经典模式重写弱章后再发布" if avg_q >= 0.65 else "建议大面积重写——整体质量不达标",
        "pipeline_ready": avg_q >= 0.7 and len(gen_chs) >= 10,
    }


@router.post("/api/ab-test")
def ab_test_opening(data: dict, background: BackgroundTasks) -> dict:
    """A/B test: generate chapter 1 with multiple writer voices, find optimal."""
    synopsis = data.get("synopsis", "").strip()
    genre = data.get("genre", "玄幻")
    voices = data.get("voices", None)  # None = test all
    if not synopsis: raise HTTPException(400, "synopsis required")
    background.add_task(_run_ab_test, synopsis, genre, voices)
    return {"status": "testing", "message": f"正在测试{len(voices) if voices else 14}种作家声音..."}


@router.post("/api/novels/{novel_id}/final-polish")
def final_polish(novel_id: str, background: BackgroundTasks) -> dict:
    """出版前终极打磨——全本一致性检查+首尾呼应+重复短语清理。"""
    novel = db.get_novel(novel_id)
    if not novel: raise HTTPException(404)
    background.add_task(_run_final_polish, novel_id)
    return {"status": "polishing", "novel_id": novel_id, "message": "出版前终极打磨中..."}


@router.post("/api/novels/{novel_id}/polish")
def polish_novel(novel_id: str, background: BackgroundTasks) -> dict:
    """全本精修：微调每章的小问题——不一致的称呼、突兀的过渡、冗余短语。"""
    novel = db.get_novel(novel_id)
    if not novel: raise HTTPException(404)
    background.add_task(_run_polish, novel_id)
    return {"status": "polishing", "novel_id": novel_id}


@router.get("/api/novels/{novel_id}/classic-assessment")
def classic_assessment(novel_id: str) -> dict:
    """经典潜质评估：前5章综合评判，低于门槛则建议推倒重来。"""
    novel = db.get_novel(novel_id)
    if not novel: raise HTTPException(404)
    gen_chs = [c for c in novel.get("chapters",[]) if c.get("word_count",0) > 0]
    if len(gen_chs) < 5: return {"ready": False, "reason": f"需要至少5章(当前{len(gen_chs)})"}

    first5 = gen_chs[:5]
    scores = [c.get("quality_score",0) for c in first5]
    avg_q = sum(scores) / len(scores)
    min_q = min(scores)
    # Extra checks
    titles = [c.get("title","") for c in first5]
    has_variety = len(set(titles[:3])) >= 2  # First 3 titles shouldn't all be similar
    # Opening quality
    from ..config import Config
    from ..generator import Generator
    gen = Generator(Config())
    opener_check = Generator._classic_check.__func__(None, first5[0].get("content","")[:500], None, None) if first5[0].get("content") else (True, [])  # type: ignore[attr-defined]
    opening_ok = opener_check[0] if isinstance(opener_check, tuple) else True
    opening_issues = opener_check[1] if isinstance(opener_check, tuple) and len(opener_check) > 1 else []

    # Decision
    threshold = 0.78
    passed = avg_q >= threshold and min_q >= 0.65 and has_variety and opening_ok

    return {
        "passed": passed,
        "avg_quality": round(avg_q, 2),
        "min_quality": round(min_q, 2),
        "title_variety": has_variety,
        "opening_ok": opening_ok,
        "opening_issues": opening_issues,
        "threshold": threshold,
        "recommendation": "✅ 经典潜质达标，可以继续" if passed else
                         f"❌ 建议推倒重来（均分{avg_q:.2f}<{threshold}）" if avg_q < threshold else
                         "⚠️ 部分指标不达标，建议针对性修改",
    }


@router.post("/api/novels/{novel_id}/evolve")
def evolve_novel(novel_id: str, background: BackgroundTasks) -> dict:
    """进化模式：如果不达标→自动换参数推倒重来，直到达标或达到最大迭代次数。"""
    novel = db.get_novel(novel_id)
    if not novel: raise HTTPException(404)
    background.add_task(_run_evolve, novel_id)
    return {"status": "evolving", "novel_id": novel_id}


@router.post("/api/novels/extract-dna")
def extract_narrative_dna(data: dict) -> dict:
    """从一本已有的小说中提取叙事基因。data.source_novel_id: 源小说ID。"""
    source_id = data.get("source_novel_id", "")
    if not source_id: raise HTTPException(400, "source_novel_id required")
    novel = db.get_novel(source_id)
    if not novel: raise HTTPException(404)
    gen_chs = [c for c in novel.get("chapters",[]) if c.get("word_count",0) > 0]
    if len(gen_chs) < 3: raise HTTPException(400, "源小说至少3章")

    from ..config import Config
    from ..generator import Generator
    provider = _get_provider(source_id)
    cfg = Config(openai_api_key=provider.get("api_key",""), openai_base_url=provider.get("base_url",""),
                 model=provider.get("models","deepseek-v4-pro")[0] if provider.get("models") else "gpt-4o")
    gen = Generator(cfg)
    target_genre = data.get("target_genre", "")
    samples = [{"title": c["title"], "word_count": c["word_count"],
                "content": c.get("content","")[:800]} for c in gen_chs[:5]]
    dna = gen.extract_narrative_dna(samples, target_genre)

    # Save DNA to file
    import json as _json
    from pathlib import Path
    (Path("data")/"narrative_dna").mkdir(exist_ok=True)
    (Path("data")/"narrative_dna"/f"{source_id}.json").write_text(_json.dumps(dna, ensure_ascii=False, indent=2))

    # Auto-apply to target if specified
    target_id = data.get("target_novel_id", "")
    if target_id and dna and "error" not in dna:
        sd = db.get_style_profile(target_id)
        if sd:
            rules = sd.get("special_rules", [])
            if "structure_type" in dna:
                rules.append(f"叙事结构类型：{dna.get('structure_type','')}")
            if "hook_pattern" in dna:
                rules.append(f"钩子模式：{dna.get('hook_pattern','')}")
            sd["special_rules"] = rules
            db.save_style_profile(target_id, sd)

    return {"dna": dna, "saved_to": f"data/narrative_dna/{source_id}.json",
            "applied_to": target_id if target_id else None}


@router.post("/api/novels/{novel_id}/import-chapters")
def import_chapters(novel_id: str, data: dict) -> dict:
    """从纯文本导入章节——每章用 --- 分隔，第一行是标题。"""
    if not db.get_novel(novel_id): raise HTTPException(404)
    text = data.get("text", "").strip()
    if not text: raise HTTPException(400, "text required")
    blocks = text.split("\n---\n")
    imported = 0
    for i, block in enumerate(blocks, 1):
        lines = block.strip().split("\n")
        title = lines[0].strip() if lines else f"第{i}章"
        content = "\n".join(lines[1:]).strip() if len(lines) > 1 else ""
        if content:
            db.add_chapter(novel_id=novel_id, number=i, title=title,
                          word_count=len(content), summary=content[:200],
                          content=content)
            imported += 1
    return {"imported": imported, "novel_id": novel_id}


@router.post("/api/novels/search")
def search_novels(data: dict) -> dict:
    """全文搜索：在标题、简介、章节内容中搜索关键词。"""
    q = data.get("q", "").strip()
    if not q: return {"results": []}
    novels = db.list_novels()
    results = []
    for n in novels:
        score = 0
        if q in n["title"]: score += 100
        if q in n.get("synopsis",""): score += 50
        chs = n.get("chapters", [])
        for c in chs:
            if q in c.get("title",""): score += 20
            if q in (c.get("content","") or "")[:5000]: score += 5
        if score > 0:
            results.append({"id": n["id"], "title": n["title"], "score": score, "genre": n.get("genre","")})
    results.sort(key=lambda x: x["score"], reverse=True)
    return {"results": results[:20]}


@router.get("/api/novels/{novel_id}/spellcheck")
def spellcheck_novel(novel_id: str) -> dict:
    """基础拼写/语法检查——检测重复词、疑似错别字、AI套话。"""
    novel = db.get_novel(novel_id)
    if not novel: raise HTTPException(404)
    chs = [c for c in novel.get("chapters",[]) if c.get("word_count",0) > 0]
    issues = []
    all_text = " ".join(c.get("content","") for c in chs[-5:])
    # Check AI clichés
    cliches = ["在这个世界","随着时间","不仅如此","总而言之","毫无疑问","值得注意的是","换句话说"]
    for cw in cliches:
        if cw in all_text:
            issues.append({"type": "cliche", "text": cw, "count": all_text.count(cw)})
    # Check repeated words (>5 occurrences in 5000 chars)
    import re
    words = re.findall(r'[一-鿿]{2}', all_text[:5000])
    word_freq: dict[str, int] = {}
    for w in words:
        word_freq[w] = word_freq.get(w, 0) + 1
    for w, c in word_freq.items():
        if c >= 8:
            issues.append({"type": "repetition", "text": w, "count": c})
    return {"issues": issues, "total_chapters_checked": len(chs)}


@router.get("/api/novels/{novel_id}/algorithm-optimize")
def algorithm_optimize(novel_id: str) -> dict:
    """番茄推荐引擎优化建议——基于平台算法最看重的指标。"""
    novel = db.get_novel(novel_id)
    if not novel: raise HTTPException(404)
    gen_chs = [c for c in novel.get("chapters",[]) if c.get("word_count",0) > 0]
    issues = []
    tips = []

    # 1. Chapter length consistency (算法喜欢稳定更新)
    if gen_chs:
        lengths = [c["word_count"] for c in gen_chs]
        avg = sum(lengths)/len(lengths)
        if max(lengths) > avg * 1.8 or min(lengths) < avg * 0.5:
            issues.append("章节长度波动过大——算法会降低推荐权重。建议每章控制在均长±30%以内。")
        if avg < 1800:
            tips.append("章节偏短(<1800字)——番茄算法优先推荐2000+字的章节")
        elif avg > 3500:
            tips.append("章节偏长(>3500字)——手机阅读最佳体验是1500-2500字，过长降低完读率")

    # 2. Update frequency (日更=加权)
    tips.append("每天固定时间发布2章=算法加权20-30%。建议设置自动日更。")

    # 3. First 3 chapters (首秀决定生死)
    if len(gen_chs) >= 3:
        first3_scores = [c.get("quality_score",0) for c in gen_chs[:3]]
        if sum(first3_scores)/3 < 0.75:
            issues.append("前3章质量不达标(均分<0.75)——番茄首秀流量取决于前3章完读率。建议经典模式重写前3章")

    # 4. Hook analysis (追读率核心)
    if gen_chs:
        hooks = [c.get("ending_hook","") for c in gen_chs[-5:]]
        strong_hooks = sum(1 for h in hooks if len(h) > 30 and ('？' in h or '！' in h or '……' in h))
        if strong_hooks < 3:
            issues.append(f"最近5章有{5-strong_hooks}章结尾钩子偏弱——追读率会下降，算法会减少推荐")

    # 5. Interaction bait (评论区活跃=加权)
    tips.append("每5章在结尾加一句'读者提问'——如'你觉得他做得对吗？评论区见'——提升互动率=算法加权")

    # 6. Category optimization
    genre = novel.get("genre","玄幻")
    genre_tips = {
        "玄幻": "玄幻读者偏好每章1个修炼突破/丹药获得/打脸场景——缺这个完读率直接降",
        "都市": "都市读者偏好现实冲突——权力博弈、金钱交易、人际关系暗流",
        "悬疑": "悬疑读者偏好信息差——每章给一点但又不够，让他们一直猜",
        "科幻": "科幻读者偏好概念的深度——不要用'量子'糊弄，用数据和逻辑",
    }
    if genre in genre_tips:
        tips.append(genre_tips[genre])

    return {
        "novel_id": novel_id, "genre": genre,
        "chapters": len(gen_chs), "words": novel.get("total_words",0),
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


@router.get("/api/market-trends")
def market_trends() -> dict:
    """市场风向：当前热门的体裁、题材、风格组合建议。"""
    return {
        "hot_genres": [
            {"genre":"AI科幻","reason":"AI话题全民关注，番茄搜索量月增300%","competition":"低（同质化少）"},
            {"genre":"官场反腐","reason":"现实题材政策扶持+读者偏好深度内容","competition":"中"},
            {"genre":"悬疑推理","reason":"短剧改编需求旺盛，悬疑类转化率最高","competition":"高"},
            {"genre":"女性职场","reason":"她经济持续升温，轻治愈+成长线","competition":"低"},
            {"genre":"末世生存","reason":"全球不确定性推高生存类阅读，硬核末世缺口大","competition":"中"},
        ],
        "recommended_combos": [
            {"genre":"AI科幻","voice":"刘慈欣","question":"当AI比人类更懂爱，人类还剩下什么"},
            {"genre":"官场反腐","voice":"东野圭吾","question":"一个好人能在坏制度里坚持多久"},
            {"genre":"悬疑推理","voice":"余华","question":"如果真相会让你恨自己，你还想知道吗"},
        ],
        "updated": __import__("datetime").datetime.now().isoformat(),
    }


@router.get("/api/novels/{novel_id}/preview")
def preview_chapter(novel_id: str) -> dict:
    """章节预览：生成200字样本展示风格和声音，不消耗完整生成费用。"""
    novel = db.get_novel(novel_id)
    if not novel: raise HTTPException(404)
    from ..config import Config
    from ..generator import Generator
    provider = _get_provider(novel_id)
    cfg = Config(openai_api_key=provider.get("api_key",""), openai_base_url=provider.get("base_url",""),
                 model=provider.get("models","deepseek-v4-pro")[0] if provider.get("models") else "gpt-4o")
    gen = Generator(cfg)
    _load_state(novel_id)  # Note: load and discard, state is not needed for preview
    sample = gen._call_llm_with_retry([
        {"role":"system","content":"你是小说家。写200字的章节开头——展示风格、声音和节奏。这是给编辑看的样本，不需要完整章节。"},
        {"role":"user","content": f"书名：{novel['title']}\n简介：{novel.get('synopsis','')}\n请写200字开篇样本。"}
    ], max_tokens=400)
    return {"preview": sample[:400]}


@router.get("/api/novels/{novel_id}/reading-stats")
def reading_stats(novel_id: str) -> dict:
    """阅读统计：预估阅读时间、可读性、章节长度分布。"""
    novel = db.get_novel(novel_id)
    if not novel: raise HTTPException(404)
    gen_chs = [c for c in novel.get("chapters",[]) if c.get("word_count",0) > 0]
    if not gen_chs: return {"error": "No chapters"}
    total = sum(c["word_count"] for c in gen_chs)
    lengths = [c["word_count"] for c in gen_chs]
    avg_len = sum(lengths)/len(lengths)
    # Chinese reading speed: ~400 chars/min
    reading_minutes = total / 400
    # Length consistency
    variance = sum((l - avg_len)**2 for l in lengths) / len(lengths)
    std_dev = variance ** 0.5
    consistency = "优秀" if std_dev < avg_len * 0.3 else "良好" if std_dev < avg_len * 0.5 else "需改善"
    return {
        "total_words": total, "chapters": len(gen_chs),
        "avg_chapter_length": round(avg_len), "std_dev": round(std_dev),
        "consistency": consistency,
        "estimated_reading_time": f"{int(reading_minutes//60)}小时{int(reading_minutes%60)}分钟",
        "longest": f"第{lengths.index(max(lengths))+1}章({max(lengths)}字)",
        "shortest": f"第{lengths.index(min(lengths))+1}章({min(lengths)}字)",
    }


@router.post("/api/novels/{novel_id}/compare")
def compare_chapters(novel_id: str, data: dict) -> dict:
    """并排对比两个版本的同一章节。ch1, ch2: 章节号。返回并排diff。"""
    ch1_num = data.get("ch1", 0)
    ch2_num = data.get("ch2", 0)
    if not ch1_num: raise HTTPException(400, "ch1 required")
    ch1 = db.get_chapter(novel_id, ch1_num)
    if not ch1: raise HTTPException(404, f"Chapter {ch1_num} not found")
    if ch2_num:
        ch2 = db.get_chapter(novel_id, ch2_num)
    else:
        # Compare latest version vs original
        versions = db.get_chapter_versions(novel_id, ch1_num)
        if len(versions) >= 2:
            ch2 = {"title": ch1["title"], "word_count": versions[-1]["word_count"],
                   "content": db.get_chapter_version_content(versions[-1]["id"])}
        else:
            ch2 = {"title": ch1["title"], "word_count": ch1["word_count"], "content": ch1.get("content","")}
    return {
        "left": {"number": ch1_num, "title": ch1["title"], "words": ch1["word_count"],
                 "preview": (ch1.get("content","") or "")[:300]},
        "right": {"number": ch2_num or f"v{len(db.get_chapter_versions(novel_id,ch1_num))}",
                  "title": ch2.get("title",""), "words": ch2.get("word_count",0),
                  "preview": (ch2.get("content","") or "")[:300]},
    }


@router.get("/api/novels/{novel_id}/check-ending")
def check_ending(novel_id: str) -> dict:
    """检测小说是否已到达自然结局——伏笔回收率、角色弧完成度、情绪曲线闭合度。"""
    novel = db.get_novel(novel_id)
    if not novel: raise HTTPException(404)
    gen_chs = [c for c in novel.get("chapters",[]) if c.get("word_count",0) > 0]
    if len(gen_chs) < 5: return {"ready": False, "reason": "章节不足5章"}

    # Check signals
    from ..config import Config
    from ..generator import Generator
    state = _load_state(novel_id)
    if not state: return {"ready": False, "reason": "无法加载状态"}
    gen2 = Generator(Config())
    audit = gen2.audit_foreshadowing(state)
    open_count = audit.get("total_open", 99)
    stale = audit.get("stale", [])
    last_chs = gen_chs[-3:]
    avg_q = sum(c.get("quality_score",0) for c in last_chs) / len(last_chs)
    # Ending readiness: few open foreshadowing + last chapters have high quality
    ready = open_count <= 3 and avg_q >= 0.7
    return {
        "ready": ready,
        "open_foreshadowing": open_count,
        "stale_foreshadowing": len(stale),
        "recent_avg_quality": round(avg_q, 2),
        "recommendation": "可以收尾" if ready else f"还有{open_count}条伏笔未回收，建议继续生成",
    }


@router.post("/api/novels/{novel_id}/world-bible")
def generate_world_bible(novel_id: str, background: BackgroundTasks) -> dict:
    """从简介自动生成完整世界观设定——世界背景、修炼体系、势力分布、角色关系网。"""
    novel = db.get_novel(novel_id)
    if not novel: raise HTTPException(404)
    background.add_task(_run_world_bible, novel_id)
    return {"status": "generating", "novel_id": novel_id}


@router.post("/api/novel-farm")
def novel_farm(data: dict, background: BackgroundTasks) -> dict:
    """批量种书：一次创建多本小说，不同体裁+不同声音，生成后横向对比评分。"""
    seeds = data.get("seeds", [])
    if not seeds: raise HTTPException(400, "seeds required")
    created = []
    import time as _t
    for i, seed in enumerate(seeds):
        nid = f"farm-{int(_t.time())%100000 + i}"
        from ..generator import random_protagonist_name
        name, _ = random_protagonist_name(seed.get("genre","玄幻"))
        db.create_novel(id=nid, title=seed.get("title", f"农场第{i+1}本"),
                        synopsis=seed.get("synopsis",""), genre=seed.get("genre","玄幻"),
                        char_key="protagonist", name=name, role="主角")
        # Set writer voice
        voice = seed.get("voice", "爆款网文")
        from dataclasses import asdict

        from ..generator import _get_style_for_genre
        style = _get_style_for_genre(seed.get("genre","玄幻"))
        style.novel_id = nid
        style.writer_voice = voice
        db.save_style_profile(nid, asdict(style))
        created.append(nid)
        background.add_task(_run_generation, nid)
    return {"status": "farming", "novels": created, "message": f"种下{len(created)}本书，正在生长..."}


@router.get("/api/novels/{novel_id}/export-full")
def export_full_novel(novel_id: str) -> dict:
    """导出完整小说数据（可跨实例迁移）——含所有章节、设定、角色、版本历史。"""
    novel = db.get_novel(novel_id)
    if not novel: raise HTTPException(404)
    import json as _json
    data = {
        "novel": {k: v for k, v in novel.items() if k != "chapters"},
        "chapters": [{"number": c["number"], "title": c["title"], "content": c.get("content",""),
                      "word_count": c["word_count"], "quality_score": c.get("quality_score"),
                      "generated_at": c.get("generated_at")}
                     for c in novel.get("chapters",[]) if c.get("word_count",0) > 0],
        "style_profile": db.get_style_profile(novel_id),
        "characters": novel.get("characters",[]),
        "factions": novel.get("factions",[]),
        "versions": {str(c["number"]): db.get_chapter_versions(novel_id, c["number"])
                     for c in novel.get("chapters",[]) if c.get("word_count",0) > 0},
    }
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse(_json.dumps(data, ensure_ascii=False, indent=2),
                             media_type="application/json",
                             headers={"Content-Disposition": f"attachment; filename={novel_id}_full.json"})


@router.post("/api/novels/{novel_id}/chapters/reorder")
def reorder_chapters(novel_id: str, data: dict) -> dict:
    """重排章节顺序。data.order = {old_number: new_number, ...}"""
    if not db.get_novel(novel_id): raise HTTPException(404)
    order = data.get("order", {})
    for old_num, new_num in order.items():
        with db.conn() as c:
            c.execute("UPDATE chapters SET number=? WHERE novel_id=? AND number=?",
                     (new_num, novel_id, int(old_num)))
    return {"ok": True}


@router.get("/api/novels/{novel_id}/timeline")
def book_timeline(novel_id: str) -> dict:
    """书的创作历程——从创建到每一章的生成、修改、评分变化。"""
    novel = db.get_novel(novel_id)
    if not novel: raise HTTPException(404)
    gen_chs = [c for c in novel.get("chapters",[]) if c.get("word_count",0) > 0]
    # Get version history
    timeline = [{
        "event": "created", "time": novel.get("created_at", ""),
        "detail": f"创建《{novel['title']}》({novel['genre']})"
    }]
    for ch in gen_chs:
        versions = db.get_chapter_versions(novel_id, ch["number"])
        q = ch.get("quality_score", 0)
        timeline.append({
            "event": "chapter_generated",
            "chapter": ch["number"], "title": ch["title"],
            "words": ch["word_count"], "quality": q,
            "time": ch.get("generated_at", ""),
            "revisions": len(versions),
        })
    return {"novel_id": novel_id, "title": novel["title"], "timeline": timeline}


@router.get("/api/novels/{novel_id}/packaging")
def generate_packaging(novel_id: str) -> dict:
    """生成书的简介、书名备选、封面描述——读者看到的第一印象。"""
    novel = db.get_novel(novel_id)
    if not novel: raise HTTPException(404)
    gen_chs = [c for c in novel.get("chapters",[]) if c.get("word_count",0) > 0]
    synopsis = novel.get("synopsis","")
    titles = [c.get("title","") for c in gen_chs[:5]]
    total_words = novel.get("total_words",0)

    from ..config import Config
    from ..generator import Generator
    provider = _get_provider(novel_id)
    cfg = Config(openai_api_key=provider.get("api_key",""), openai_base_url=provider.get("base_url",""),
                 model=provider.get("models","deepseek-v4-pro")[0] if provider.get("models") else "gpt-4o")
    gen = Generator(cfg)

    # Generate blurb
    blurb_prompt = f"""你是顶级出版编辑。为以下小说写一段200字以内的简介，让读者在3秒内想点开看。
简介不能剧透关键转折，但要暗示核心冲突。要有节奏感——短句+悬念。

书名：{novel.get('title','')}
设定：{synopsis[:300]}
核心追问：{db.get_style_profile(novel_id).get('central_question','') if db.get_style_profile(novel_id) else ''}
已有章节：{'、'.join(titles)}

简介："""

    blurb = ""
    try:
        blurb = gen._call_llm_with_retry([
            {"role":"system","content":"你是出版编辑，写简介要让人3秒内想点开。"},
            {"role":"user","content": blurb_prompt}
        ], max_tokens=300)
    except: pass

    # Generate title candidates
    titles_raw = ""
    try:
        titles_raw = gen._call_llm_with_retry([
            {"role":"system","content":"生成5个2-6字的小说书名。有意象感，不拗口。只输出书名。"},
            {"role":"user","content": f"简介：{synopsis}\n已有章名：{'、'.join(titles[:5])}"}
        ], max_tokens=128)
    except: pass

    # Generate cover concept
    cover_prompt = ""
    try:
        cover_prompt = gen._call_llm_with_retry([
            {"role":"system","content":"你是封面设计师。用一段英文描述这本书的封面设计方案，用于AI绘图工具。"},
            {"role":"user","content": f"""书名：{novel.get('title','')}
简介：{synopsis[:200]}
风格：{novel.get('genre','')}

请输出英文封面描述（用于Midjourney/DALL-E），包含：色调、构图、关键元素、情绪氛围。50-100 words。"""}
        ], max_tokens=200)
    except: pass

    return {
        "blurb": blurb.strip() if blurb else "",
        "title_candidates": [t.strip() for t in titles_raw.split('\n') if t.strip() and 2<=len(t.strip())<=10][:5] if titles_raw else [],
        "cover_concept": cover_prompt.strip() if cover_prompt else "",
        "stats": {"chapters": len(gen_chs), "words": total_words},
    }


@router.get("/api/novels/{novel_id}/export-epub")
def export_epub(novel_id: str) -> dict:
    """导出EPUB电子书——可直接上传到阅读平台或Kindle。"""
    novel = db.get_novel(novel_id)
    if not novel: raise HTTPException(404)
    gen_chs = [c for c in novel.get("chapters",[]) if c.get("word_count",0) > 0]
    if not gen_chs: raise HTTPException(400, "No chapters")

    # Build HTML-based EPUB content (EPUB is HTML+CSS in a ZIP)
    html_parts = [f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml">
<head><title>{novel['title']}</title>
<style>body{{font-family:serif;line-height:1.8;margin:2em}}h1{{text-align:center}}h2{{margin-top:2em}}.synopsis{{font-style:italic;color:#666}}</style></head>
<body>
<h1>{novel['title']}</h1>
<p class="synopsis">{novel.get('synopsis','')}</p>"""]
    for ch in gen_chs:
        content = ch.get("content","")
        # Strip markdown headers from body
        import re
        content = re.sub(r'^#+\s*.*$', '', content, flags=re.MULTILINE).strip()
        html_parts.append(f"<h2>第{ch['number']}章 {ch['title']}</h2>")
        for para in content.split('\n'):
            if para.strip():
                html_parts.append(f"<p>{para.strip()}</p>")
    html_parts.append("</body></html>")
    html = '\n'.join(html_parts)

    from fastapi.responses import PlainTextResponse
    fn = f"{novel['title']}_{len(gen_chs)}chapters.html"
    return PlainTextResponse(html, media_type="text/html; charset=utf-8",
                             headers={"Content-Disposition": f"attachment; filename*=UTF-8''{fn}"})


@router.get("/api/novels/{novel_id}/export-pdf")
def export_pdf(novel_id: str) -> dict:
    """导出PDF电子书——先尝试 weasyprint/pdfkit，否则返回带打印CSS的HTML。"""
    novel = db.get_novel(novel_id)
    if not novel: raise HTTPException(404)
    gen_chs = [c for c in novel.get("chapters",[]) if c.get("word_count",0) > 0]
    if not gen_chs: raise HTTPException(400, "No chapters")

    # Build HTML with print CSS for PDF
    html_parts = [f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>{novel['title']}</title>
<style>
  @page {{ size: A4; margin: 2cm; }}
  body {{ font-family: "Noto Serif CJK SC", "Songti SC", "SimSun", serif; line-height: 2; font-size: 12pt; color: #333; }}
  h1 {{ text-align: center; font-size: 18pt; margin-bottom: 0.5em; page-break-before: avoid; }}
  h2 {{ margin-top: 2em; font-size: 14pt; page-break-before: always; page-break-after: avoid; }}
  .synopsis {{ font-style: italic; color: #666; text-align: center; margin-bottom: 2em; }}
  p {{ text-indent: 2em; margin: 0.5em 0; }}
  @media print {{ body {{ font-size: 11pt; }} }}
</style></head>
<body>
<h1>{novel['title']}</h1>
<p class="synopsis">{novel.get('synopsis','')}</p>"""]
    for ch in gen_chs:
        content = ch.get("content","")
        import re
        content = re.sub(r'^#+\s*.*$', '', content, flags=re.MULTILINE).strip()
        html_parts.append(f"<h2>第{ch['number']}章 {ch['title']}</h2>")
        for para in content.split('\n'):
            if para.strip():
                html_parts.append(f"<p>{para.strip()}</p>")
    html_parts.append("</body></html>")
    html = '\n'.join(html_parts)

    # Try weasyprint first, then pdfkit
    pdf_bytes = None
    try:
        from weasyprint import HTML
        pdf_bytes = HTML(string=html).write_pdf()
    except ImportError:
        pass

    if pdf_bytes is None:
        try:
            import pdfkit
            pdf_bytes = pdfkit.from_string(html, False)
        except ImportError:
            pass

    if pdf_bytes:
        from fastapi.responses import Response
        fn_str = f"{novel['title']}_{len(gen_chs)}chapters.pdf"
        return Response(pdf_bytes, media_type="application/pdf",
                        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{fn_str}"})

    # Fallback: return HTML with print CSS, browser can print-to-PDF
    from fastapi.responses import PlainTextResponse
    fn_str = f"{novel['title']}_{len(gen_chs)}chapters_pdf.html"
    return PlainTextResponse(html, media_type="text/html; charset=utf-8",
                             headers={"Content-Disposition": f"attachment; filename*=UTF-8''{fn_str}"})


@router.get("/api/novels/{novel_id}/export-mobi")
def export_mobi(novel_id: str) -> dict:
    """导出MOBI电子书——需要Calibre的ebook-convert工具。"""
    novel = db.get_novel(novel_id)
    if not novel: raise HTTPException(404)
    gen_chs = [c for c in novel.get("chapters",[]) if c.get("word_count",0) > 0]
    if not gen_chs: raise HTTPException(400, "No chapters")

    # Build HTML content (same structure as epub)
    html_parts = [f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>{novel['title']}</title>
<style>body{{font-family:serif;line-height:1.8;margin:2em}}h1{{text-align:center}}h2{{margin-top:2em}}.synopsis{{font-style:italic;color:#666}}</style></head>
<body>
<h1>{novel['title']}</h1>
<p class="synopsis">{novel.get('synopsis','')}</p>"""]
    for ch in gen_chs:
        content = ch.get("content","")
        import re
        content = re.sub(r'^#+\s*.*$', '', content, flags=re.MULTILINE).strip()
        html_parts.append(f"<h2>第{ch['number']}章 {ch['title']}</h2>")
        for para in content.split('\n'):
            if para.strip():
                html_parts.append(f"<p>{para.strip()}</p>")
    html_parts.append("</body></html>")
    html = '\n'.join(html_parts)

    # Try calibre ebook-convert
    import os
    import subprocess
    import tempfile
    try:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as f:
            f.write(html)
            html_path = f.name

        mobi_path = html_path.replace('.html', '.mobi')
        result = subprocess.run(
            ['ebook-convert', html_path, mobi_path],
            capture_output=True, text=True, timeout=60
        )

        if result.returncode == 0 and os.path.exists(mobi_path):
            with open(mobi_path, 'rb') as f_mobi:
                mobi_bytes = f_mobi.read()
            os.unlink(html_path)
            os.unlink(mobi_path)
            from fastapi.responses import Response
            fn_str = f"{novel['title']}_{len(gen_chs)}chapters.mobi"
            return Response(mobi_bytes, media_type="application/x-mobipocket-ebook",
                            headers={"Content-Disposition": f"attachment; filename*=UTF-8''{fn_str}"})
        else:
            os.unlink(html_path)
            if os.path.exists(mobi_path):
                os.unlink(mobi_path)
    except FileNotFoundError:
        pass

    # Neither kindlegen nor calibre available
    raise HTTPException(501, "Install Calibre (https://calibre-ebook.com) for MOBI export. Run: brew install calibre")

@router.get("/api/analytics-dashboard")
def analytics_dashboard() -> dict:
    """生成分析看板：全局数据一览。"""
    novels = db.list_novels()
    total_chs = sum(n.get("total_chapters",0) for n in novels)
    total_words = sum(n.get("total_words",0) for n in novels)
    costs = db.get_cost_summary()
    # Per-novel stats
    novel_stats = []
    for n in novels:
        chs = n.get("chapters", [])
        gen = [c for c in chs if c.get("word_count",0) > 0]
        scores = [c.get("quality_score",0) for c in gen if c.get("quality_score")]
        novel_stats.append({
            "id": n["id"], "title": n["title"], "genre": n.get("genre","?"),
            "chapters": len(gen), "words": n.get("total_words",0),
            "avg_quality": round(sum(scores)/len(scores),2) if scores else 0,
            "status": "活跃" if gen else "空",
        })
    return {
        "global": {"novels": len(novels), "chapters": total_chs, "words": total_words,
                   "total_cost": round(costs.get("total_cost",0),4),
                   "total_llm_calls": costs.get("total_calls",0)},
        "novels": sorted(novel_stats, key=lambda x: x["words"], reverse=True),
    }


@router.get("/api/publishing-dashboard")
def publishing_dashboard() -> dict:
    """发布看板：哪些章节发布了、哪些失败、待发布队列。"""
    novels = db.list_novels()
    dashboard = []
    for n in novels:
        chs = n.get("chapters", [])
        gen = [c for c in chs if c.get("word_count",0) > 0]
        published = []
        failed = []
        with db.conn() as c:
            for ch in gen:
                pr = c.execute("SELECT success,error FROM publish_records WHERE chapter_id=? ORDER BY id DESC LIMIT 1",
                              (ch["id"],)).fetchone()
                if pr and pr["success"]:
                    published.append(ch["number"])
                elif pr:
                    failed.append({"chapter": ch["number"], "error": pr["error"] or "unknown"})
        dashboard.append({
            "novel_id": n["id"], "title": n["title"],
            "total": len(gen),
            "published": sorted(published),
            "pending": [c["number"] for c in gen if c["number"] not in published],
            "failed": failed,
        })
    return {"novels": dashboard}


@router.get("/api/daily")
def daily_digest() -> dict:
    """每日摘要：今天的系统做了什么。"""
    novels = db.list_novels()
    total_chs = sum(n.get("total_chapters",0) for n in novels)
    total_words = sum(n.get("total_words",0) for n in novels)
    costs = db.get_cost_summary()
    logs = db.get_logs(20)
    today_logs = [l for l in logs if "today" in str(l.get("created_at",""))[:10] or True][:5]
    return {
        "novels": len(novels), "total_chapters": total_chs, "total_words": total_words,
        "total_cost": round(costs.get("total_cost", 0), 4),
        "total_llm_calls": costs.get("total_calls", 0),
        "recent_events": [{"event": l.get("event",""), "detail": (l.get("detail","") or "")[:80]} for l in today_logs],
    }


@router.get("/api/novels/{novel_id}/diffs")
def chapter_diffs(novel_id: str) -> dict:
    """查看章节的修改历史——原版和修订版之间的差异。"""
    novel = db.get_novel(novel_id)
    if not novel: raise HTTPException(404)
    gen_chs = [c for c in novel.get("chapters",[]) if c.get("word_count",0) > 0]
    diffs = []
    for ch in gen_chs:
        versions = db.get_chapter_versions(novel_id, ch["number"])
        if len(versions) >= 2:
            v1 = db.get_chapter_version_content(versions[-1]["id"])
            v2 = db.get_chapter_version_content(versions[0]["id"])
            diffs.append({
                "chapter": ch["number"], "title": ch["title"],
                "original_words": versions[-1]["word_count"],
                "revised_words": versions[0]["word_count"],
                "versions": len(versions),
            })
    return {"diffs": diffs}


@router.get("/api/novels/{novel_id}/ask")
def ask_novel(novel_id: str, q: str = "") -> dict:
    """向自己的小说提问——基于RAG检索最相关的章节回答。"""
    if not q: raise HTTPException(400, "q required")
    from ..config import Config
    from ..generator import Generator
    provider = _get_provider(novel_id)
    cfg = Config(openai_api_key=provider.get("api_key",""), openai_base_url=provider.get("base_url",""),
                 model=provider.get("models","deepseek-v4-pro")[0] if provider.get("models") else "gpt-4o")
    gen = Generator(cfg)
    # RAG search
    context = gen.retrieve_relevant_context(q, novel_id, top_k=5)
    if not context:
        return {"answer": "未找到相关信息", "sources": []}
    ctx_text = '\n'.join(f"第{c.get('chapter_number','?')}章：{c.get('chunk_text','')[:300]}" for c in context)
    answer = gen._call_llm_with_retry([
        {"role":"system","content":"你正在回答关于你自己写的小说的问题。基于以下章节内容回答。如果信息不足，诚实说不知道。"},
        {"role":"user","content": f"问题：{q}\n\n相关章节：\n{ctx_text[:3000]}\n\n回答："}
    ], max_tokens=512)
    return {"answer": answer, "sources": [{"chapter": c.get("chapter_number"), "title": c.get("title")} for c in context]}


@router.get("/api/insights")
def cross_novel_insights() -> dict:
    """跨书自适应学习：从所有已生成小说中提取模式。"""
    novels = db.list_novels()
    insights: dict[str, Any] = {"total_novels": len(novels), "total_chapters": 0, "total_words": 0,
                "best_genres": [], "avg_quality_by_genre": {}, "cost_summary": db.get_cost_summary()}
    genre_scores: dict[str, list[float]] = {}
    for n in novels:
        chs = n.get("chapters", [])
        gen = [c for c in chs if c.get("word_count", 0) > 0]
        insights["total_chapters"] += len(gen)
        insights["total_words"] += sum(c.get("word_count", 0) for c in gen)
        g = n.get("genre", "其他")
        scores = [c.get("quality_score", 0) for c in gen if c.get("quality_score")]
        if scores:
            genre_scores.setdefault(g, []).extend(scores)
    for g, ss in genre_scores.items():
        insights["avg_quality_by_genre"][g] = round(sum(ss)/len(ss), 2)
    # Best genre
    best = max(genre_scores.items(), key=lambda x: sum(x[1])/len(x[1])) if genre_scores else ("N/A", [])
    insights["best_genre"] = best[0]
    insights["best_genre_avg"] = round(sum(best[1])/len(best[1]), 2) if best[1] else 0
    # Recommendation
    insights["recommendation"] = f"当前最优体裁: {best[0]}(均分{insights['best_genre_avg']})。建议新书优先选择此体裁。"
    return insights


@router.post("/api/novels/{novel_id}/pipeline")
def trigger_pipeline(novel_id: str, background: BackgroundTasks) -> dict:
    """自主出版管线：生成剩余章节 → 回修开头 → 识别弱章 → 经典重写 → 质量报告"""
    if not db.get_novel(novel_id):
        raise HTTPException(404)
    background.add_task(_run_pipeline, novel_id)
    return {"status": "pipeline", "novel_id": novel_id, "message": "自主管线启动"}


@router.get("/api/novels/{novel_id}/chapters/{chapter_num}/fact-check")
def fact_check_chapter(novel_id: str, chapter_num: int) -> dict:
    """AI幻觉检测：让AI自己审计章节中的事实性陈述。"""
    ch = db.get_chapter(novel_id, chapter_num)
    if not ch: raise HTTPException(404)
    novel = db.get_novel(novel_id)
    from ..config import Config
    from ..generator import Generator
    provider = _get_provider(novel_id)
    cfg = Config(openai_api_key=provider.get("api_key",""), openai_base_url=provider.get("base_url",""),
                 model=provider.get("models","deepseek-v4-pro")[0] if provider.get("models") else "gpt-4o")
    gen = Generator(cfg)
    result = gen.fact_check(ch.get("content",""), novel.get("genre",""))
    return result


@router.post("/api/novels/{novel_id}/chapters/{chapter_num}/humanize")
def humanize_chapter(novel_id: str, chapter_num: int, background: BackgroundTasks) -> dict:
    """深度去AI味——AI读自己的文字，找出不像人写的地方并修复。"""
    ch = db.get_chapter(novel_id, chapter_num)
    if not ch: raise HTTPException(404)
    background.add_task(_run_humanize, novel_id, chapter_num)
    return {"status": "humanizing", "novel_id": novel_id, "chapter": chapter_num}


@router.post("/api/novels/{novel_id}/chapters/{chapter_num}/revise")
def revise_chapter(novel_id: str, chapter_num: int, data: dict, background: BackgroundTasks) -> dict:
    """基于自然语言批评重写章节。"""
    ch = db.get_chapter(novel_id, chapter_num)
    if not ch: raise HTTPException(404, "Chapter not found")
    critique = data.get("critique", "").strip()
    if not critique: raise HTTPException(400, "critique required")
    background.add_task(_run_revise_chapter, novel_id, chapter_num, critique)
    return {"status": "revising", "novel_id": novel_id, "chapter": chapter_num}


@router.post("/api/novels/{novel_id}/revise-opening")
def trigger_revise_opening(novel_id: str, background: BackgroundTasks) -> dict:
    """全书生成完后，回头重写前3章——基于结局知识植入精准伏笔。"""
    if not db.get_novel(novel_id):
        raise HTTPException(404)
    background.add_task(_run_revise_opening, novel_id)
    return {"status": "revising", "novel_id": novel_id, "message": "正在基于结局重写前3章..."}


@router.post("/api/novels/{novel_id}/generate-classic")
def trigger_generate_classic(novel_id: str, background: BackgroundTasks) -> dict:
    """经典模式：生成多版，只通过≥0.75+经典检查+跨章一致的版本。"""
    if not db.get_novel(novel_id):
        raise HTTPException(404)
    background.add_task(_run_generation_classic, novel_id)
    return {"status": "generating_classic", "novel_id": novel_id}


@router.post("/api/novels/{novel_id}/generate-batch")
def trigger_generate_batch(novel_id: str, data: dict, background: BackgroundTasks) -> dict:
    if not db.get_novel(novel_id):
        raise HTTPException(404)
    count = data.get("count", 5)
    count = max(1, min(count, 20))  # cap at 20
    quality_threshold = float(data.get("quality_threshold", 0.8))

    # Check if a job is already queued/running for this novel
    existing = _get_queue_status(novel_id)
    if existing:
        raise HTTPException(409, f"已有任务进行中: {existing['job_id']} (状态: {existing['status']})")

    job_id = uuid.uuid4().hex[:12]
    ch_count = len(db.get_novel(novel_id).get("chapters", []))
    job = {
        "job_id": job_id,
        "novel_id": novel_id,
        "status": "queued",
        "progress": {"current": 0, "total": count},
        "count": count,
        "quality_threshold": quality_threshold,
        "last_error": None,
    }
    with _job_lock:
        _job_queue[job_id] = job
    thread = threading.Thread(target=_run_queue_job, args=(job,), daemon=True)
    thread.start()
    return {"job_id": job_id, "status": "queued", "count": count, "next_chapter": ch_count + 1}


@router.get("/api/novels/{novel_id}/generate/queue-status")
def generate_queue_status(novel_id: str) -> dict:
    """Get the current batch generation queue status for a novel."""
    queue_status = _get_queue_status(novel_id)
    if not queue_status:
        return {"job_id": None, "status": "idle", "progress": {"current": 0, "total": 0}, "last_error": None}
    return queue_status


def _run_generation(novel_id: str):
    """V3: Full generation pipeline with quality scoring, de-AI, and RAG"""
    try:
        _set_status(novel_id, "generating", "正在构思章节…（生成中，约需60秒）", 10)
        from ..config import Config
        from ..generator import Generator
        provider = _get_provider(novel_id)
        model_override = _gen_directions.pop(novel_id + "_model", "")
        model = model_override or (provider.get("models", "deepseek-v4-pro")[0] if provider.get("models") else "gpt-4o")
        cfg = Config(
            openai_api_key=provider.get("api_key", ""),
            openai_base_url=provider.get("base_url", ""),
            model=model,
        )
        gen = Generator(cfg)
        # Streaming callback: push partial content to status for live preview
        def on_stream(text: str):
            # Strip thinking tokens and clean
            clean = gen._strip_thinking(text)
            _gen_status[novel_id]["stream_content"] = clean[:8000]
        gen._on_stream_chunk = on_stream  # type: ignore[attr-defined]
        state = _load_state(novel_id)
        # Load style profile
        style = None
        try:
            from ..generator import StyleProfile, _get_style_for_genre
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
            with db.conn() as conn:
                rows = conn.execute(
                    "SELECT number, title, summary FROM chapters WHERE novel_id=? AND word_count=0 ORDER BY number LIMIT 5",
                    (novel_id,)
                ).fetchall()
                outline = [{"number": r["number"], "title": r["title"], "summary": r["summary"]} for r in rows]
        except Exception:
            pass

        # RAG: retrieve relevant context for better generation
        rag_context = gen.retrieve_relevant_context(
            query=state.plot.current_arc or state.plot.premise,
            novel_id=novel_id,
            top_k=5,
        )

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
        if soul_injection:
            author_direction = soul_injection + ("\n\n作者方向：" + author_direction if author_direction else "")
        # 【核心】Brain Agent + 约束压缩 —— 数据库写小说，AI只是笔
        next_ch = len([c for c in state.chapters if c.word_count > 0]) + 1
        brain = BrainAgent(db)
        constraint_result = brain.constraint_builder.run({
            "novel_id": novel_id, "chapter_num": next_ch, "db": db
        })
        compressor = ConstraintCompressor()
        # Configurable compression level (default L1, "NONE" to skip constraints)
        comp_level = _gen_directions.pop(novel_id + "_compression", "L1")
        if comp_level == "NONE":
            _set_status(novel_id, "generating", "正在生成候选版本…（无约束对照组）", 20)
        else:
            compressed = compressor.compress(constraint_result, comp_level)
            if compressed["text"]:
                author_direction = f"【硬约束】\n{compressed['text']}\n\n" + ("【作者方向】\n" + author_direction if author_direction else "")
            _set_status(novel_id, "generating", f"正在生成候选版本…（约束{compressed['char_count']}字）", 20)

        # 【技法顾问】场景分析 → 写作指导注入
        technique_guidance = ""
        try:
            from ..stations.novel.technique_advisor import TechniqueAdvisor
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
                technique_guidance = tech_result["guidance"]
                author_direction = author_direction + "\n\n【技法指导】\n" + technique_guidance
                print(f"[TECHNIQUE] {novel_id} Ch{next_ch}: {technique_guidance[:60]}...")
        except Exception as e:
            print(f"[TECHNIQUE] skipped: {e}")

        chapter, quality = gen.batch_generate(state, n=2, rag_context=rag_context, outline=outline, style=style, author_input=author_direction)
        gen_duration = (_time.time() - t0) * 1000
        body = chapter.content or chapter.summary

        # Retry with quality feedback if too low
        q_threshold = float(_gen_directions.pop(novel_id + "_qthreshold", "0.8"))
        retries = 0
        max_retries = 3 if q_threshold >= 0.8 else 2
        while quality['overall'] < q_threshold and retries < max_retries:
            retries += 1
            issues_str = '；'.join(quality.get('issues', ['质量不足']))
            print(f"[GEN] {novel_id} Q={quality['overall']} — retry #{retries}: {issues_str}")

            # Agent Engine: Editor review → targeted rewrite (first retry only)
            if retries == 1 and quality['overall'] >= 0.6:
                _set_status(novel_id, "reviewing", "编辑 Agent 审稿中…", 32)
                editor_result = _editor_review(novel_id, chapter.number, body, quality.get('issues', []))
                if editor_result.get('feedback'):
                    _set_status(novel_id, "generating", "根据编辑意见定向修改…", 37)
                    body = _targeted_rewrite(novel_id, chapter.number, body, editor_result['feedback'])
                    # Re-score after targeted fix
                    _set_status(novel_id, "reviewing", "重新评分…", 42)
                    quality = gen.score_quality(body, state, style)
                    print(f"[GEN] {novel_id} Editor round Q={quality['overall']}")
                    if quality['overall'] >= q_threshold:
                        break  # Editor fix succeeded

            # Fallback: full regenerate
            _set_status(novel_id, "generating", f"质量不足，正在重写…（第{retries+1}次）", 30 + retries * 15, quality['overall'])
            chapter, quality = gen.batch_generate(state, n=1, rag_context=rag_context, outline=outline, style=style)
            body = chapter.content or chapter.summary
            _set_status(novel_id, "reviewing", "正在质检评分…", 60)

        # Self-edit pass (LLM refines pacing/redundancy/transitions)
        _set_status(novel_id, "editing", "正在精修文稿…（约25秒）", 70)
        body = gen._self_edit(body, state, style)

        # De-AI post-processing — always apply
        cleaned_body, de_ai_changes = gen.de_ai(body)
        if de_ai_changes > 0:
            print(f"[GEN] {novel_id} de-AI: {de_ai_changes} changes")

        # Forced Specificity — replace generic phrases with concrete details
        _set_status(novel_id, "editing", "正在注入具体细节…", 65)
        specificity_prompt = f"""以下是一段小说正文。请找出文中所有模糊、笼统、模式化的描写（如"他很生气""她很难过""非常漂亮""异常强大"等），用具体、独特、五感可感知的细节替换它们。保持原意和风格不变。不要改变情节。

正文：
{cleaned_body or body}

请直接返回修改后的全文，不要加任何说明。"""
        try:
            from ..generator import Generator
            specificity_messages = [{"role": "user", "content": specificity_prompt}]
            specificity_result = gen._call_llm_with_retry(specificity_messages, max_tokens=8192)
            if specificity_result and len(specificity_result) > len(cleaned_body or body) * 0.7:
                body = specificity_result
                print(f"[GEN] {novel_id} forced specificity applied")
        except Exception as e:
            print(f"[GEN] {novel_id} specificity pass failed: {e}")

        # Pattern Disruption — for chapters 3+, break predictable patterns
        if chapter.number >= 3:
            try:
                disruption_prompt = f"""以下是一章小说正文。如果这一章的结构是"铺垫→冲突→解决→悬念"的标准模式，请在保持主线的前提下，做以下任一改变：
1. 把高潮提前到中间，后半段写余波
2. 用一句毫不相关的话结尾（但暗中与主题呼应）
3. 在最紧张的时刻插入一段平静的描写

如果文章结构已经独特，则保持不变。请直接返回全文。

正文：
{body}"""
                disruption_messages = [{"role": "user", "content": disruption_prompt}]
                disruption_result = gen._call_llm_with_retry(disruption_messages, max_tokens=8192)
                if disruption_result and len(disruption_result) > len(body) * 0.8:
                    body = disruption_result
                    print(f"[GEN] {novel_id} pattern disruption applied")
            except Exception as e:
                print(f"[GEN] {novel_id} disruption pass failed: {e}")

        # LLM Judge — final quality evaluation
        _set_status(novel_id, "judging", "正在 AI 评估质量…（约15秒）", 80)
        final_quality = gen.judge_quality(cleaned_body or body, state, style)
        if final_quality.get("method") == "llm":
            print(f"[GEN] {novel_id} LLM judge: {final_quality['grade']}({final_quality['overall']}) — {final_quality.get('judge_detail', {})}")

        # If LLM judge score is below threshold, retry with judge feedback
        judge_retries = 0
        while final_quality['overall'] < q_threshold and judge_retries < 2:
            judge_retries += 1
            issues_str = '；'.join(final_quality.get('issues', ['质量不足']))
            print(f"[GEN] {novel_id} LLM Judge Q={final_quality['overall']} — judge retry #{judge_retries}: {issues_str}")
            _set_status(novel_id, "generating", f"LLM 评审未达标，针对性重写…（第{judge_retries}次）", 50 + judge_retries * 15, final_quality['overall'])
            chapter, quality = gen.batch_generate(state, n=1, rag_context=rag_context, outline=outline, style=style, author_input=f"请改进以下问题：{issues_str}")
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

        # Save chapter
        cid = db.add_chapter(
            novel_id=novel_id, number=chapter.number, title=chapter.title,
            word_count=chapter.word_count, summary=chapter.summary,
            content=cleaned_body or chapter.content or chapter.summary, ending_hook=chapter.ending_hook,
            key_events=json.dumps(chapter.key_events),
            revelations=json.dumps(chapter.revelations),
            quality_score=final_quality['overall'], model_used=cfg.model,
        )

        # V7: Pre-generate TTS audio in background (non-blocking)
        try:
            import threading

            from .audiobook import _pregen_tts_background
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
            final_content = cleaned_body or chapter.content or chapter.summary
            _extract_story_bible(novel_id, chapter.number, final_content, chapter.title)
            _run_consistency_check(novel_id, chapter.number)
            # Foreshadowing auto-resolution: detect resolved threads
            try:
                from ..stations.novel.foreshadowing_resolver import ForeshadowingResolver
                resolver = ForeshadowingResolver()
                fs_result = resolver.run({
                    "novel_id": novel_id,
                    "chapter_num": chapter.number,
                    "chapter_content": final_content,
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
            _constraints_cache[novel_id] = _build_constraints(novel_id, chapter.number + 1)
        except Exception:
            pass

        # Extract character voices from generated chapter
        try:
            gen._extract_character_voices(cleaned_body or chapter.content or "", state)
        except Exception:
            pass

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
        _set_status(novel_id, "complete", quality_msg, 100)
        # Store extra quality data for frontend to fetch
        _gen_status[novel_id]["quality_detail"] = quality_detail
        _gen_status[novel_id]["grade"] = final_quality.get("grade", "?")
        _gen_status[novel_id]["overall"] = final_quality["overall"]
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
        err_msg = str(e)[:200]
        err_type = type(e).__name__
        tb = traceback.format_exc()[-300:]
        phase = f"chapter {(state.total_chapters + 1) if 'state' in dir() else 'unknown'}"

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
            from ..config import Config
            from ..generator import Generator
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

            # Simpler prompt: strip complex context, just use genre + recent hook
            simple_direction = f"写{state.genre}小说第{state.total_chapters + 1}章。保持风格一致。"
            prev_chapter = None
            try:
                chs = [c for c in state.chapters if c.word_count > 0]
                prev_chapter = chs[-1] if chs else None
            except Exception:
                pass
            if prev_chapter:
                simple_direction += f" 上章：{prev_chapter.title}。{prev_chapter.ending_hook}"

            chapter, quality = gen.batch_generate(state, n=1, author_input=simple_direction)
            body = chapter.content or chapter.summary

            # Light de-AI only
            try:
                cleaned_body, de_ai_changes = gen.de_ai(body)
                if de_ai_changes > 0:
                    body = cleaned_body
            except Exception:
                pass

            # Save chapter
            cid = db.add_chapter(
                novel_id=novel_id, number=chapter.number, title=chapter.title,
                word_count=chapter.word_count, summary=chapter.summary,
                content=body, ending_hook=chapter.ending_hook,
                key_events=json.dumps(chapter.key_events) if chapter.key_events else "[]",
                revelations=json.dumps(chapter.revelations) if chapter.revelations else "[]",
                quality_score=quality.get("overall", 0.7), model_used=cfg.model,
            )

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


def _run_revise_opening(novel_id: str):
    """Background: revise opening chapters with full-book knowledge."""
    try:
        _set_status(novel_id, "revising", "正在基于结局重写前3章…")
        from ..config import Config
        from ..generator import Generator
        provider = _get_provider(novel_id)
        cfg = Config(openai_api_key=provider.get("api_key",""), openai_base_url=provider.get("base_url",""),
                     model=provider.get("models","deepseek-v4-pro")[0] if provider.get("models") else "gpt-4o")
        gen = Generator(cfg)
        state = _load_state(novel_id)
        if not state or state.total_chapters < 5:
            _set_status(novel_id, "error", "至少需要5章才能回修开头")
            return
        style = None
        try:
            from ..generator import StyleProfile
            sd = db.get_style_profile(novel_id)
            if sd: style = StyleProfile(**{k:v for k,v in sd.items() if k in StyleProfile.__dataclass_fields__})
        except: pass

        revised = gen.revise_opening(state, target_chapters=3, style=style)
        for ch in revised:
            db.update_chapter(novel_id, ch.number, content=ch.content,
                            word_count=ch.word_count)
            db.log(novel_id, "chapter.revised", {"chapter": ch.number})
        _set_status(novel_id, "complete", f"前{len(revised)}章回修完成")
    except Exception as e:
        _set_status(novel_id, "error", str(e)[:200])


def _run_humanize(novel_id: str, chapter_num: int):
    """Background: deep humanize a chapter."""
    from ..config import Config
    from ..generator import Generator
    provider = _get_provider(novel_id)
    cfg = Config(openai_api_key=provider.get("api_key",""), openai_base_url=provider.get("base_url",""),
                 model=provider.get("models","deepseek-v4-pro")[0] if provider.get("models") else "gpt-4o")
    gen = Generator(cfg)
    ch = db.get_chapter(novel_id, chapter_num)
    if not ch: return
    content = ch.get("content","")
    if not content: return
    humanized = gen.humanize(content)
    db.save_chapter_version(novel_id, chapter_num, content, "pre-humanize")
    db.update_chapter(novel_id, chapter_num, content=humanized, word_count=len(humanized))
    db.log(novel_id, "chapter.humanized", {"chapter": chapter_num})


def _run_revise_chapter(novel_id: str, chapter_num: int, critique: str):
    """Background: revise a chapter based on natural language critique."""
    try:
        _set_status(novel_id, "revising", f"正在根据批评重写第{chapter_num}章…")
        from ..config import Config
        from ..generator import Generator
        provider = _get_provider(novel_id)
        cfg = Config(openai_api_key=provider.get("api_key",""), openai_base_url=provider.get("base_url",""),
                     model=provider.get("models","deepseek-v4-pro")[0] if provider.get("models") else "gpt-4o")
        gen = Generator(cfg)
        state = _load_state(novel_id)
        ch = db.get_chapter(novel_id, chapter_num)
        if not ch or not state: raise Exception("Chapter or state not found")
        style = None
        try:
            from ..generator import StyleProfile
            sd = db.get_style_profile(novel_id)
            if sd: style = StyleProfile(**{k:v for k,v in sd.items() if k in StyleProfile.__dataclass_fields__})
        except: pass

        revised = gen.revise_chapter(ch.get("content",""), critique, state, style)
        # Save as new version
        db.save_chapter_version(novel_id, chapter_num, ch.get("content",""), "pre-critique-revision")
        db.update_chapter(novel_id, chapter_num, content=revised, word_count=len(revised))
        db.log(novel_id, "chapter.revised_by_critique", {"chapter": chapter_num, "critique": critique[:100]})
        _set_status(novel_id, "complete", f"第{chapter_num}章已按批评重写")
    except Exception as e:
        _set_status(novel_id, "error", str(e)[:200])


def _run_autonomous(novel_id: str, target_chapters: int = 30):
    """全自动成书：A/B→生成→管线→书名→报告→导出"""
    from dataclasses import asdict

    from ..config import Config
    from ..generator import GENRE_TO_STYLE, STYLE_POOL, Generator
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
        style = STYLE_POOL.get(style_key)
        if style:
            style.novel_id = novel_id
            style.writer_voice = best_voice
            db.save_style_profile(novel_id, asdict(style))

        # Phase 1: Generate all chapters
        _set_status(novel_id, "generating", f"生成{target_chapters}章...")
        state = _load_state(novel_id)
        if state:
            # Add outline
            for i in range(1, target_chapters + 1):
                with db.conn() as c:
                    existing = c.execute("SELECT id FROM chapters WHERE novel_id=? AND number=?",(novel_id,i)).fetchone()
                    if not existing:
                        c.execute("INSERT INTO chapters (novel_id,number,title,summary,word_count) VALUES (?,?,?,'',0)",(novel_id,i,f"第{i}章"))
            gen.generate_chapters(state, n=target_chapters, style=style)

        # Phase 2: Revise opening
        _set_status(novel_id, "revising", "基于结局回修前3章...")
        state2 = _load_state(novel_id)
        if state2 and state2.total_chapters >= 5:
            revised = gen.revise_opening(state2, target_chapters=3, style=style)
            for ch in revised:
                db.update_chapter(novel_id, ch.number, content=ch.content, word_count=ch.word_count)

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
                        new_ch = gen.generate_chapter_classic(state3, style=style)
                        if new_ch:
                            db.update_chapter(novel_id, ch_num, content=new_ch.content, word_count=len(new_ch.content))

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


def _run_evolve(novel_id: str):
    """进化模式：迭代推倒→重来，直到经典潜质达标。max 3次，有成本追踪和死胡同检测。"""
    import random as _rd
    import time as _t

    from ..config import Config
    from ..generator import GENRE_TO_STYLE, STYLE_POOL, WRITER_VOICES, Generator
    provider = _get_provider(novel_id)
    cfg = Config(openai_api_key=provider.get("api_key",""), openai_base_url=provider.get("base_url",""),
                 model=provider.get("models","deepseek-v4-pro")[0] if provider.get("models") else "gpt-4o")
    gen = Generator(cfg)
    novel = db.get_novel(novel_id)
    max_iter = 3
    timeout_per_iter = 600  # 10 min per iteration
    voices = list(WRITER_VOICES.keys())
    _rd.shuffle(voices)  # random order, try each once
    best_avg = 0
    best_iter = 0
    tried_voices: list[str] = []

    for iteration in range(1, max_iter + 1):
        t0 = _t.time()
        _set_status(novel_id, "evolving", f"第{iteration}/{max_iter}次迭代（最多{max_iter}次，约¥0.10/次）...")

        # Pick untried voice
        available = [v for v in voices if v not in tried_voices]
        if not available: available = voices
        voice = _rd.choice(available)
        tried_voices.append(voice)

        # Delete old chapters
        with db.conn() as c:
            c.execute("DELETE FROM chapters WHERE novel_id=? AND word_count>0", (novel_id,))

        # Set voice
        from dataclasses import asdict
        style_key = GENRE_TO_STYLE.get(novel.get("genre","玄幻"), "玄幻")
        style = STYLE_POOL.get(style_key)
        if style:
            style.novel_id = novel_id; style.writer_voice = voice
            db.save_style_profile(novel_id, asdict(style))

        # Regenerate 5 chapters (with timeout guard)
        state = _load_state(novel_id)
        if state:
            for i in range(1, 6):
                with db.conn() as c:
                    if not c.execute("SELECT id FROM chapters WHERE novel_id=? AND number=?",(novel_id,i)).fetchone():
                        c.execute("INSERT INTO chapters (novel_id,number,title,summary,word_count) VALUES (?,?,?,'',0)",(novel_id,i,f"第{i}章"))
            gen.generate_chapters(state, n=5, style=style)

        elapsed = _t.time() - t0
        if elapsed > timeout_per_iter:
            db.log(novel_id, "evolve.timeout", {"iteration": iteration, "elapsed": int(elapsed)})
            _set_status(novel_id, "evolving", f"第{iteration}次超时({elapsed:.0f}s)——跳过")
            continue

        # Assess
        novel2 = db.get_novel(novel_id)
        gen_chs = [c for c in novel2.get("chapters",[]) if c.get("word_count",0) > 0]
        if len(gen_chs) >= 5:
            first5 = gen_chs[:5]
            avg_q = sum(c.get("quality_score",0) for c in first5) / 5
            db.log(novel_id, "evolve.iteration", {"iteration": iteration, "voice": voice, "avg_q": avg_q, "cost_est": "~$0.10"})

            if avg_q > best_avg:
                best_avg = avg_q; best_iter = iteration

            if avg_q >= 0.78:
                _set_status(novel_id, "complete", f"第{iteration}次迭代达标！声音={voice} 均分={avg_q:.2f} 花费~$0.{iteration}0")
                return

            # Dead-end detection: if 2 iterations and quality decreased, stop
            if iteration >= 2 and avg_q < best_avg - 0.05:
                db.log(novel_id, "evolve.dead_end", {"iteration": iteration, "avg_q": avg_q, "best": best_avg})
                _set_status(novel_id, "complete", f"质量下降({avg_q:.2f}<{best_avg:.2f})——提前终止，保留第{best_iter}次版本")
                return

        _set_status(novel_id, "evolving", f"第{iteration}次未达标({avg_q:.2f})，换声音...")

    _set_status(novel_id, "complete", f"完成{max_iter}次迭代，最优=第{best_iter}次(均分{best_avg:.2f})，总花费~$0.{max_iter*10}")


def _run_world_bible(novel_id: str):
    """Background: generate complete world bible from synopsis."""
    from ..config import Config
    from ..generator import Generator
    provider = _get_provider(novel_id)
    cfg = Config(openai_api_key=provider.get("api_key",""), openai_base_url=provider.get("base_url",""),
                 model=provider.get("models","deepseek-v4-pro")[0] if provider.get("models") else "gpt-4o")
    gen = Generator(cfg)
    novel = db.get_novel(novel_id)
    try:
        _set_status(novel_id, "generating", "生成世界观设定...")
        bible = gen._call_llm_with_retry([
            {"role":"system","content":"你是世界观设计师。基于小说简介生成完整的设定集。"},
            {"role":"user","content": f"""基于以下简介，生成完整世界观设定（JSON格式）：

简介：{novel.get('synopsis','')}
体裁：{novel.get('genre','玄幻')}

输出JSON：
{{
  "world_name": "世界名称",
  "era": "时代背景",
  "power_system": "核心力量体系（100字内）",
  "geography": "地理格局（100字内）",
  "factions": [{{"name":"势力名","description":"简介","leader":"首领"}}],
  "key_locations": [{{"name":"地名","description":"描述"}}],
  "historical_events": [{{"event":"事件名","year":"时间","impact":"影响"}}],
  "cultural_notes": "文化/社会特色（200字内）"
}}

只输出JSON。"""}
        ], max_tokens=2048)

        import json as _json
        import re
        json_match = re.search(r'\{[\s\S]*\}', bible)
        if json_match:
            data = _json.loads(json_match.group(0))
            # Save to novel
            updates = {}
            for k in ['world_name','era','power_system']:
                if k in data: updates[k] = data[k]
            if 'geography' in data: updates['world_geo'] = data.get('geography','')
            if updates:
                db.update_novel(novel_id, **updates)
            # Save factions
            for f in data.get('factions',[])[:5]:
                with db.conn() as c:
                    c.execute("INSERT OR IGNORE INTO factions (novel_id,name,description,leader) VALUES (?,?,?,?)",
                             (novel_id, f.get('name',''), f.get('description','')[:200], f.get('leader','')))
            # Save as world bible JSON
            from pathlib import Path
            (Path("data")/"bibles").mkdir(exist_ok=True)
            (Path("data")/"bibles"/f"{novel_id}.json").write_text(_json.dumps(data, ensure_ascii=False, indent=2))
            db.log(novel_id, "world.bible_generated", {"factions": len(data.get('factions',[]))})
        _set_status(novel_id, "complete", "世界设定集已生成")
    except Exception as e:
        _set_status(novel_id, "error", str(e)[:200])


def _run_final_polish(novel_id: str):
    """出版前终极打磨——全本一致性+首尾呼应+重复短语清理。"""
    from ..config import Config
    from ..generator import Generator
    provider = _get_provider(novel_id)
    cfg = Config(openai_api_key=provider.get("api_key",""), openai_base_url=provider.get("base_url",""),
                 model=provider.get("models","deepseek-v4-pro")[0] if provider.get("models") else "gpt-4o")
    gen = Generator(cfg)
    novel = db.get_novel(novel_id)
    gen_chs = [c for c in novel.get("chapters",[]) if c.get("word_count",0) > 0]
    if not gen_chs: return

    total = len(gen_chs)
    _set_status(novel_id, "polishing", f"终极打磨 {total}章…")

    # Phase 1: Check first-last chapter echo
    first_ch = gen_chs[0]
    last_ch = gen_chs[-1]
    _set_status(novel_id, "polishing", "检查首尾呼应…")
    echo_check = gen._call_llm_with_retry([
        {"role":"system","content":"分析第一章和最后一章是否形成呼应。"},
        {"role":"user","content": f"第一章：{first_ch.get('content','')[:500]}\n最后一章：{last_ch.get('content','')[:500]}\n是否有画面、对话或主题的呼应？有的话描述，没有的话建议3处可以加入的呼应。"}
    ], max_tokens=512)
    db.log(novel_id, "final_polish.echo", {"result": echo_check[:200]})

    # Phase 2: Find and flag repetitive phrases across the book
    _set_status(novel_id, "polishing", "扫描全本重复短语…")
    all_text = " ".join(c.get("content","") for c in gen_chs)
    import collections
    import re
    phrases = re.findall(r'[一-鿿]{2,4}', all_text[:50000])
    freq = collections.Counter(phrases)
    overused = [(p, c) for p, c in freq.most_common(20) if c > len(gen_chs) * 3]
    if overused:
        db.log(novel_id, "final_polish.repetition", {"phrases": str(overused[:5])})

    _set_status(novel_id, "complete", f"终极打磨完成({total}章)")


def _run_polish(novel_id: str):
    """Background: polish all chapters — fix micro-issues."""
    from ..config import Config
    from ..generator import Generator
    provider = _get_provider(novel_id)
    cfg = Config(openai_api_key=provider.get("api_key",""), openai_base_url=provider.get("base_url",""),
                 model=provider.get("models","deepseek-v4-pro")[0] if provider.get("models") else "gpt-4o")
    gen = Generator(cfg)
    novel = db.get_novel(novel_id)
    gen_chs = [c for c in novel.get("chapters",[]) if c.get("word_count",0) > 0]
    if not gen_chs:
        _set_status(novel_id, "error", "No chapters to polish")
        return
    # Check length consistency
    lengths = [c.get("word_count",0) for c in gen_chs]
    avg_len = sum(lengths)/len(lengths)
    outliers = [(c["number"], c["word_count"]) for c in gen_chs if abs(c["word_count"]-avg_len) > avg_len*0.5]
    if outliers:
        print(f"[POLISH] ⚠️ Length outliers: {outliers}")
        db.log(novel_id, "polish.outliers", {"chapters": [str(o) for o in outliers]})

    total = len(gen_chs)
    for i, ch in enumerate(gen_chs):
        _set_status(novel_id, "polishing", f"精修第{ch['number']}章 ({i+1}/{total})...")
        content = ch.get("content","")
        if not content: continue
        polish_prompt = """精修以下章节——只做微调，不改剧情：

1. 修正角色称呼不一致（如果同一角色在本章内被叫了不同名字，统一）
2. 平滑场景切换处的过渡（如果两段之间跳得太快，加半句过渡）
3. 删除本章内重复出现的形容词/比喻（同一意象出现≥2次，只保留最好的那一次）
4. 检查章节标题和正文内容是否匹配——如果标题暗示的内容没出现，则调整标题

输出修改后的完整章节正文。保持字数±5%。"""

        polished = gen._call_llm_with_retry([
            {"role":"system","content":"你是专业校对编辑。只做微调，不改剧情。"},
            {"role":"user","content": f"{polish_prompt}\n\n原稿：\n{content}"}
        ], max_tokens=8192)
        if polished and len(polished) > len(content)*0.7:
            db.update_chapter(novel_id, ch["number"], content=polished, word_count=len(polished))
    _set_status(novel_id, "complete", f"全本精修完成({total}章)")


def _run_ab_test(synopsis: str, genre: str, voices: list[str] | None = None):
    """Background: run A/B test across multiple writer voices."""
    from ..config import Config
    from ..generator import Generator
    provider = _get_provider(None)
    cfg = Config(openai_api_key=provider.get("api_key",""), openai_base_url=provider.get("base_url",""),
                 model=provider.get("models","deepseek-v4-pro")[0] if provider.get("models") else "gpt-4o")
    gen = Generator(cfg)
    result = gen.ab_test_opening(synopsis, genre, voices)
    # Save results to a log file
    import json as _json
    from pathlib import Path
    log_dir = Path("data") / "ab_tests"
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / f"ab_{int(__import__('time').time())}.json"
    log_file.write_text(_json.dumps(result, ensure_ascii=False, indent=2))
    best = result.get("best_voice", "?")
    best_q = result.get("best_chapter", {}).get("quality", 0)
    db.log("ab_test", "ab.completed", {"best": best, "quality": best_q})
    print(f"[AB] Best voice: {best} (Q={best_q}) -> saved to {log_file}")


def _run_pipeline(novel_id: str):
    """自主出版管线：生成→回修→弱章重写→质量报告"""
    from ..config import Config
    from ..generator import Generator, StyleProfile
    provider = _get_provider(novel_id)
    cfg = Config(openai_api_key=provider.get("api_key",""), openai_base_url=provider.get("base_url",""),
                 model=provider.get("models","deepseek-v4-pro")[0] if provider.get("models") else "gpt-4o")
    gen = Generator(cfg)
    style = None
    try:
        sd = db.get_style_profile(novel_id)
        if sd: style = StyleProfile(**{k:v for k,v in sd.items() if k in StyleProfile.__dataclass_fields__})
    except: pass

    try:
        # Phase 1: Generate all remaining chapters
        _set_status(novel_id, "generating", "Phase 1/3: 生成全部章节…")
        state = _load_state(novel_id)
        if not state: return
        outline_items = [{"number": c["number"], "title": c["title"], "summary": c["summary"]}
                         for c in db.get_novel(novel_id).get("chapters",[]) if c.get("word_count", 0) == 0]
        remaining = len(outline_items) or 10
        gen.generate_chapters(state, n=min(remaining, 10), style=style)
        db.log(novel_id, "pipeline.phase1", {"chapters": state.total_chapters})

        # Phase 2: Revise opening
        _set_status(novel_id, "revising", "Phase 2/3: 基于结局回修前3章…")
        if state.total_chapters >= 5:
            revised = gen.revise_opening(state, target_chapters=3, style=style)
            for ch in revised:
                db.update_chapter(novel_id, ch.number, content=ch.content, word_count=ch.word_count)
            db.log(novel_id, "pipeline.phase2", {"revised": len(revised)})

        # Phase 3: Identify & regenerate weak chapters
        _set_status(novel_id, "generating", "Phase 3/3: 经典模式重写弱章…")
        novel = db.get_novel(novel_id)
        gen_chs = [c for c in novel.get("chapters",[]) if c.get("word_count",0) > 0]
        if gen_chs:
            scores = [(c["number"], c.get("quality_score",0)) for c in gen_chs]
            scores.sort(key=lambda x: x[1])
            bottom_20 = [n for n, q in scores[:max(1, len(scores)//5)] if q < 0.75]
            for ch_num in bottom_20:
                _set_status(novel_id, "generating", f"经典重写第{ch_num}章…")
                state2 = _load_state(novel_id)
                if state2:
                    new_ch = gen.generate_chapter_classic(state2, style=style)
                    if new_ch:
                        db.update_chapter(novel_id, ch_num, content=new_ch.content,
                                        word_count=len(new_ch.content))
                        if style:
                            style.regeneration_log.append({"chapter": ch_num, "reason": "pipeline_weak"})
                        db.log(novel_id, "pipeline.phase3", {"regenerated": ch_num})

        _set_status(novel_id, "complete", "管线完成！")
    except Exception as e:
        _set_status(novel_id, "error", str(e)[:200])


def _run_generation_classic(novel_id: str):
    """经典模式：使用 generate_chapter_classic，多版本淘汰制。"""
    try:
        _set_status(novel_id, "generating", "经典模式：正在多版本筛选…（约需3-5分钟）", 10)
        from ..config import Config
        from ..generator import Generator
        provider = _get_provider(novel_id)
        cfg = Config(openai_api_key=provider.get("api_key",""), openai_base_url=provider.get("base_url",""),
                     model=provider.get("models","deepseek-v4-pro")[0] if provider.get("models") else "gpt-4o")
        gen = Generator(cfg)
        state = _load_state(novel_id)
        if not state: return
        outline = [{"number": c["number"], "title": c["title"], "summary": c["summary"]}
                   for c in db.get_novel(novel_id).get("chapters",[]) if c.get("word_count", 0) == 0]
        rag_context = gen.retrieve_relevant_context(query=state.plot.current_arc or state.plot.premise, novel_id=novel_id, top_k=5)
        style = None
        try:
            from ..generator import StyleProfile
            sd = db.get_style_profile(novel_id)
            if sd: style = StyleProfile(**{k:v for k,v in sd.items() if k in StyleProfile.__dataclass_fields__})
        except: pass

        _set_status(novel_id, "generating", "经典模式：生成+淘汰中…", 20)
        chapter = gen.generate_chapter_classic(state, style=style, rag_context=rag_context, outline=outline)
        body = chapter.content or chapter.summary
        cleaned, de_ai_changes = gen.de_ai(body)
        quality = gen.judge_quality(cleaned, state, style)

        cid = db.add_chapter(novel_id=novel_id, number=chapter.number, title=chapter.title,
            word_count=len(cleaned), summary=chapter.summary, content=cleaned,
            ending_hook=chapter.ending_hook, key_events=json.dumps(chapter.key_events),
            revelations=json.dumps(chapter.revelations), quality_score=quality['overall'], model_used=cfg.model)
        _set_status(novel_id, "complete", f"第{chapter.number}章完成 — 经典模式 — Q:{quality.get('grade','?')}({quality.get('overall',0):.2f})", 100)
    except Exception as e:
        _set_status(novel_id, "error", f"经典模式失败: {str(e)[:200]}", 0)


def _run_batch_generation(novel_id: str, count: int):
    """V5: Batch generate n chapters sequentially. Supports:
    - Queue progress tracking via _job_queue
    - Smart context window: auto-summarize old chapters when novel exceeds 30 chapters
    - Cost tracking via cost_logs + chapters table
    """
    try:
        from ..config import Config
        from ..generator import Generator
        provider = _get_provider(novel_id)
        cfg = Config(
            openai_api_key=provider.get("api_key", ""),
            openai_base_url=provider.get("base_url", ""),
            model=provider.get("models", ["deepseek-v4-pro"])[0] if provider.get("models") else "deepseek-v4-pro",
        )
        gen = Generator(cfg)
        state = _load_state(novel_id)
        if not state:
            return

        q_threshold = float(_gen_directions.pop(novel_id + "_qthreshold", "0.8"))
        outline = []
        try:
            with db.conn() as conn:
                rows = conn.execute(
                    "SELECT number, title, summary FROM chapters WHERE novel_id=? AND word_count=0 ORDER BY number LIMIT 10",
                    (novel_id,)
                ).fetchall()
                outline = [{"number": r["number"], "title": r["title"], "summary": r["summary"]} for r in rows]
        except Exception:
            pass

        # Load style
        style = None
        try:
            from ..generator import StyleProfile
            style_data = db.get_style_profile(novel_id)
            if style_data:
                style = StyleProfile(**style_data)
        except Exception:
            pass

        # Smart context window: generate chapter summaries for novels with 30+ chapters
        _ensure_smart_context(novel_id, gen, state)

        # RAG context (reuse across batch)
        rag_context: Any = gen.retrieve_relevant_context(
            query=state.plot.current_arc or state.plot.premise,
            novel_id=novel_id, top_k=5,
        )

        # Inject chapter summaries into RAG context if available
        existing_summaries = db.get_chapter_summaries(novel_id)
        if existing_summaries:
            summary_text = "【前情摘要】\n" + "\n".join(
                f"第{s['chapter_num']}章: {s['summary_text']}" for s in existing_summaries
            )
            if rag_context:
                rag_context = summary_text + "\n\n" + str(rag_context)
            else:
                rag_context = summary_text

        for i, outline_item in enumerate(outline[:count]):
            target_num = outline_item["number"]
            progress_pct = ((i + 1) * 100) // count
            _set_status(novel_id, "generating", f"正在生成第{target_num}章...", progress_pct)

            # Update queue job progress
            _update_job_progress(novel_id, i, count)

            chapter, quality = gen.batch_generate(state, n=2, rag_context=rag_context,
                                                   outline=outline, style=style)
            body = chapter.content or chapter.summary

            retries = 0
            max_retries = 3 if q_threshold >= 0.8 else 2
            while quality['overall'] < q_threshold and retries < max_retries:
                retries += 1
                chapter, quality = gen.batch_generate(state, n=1, rag_context=rag_context,
                                                       outline=outline, style=style)
                body = chapter.content or chapter.summary
                quality = gen.score_quality(body, state, style=style)

            # Guard: if body is still empty after all retries, skip this chapter
            if not body:
                print(f"[BATCH ERROR] {novel_id} ch{target_num}: generate returned empty content (tried {retries+1} times), skipping slot {target_num}")
                db.log(novel_id, "chapter.empty_skipped", {"target_num": target_num, "retries": retries})
                _set_status(novel_id, "error", f"第{target_num}章生成失败（内容为空），已跳过", 0)
                _update_job_progress(novel_id, i + 1, count, f"第{target_num}章生成失败（内容为空）")
                continue

            # Self-edit pass
            body = gen._self_edit(body, state, style)

            cleaned_body, de_ai_changes = gen.de_ai(body)
            if de_ai_changes > 0:
                print(f"[BATCH] {novel_id} de-AI: {de_ai_changes} changes")

            # LLM Judge — final evaluation
            final_quality = gen.judge_quality(cleaned_body or body, state, style)
            if final_quality.get("method") == "llm":
                detail = final_quality.get("judge_detail", {})
                print(f"[BATCH] {novel_id} ch{chapter.number} judge: {final_quality['grade']}({final_quality['overall']}) — {detail.get('biggest_issue', '')}")

            # Cost tracking is handled internally by Generator._save_cost_log

            # CRITICAL: use outline slot number (target_num), NOT chapter.number.
            # Pass cost info from generator if available
            usage = getattr(gen, '_last_usage', None) or {}
            cid = db.add_chapter(
                novel_id=novel_id, number=target_num, title=chapter.title,
                word_count=len(cleaned_body), summary=chapter.summary,
                content=cleaned_body, ending_hook=chapter.ending_hook,
                key_events=json.dumps(chapter.key_events),
                revelations=json.dumps(chapter.revelations),
                quality_score=final_quality['overall'], model_used=cfg.model,
                prompt_tokens=usage.get("prompt_tokens", 0),
                completion_tokens=usage.get("completion_tokens", 0),
                cost=round(usage.get("cost", 0), 6),
            )
            # Append to state so next chapter sees full text
            chapter.content = cleaned_body
            chapter.word_count = len(cleaned_body)
            chapter.number = target_num  # fix number to match the filled slot
            state.chapters.append(chapter)

            # Extract character voices from this chapter
            try:
                gen._extract_character_voices(cleaned_body, state)
            except Exception:
                pass

            # Foreshadowing audit every 10 chapters
            if state.total_chapters % 10 == 0:
                try:
                    audit = gen.audit_foreshadowing(state)
                    if audit.get("warning"):
                        print(f"[BATCH] ⚠️  {novel_id}: {audit['warning']}")
                except Exception:
                    pass

            db.log(novel_id, "chapter.generated", {
                "chapter": target_num, "words": len(cleaned_body),
                "quality": quality['overall'], "grade": quality['grade'],
                "de_ai_changes": de_ai_changes, "batch": i + 1,
            })
            print(f"[BATCH] {novel_id} ch{target_num}/{state.total_chapters} — {len(cleaned_body)}w — Q:{quality['grade']}({quality['overall']})")

            # After generating a chapter beyond 30, generate its summary for future context
            if target_num > 30 and len(cleaned_body) > 100:
                try:
                    _generate_single_chapter_summary(novel_id, gen, target_num, cleaned_body[:1000])
                except Exception as e:
                    print(f"[BATCH] summary gen failed for ch{target_num}: {e}")

        _set_status(novel_id, "complete", f"批量生成完成：{count}章", 100)
        _update_job_progress(novel_id, count, count)

    except Exception as e:
        err_msg = str(e)[:200]
        _set_status(novel_id, "error", f"批量生成失败: {err_msg}", 0)
        _update_job_progress(novel_id, 0, 0, err_msg)
        db.log(novel_id, "error.critical", {"error": err_msg})
        print(f"[BATCH ERROR] {novel_id}: {err_msg}", file=sys.stderr)


def _update_job_progress(novel_id: str, current: int, total: int, error: str = ""):
    """Update the queue job progress for a novel."""
    with _job_lock:
        for job in _job_queue.values():
            if job["novel_id"] == novel_id and job["status"] in ("queued", "running"):
                job["progress"]["current"] = current
                job["progress"]["total"] = total
                if error:
                    job["last_error"] = error
                break


def _ensure_smart_context(novel_id: str, gen, state):
    """Smart context window: for novels with 30+ total chapters, summarize older
    chapters so context fits within LLM limits. Generates summaries on-demand and
    stores them in chapter_summaries table for reuse.

    The --skip-summaries flag can be passed via environment variable for testing.
    """
    import os
    if os.environ.get("SKIP_SUMMARIES"):
        return

    total = state.total_chapters
    if total < 30:
        return

    # Summarize chapters 1..max(5, total-25) if summaries don't exist
    summarize_up_to = max(5, total - 25)
    if db.has_chapter_summaries(novel_id, summarize_up_to):
        return  # Already have summaries

    print(f"[CONTEXT] Smart context: summarizing chapters 1..{summarize_up_to} for {novel_id}")

    # Get chapters that need summaries
    for ch_num in range(1, summarize_up_to + 1):
        # Skip if summary already exists
        existing = db.get_chapter_summaries(novel_id, [ch_num])
        if existing:
            continue

        ch = db.get_chapter(novel_id, ch_num)
        if not ch or not ch.get("content"):
            continue

        content = ch["content"][:1000]
        summary = _generate_summary_with_llm(gen, novel_id, ch_num, content)
        if summary:
            db.save_chapter_summary(novel_id, ch_num, summary)
            print(f"[CONTEXT] Summarized ch{ch_num}: {summary[:60]}...")

    print(f"[CONTEXT] Smart context summaries complete for {novel_id}")


def _generate_single_chapter_summary(novel_id: str, gen, chapter_num: int, content: str):
    """Generate a summary for a single chapter and store it."""
    summary = _generate_summary_with_llm(gen, novel_id, chapter_num, content)
    if summary:
        db.save_chapter_summary(novel_id, chapter_num, summary)


def _generate_summary_with_llm(gen, novel_id: str, chapter_num: int, content: str) -> str:
    """Generate a one-sentence summary for a chapter using the LLM."""
    try:
        result = gen._call_llm_with_retry([
            {"role": "system", "content": "你是一位小说编辑。用一句话概括以下章节的核心事件和人物变化（不超过50字）。"},
            {"role": "user", "content": content[:1000]}
        ], max_tokens=128)
        summary = result.strip()
        # Track cost of summary generation
        usage = getattr(gen, '_last_usage', None)
        if usage:
            _record_chapter_cost(novel_id, chapter_num, usage.get("model", ""),
                usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0),
                usage.get("total_tokens", 0), usage.get("cost", 0), purpose="summarize")
        return summary
    except Exception as e:
        print(f"[CONTEXT] Failed to summarize ch{chapter_num}: {e}")
        return ""


def _record_chapter_cost(novel_id: str, chapter_number: int, model: str,
                          prompt_tokens: int, completion_tokens: int,
                          total_tokens: int, cost: float, purpose: str = "generate"):
    """Record API cost for a chapter generation or summary call."""
    try:
        db.log_cost(novel_id, chapter_number, model,
                    prompt_tokens, completion_tokens, total_tokens, cost, purpose)
    except Exception:
        pass  # Cost logging is non-critical


def _load_state(novel_id: str):
    """Temporary: load state from DB for generator compatibility"""
    from ..story_state import ChapterMeta, Character, Plot, StoryState, World
    novel = db.get_novel(novel_id)
    if not novel:
        return None
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
                   arc_chapter_start=novel.get("arc_chapter_start",1)),
        chapters=[ChapterMeta(number=ch["number"], title=ch["title"],
                     word_count=ch["word_count"], summary=ch.get("summary",""),
                     ending_hook=ch.get("ending_hook",""),
                     key_events=json.loads(ch.get("key_events","[]")) if isinstance(ch.get("key_events"), str) else [],
                     revelations=json.loads(ch.get("revelations","[]")) if isinstance(ch.get("revelations"), str) else [],
                     generated_at=ch.get("generated_at",""))
                     for ch in novel.get("chapters", []) if ch.get("word_count", 0) > 0],
    )


# ═══════════════ Consistency Scoring & Batch (Long-Run) ═══════════════

def _run_single_generation(novel_id: str, compression: str, quality_threshold: float) -> dict:
    """Wrapper for single chapter generation used by BatchRunner."""
    _gen_directions[novel_id + "_compression"] = compression
    _gen_directions[novel_id + "_qthreshold"] = str(quality_threshold)
    _run_generation(novel_id)
    # Return captured quality info
    status = _gen_status.get(novel_id, {})
    return {
        "quality": {
            "overall": status.get("overall", 0),
            "grade": status.get("grade", "?"),
        },
        "word_count": status.get("word_count", 0),
        "retries": status.get("retries", 0),
        "auto_recovery": status.get("auto_recovery", False),
    }


def _run_longrun_batch_generation(novel_id: str, chapters: int, compression: str, quality_threshold: float):
    """Background task: run batch generation with metrics tracking."""
    from ..stations.novel.batch_runner import BatchRunner
    try:
        runner = BatchRunner(db, _get_provider, _run_single_generation)
        report = runner.run(novel_id, chapters, compression, quality_threshold)
        _gen_status[novel_id] = {
            "status": "batch_complete",
            "message": f"批量生成完成: {report['chapters_generated']}/{chapters}章",
            "progress": 100,
            "batch_report": report,
        }
        print(runner.format_report(report))
    except Exception as e:
        import traceback
        _gen_status[novel_id] = {
            "status": "batch_failed",
            "message": f"批量生成失败: {str(e)[:100]}",
            "progress": 0,
        }
        traceback.print_exc()


@router.get("/api/novels/{novel_id}/consistency-score")
def get_consistency_score(novel_id: str) -> dict:
    """Get cross-chapter consistency score (5-dimension structural scoring)."""
    from ..stations.novel.consistency_scorer import ConsistencyScorer
    scorer = ConsistencyScorer()
    result = scorer.run({"novel_id": novel_id, "db": db})
    return result


@router.post("/api/novels/{novel_id}/batch-generate")
def trigger_batch_generate(novel_id: str, background: BackgroundTasks, data: dict = {}) -> dict:
    """Generate N chapters sequentially with fixed constraint level for long-run testing."""
    if not db.get_novel(novel_id):
        raise HTTPException(404)
    chapters = int((data or {}).get("chapters", 10))
    compression = (data or {}).get("compression", "L1").strip().upper()
    quality_threshold = float((data or {}).get("quality_threshold", 0.75))
    if compression not in ("L0", "L1", "L2", "L3", "NONE"):
        compression = "L1"
    if chapters < 1 or chapters > 20:
        raise HTTPException(400, "chapters must be 1-20")
    background.add_task(_run_longrun_batch_generation, novel_id, chapters, compression, quality_threshold)
    return {
        "status": "batch_started",
        "novel_id": novel_id,
        "chapters": chapters,
        "compression": compression,
    }


# ═══════════════ Publish ═══════════════

@router.post("/api/novels/{novel_id}/publish")
def trigger_publish(novel_id: str, data: dict = {}, background: BackgroundTasks = BackgroundTasks()):
    novel = db.get_novel(novel_id)
    if not novel:
        raise HTTPException(404)
    chapters = novel.get("chapters", [])
    if not chapters:
        raise HTTPException(400, "No chapters")
    ch_num = data.get("chapter_number") if isinstance(data, dict) else None
    if ch_num is None:
        ch_num = chapters[-1]["number"]
    background.add_task(_run_publish, novel_id, ch_num)
    return {"status": "publishing", "novel_id": novel_id, "chapter": ch_num}


@router.get("/api/novels/{novel_id}/publish-status")
def publish_status(novel_id: str) -> dict:
    """Return publish status for all chapters."""
    novel = db.get_novel(novel_id)
    if not novel:
        raise HTTPException(404)
    chapters = novel.get("chapters", [])
    published = set()
    with db.conn() as c:
        rows = c.execute("""
            SELECT p.chapter_id, p.success, c.number
            FROM publish_records p
            JOIN chapters c ON c.id = p.chapter_id
            WHERE c.novel_id = ? AND p.success = 1
        """, (novel_id,)).fetchall()
        published = {r["number"] for r in rows}
    return {
        "published": sorted(published),
        "pending": [c["number"] for c in chapters if c.get("word_count", 0) > 0 and c["number"] not in published],
    }


def _run_publish(novel_id: str, chapter_number: int):
    """Background task: publish chapter to platform"""
    try:
        import asyncio

        from ..publisher import Publisher
        pub = Publisher()
        result = asyncio.run(pub.publish(novel_id, chapter_number))
        if result.success:
            print(f"[PUB] {novel_id} ch{chapter_number} published to {result.platform}")
        else:
            print(f"[PUB FAIL] {novel_id} ch{chapter_number}: {result.error}")
    except Exception as e:
        db.log(novel_id, "publish.failed", {"chapter": chapter_number, "error": str(e)})
        print(f"[PUB ERROR] {novel_id}: {e}", file=sys.stderr)


# ═══════════════ Drafts (Mode B) ═══════════════

@router.post("/api/novels/{novel_id}/draft")
def draft_directions(novel_id: str, data: dict, background: BackgroundTasks) -> dict:
    if not db.get_novel(novel_id):
        raise HTTPException(404)
    author_input = data.get("input", "")
    if not author_input:
        raise HTTPException(400, "input required")
    background.add_task(_run_draft, novel_id, author_input)
    return {"status": "drafting", "novel_id": novel_id}


@router.post("/api/novels/{novel_id}/expand")
def expand_chapter(novel_id: str, data: dict, background: BackgroundTasks) -> dict:
    if not db.get_novel(novel_id):
        raise HTTPException(404)
    chosen_id = data.get("chosen_id", "")
    edits = data.get("edits", "")
    if not chosen_id:
        raise HTTPException(400, "chosen_id required")
    background.add_task(_run_expand, novel_id, chosen_id, data.get("direction",""), data.get("preview",""), data.get("hook",""), edits)
    return {"status": "expanding", "novel_id": novel_id}


# ═══════════════ Auto Mode ═══════════════

@router.post("/api/novels/{novel_id}/auto/start")
def auto_start(novel_id: str) -> dict:
    if not db.get_novel(novel_id):
        raise HTTPException(404)
    db.set_scheduler_state(novel_id, is_running=1)
    db.log(novel_id, "mode.switched", {"from": "creator", "to": "auto"})
    return {"status": "started"}


@router.post("/api/novels/{novel_id}/auto/stop")
def auto_stop(novel_id: str) -> dict:
    db.set_scheduler_state(novel_id, is_running=0)
    db.log(novel_id, "mode.switched", {"from": "auto", "to": "creator"})
    return {"status": "stopped"}


@router.post("/api/novels/{novel_id}/auto/once")
def auto_once(novel_id: str, background: BackgroundTasks) -> dict:
    if not db.get_novel(novel_id):
        raise HTTPException(404)
    background.add_task(_run_generation, novel_id)
    return {"status": "running"}


# ═══════════════ System ═══════════════

def revenue_estimate(novel_id: str):
    """收入预估：基于平台数据和体裁，估算潜在月收入。"""
    novel = db.get_novel(novel_id)
    if not novel: raise HTTPException(404)
    gen_chs = [c for c in novel.get("chapters",[]) if c.get("word_count",0) > 0]
    words = novel.get("total_words", 0)
    chapters = len(gen_chs)
    genre = novel.get("genre", "玄幻")
    # Platform data (approximate, based on public reports)
    rpm = {"玄幻": 2.5, "都市": 3.0, "悬疑": 3.5, "科幻": 2.8, "系统流": 2.2,
           "女频": 3.2, "历史": 2.0, "游戏": 3.0, "官场": 1.8}.get(genre, 2.5)
    # Milestone status
    milestones = []
    for ms in [(20,"签约资格"), (50,"推荐位"), (100,"全勤奖"), (200,"精品频道"), (500,"大神约")]:
        if chapters < ms[0]:
            milestones.append({"need": ms[0] - chapters, "chapters_total": ms[0], "reward": ms[1]})
    # Revenue projection
    daily_readers_low = max(100, words // 500)
    daily_readers_high = daily_readers_low * 5
    monthly_low = round(daily_readers_low * rpm / 1000 * 30, 0)
    monthly_high = round(daily_readers_high * rpm / 1000 * 30, 0)
    return {
        "genre": genre, "rpm_per_1k_reads": rpm,
        "words": words, "chapters": chapters,
        "milestones": milestones,
        "revenue_projection": f"¥{monthly_low}~{monthly_high}/月（基于{words}字、体裁{genre}）",
        "tip": "达到50章后平台推荐位可提升5-10倍曝光",
        "publish_cadence": "建议每日发布2章，保持稳定更新节奏以获得全勤奖励",
    }


@router.get("/api/novels/{novel_id}/freshness-check")
def freshness_check(novel_id: str) -> dict:
    """新鲜度检测：这个故事的设定、人物、冲突是否太像已有的爆款？"""
    novel = db.get_novel(novel_id)
    if not novel: raise HTTPException(404)
    synopsis = novel.get("synopsis","")
    genre = novel.get("genre","")
    gen_chs = [c for c in novel.get("chapters",[]) if c.get("word_count",0) > 0]

    from ..config import Config
    from ..generator import Generator
    provider = _get_provider(novel_id)
    cfg = Config(openai_api_key=provider.get("api_key",""), openai_base_url=provider.get("base_url",""),
                 model=provider.get("models","deepseek-v4-pro")[0] if provider.get("models") else "gpt-4o")
    gen = Generator(cfg)

    check = gen._call_llm_with_retry([
        {"role":"system","content":"你是网文市场分析师。判断这个故事的设定和核心冲突是否太像已知爆款。给出1-10的新鲜度评分。"},
        {"role":"user","content": f"体裁：{genre}\n简介：{synopsis}\n已有章节标题：{'、'.join(c['title'] for c in gen_chs[:5])}\n\n分析：这个设定和哪些已知爆款相似？相似度多高？有什么可以调整让它更独特？"}
    ], max_tokens=512)

    return {
        "synopsis": synopsis,
        "analysis": check,
        "tip": "如果新鲜度<6，建议调整核心设定——换一个不同类型的'金手指'或改变主角的起点，可以大幅提升新鲜感"
    }


@router.get("/api/novels/{novel_id}/acquisition-review")
def acquisition_review(novel_id: str) -> dict:
    """模拟出版社编辑的买断评估——这本书值不值得签。"""
    novel = db.get_novel(novel_id)
    if not novel: raise HTTPException(404)
    gen_chs = [c for c in novel.get("chapters",[]) if c.get("word_count",0) > 0]
    if len(gen_chs) < 10: return {"error": "至少需要10章才能做买断评估"}

    scores = [c.get("quality_score",0) for c in gen_chs]
    avg_q = sum(scores)/len(scores)
    titles = [c.get("title","") for c in gen_chs]

    # Acquisition criteria
    criteria: dict[str, dict[str, Any]] = {
        "结构完整度": {"score": min(10, len(gen_chs)//5 + 5), "max": 10,
                      "note": f"{len(gen_chs)}章——{'结构完整，弧线清晰' if len(gen_chs)>=20 else '章节偏少，故事弧线尚不完整'}"},
        "语言成熟度": {"score": min(10, int(avg_q * 12)), "max": 10,
                      "note": f"均分{avg_q:.2f}——{'文笔成熟，接近出版级别' if avg_q>=0.8 else '文笔达标，可出版但需要编辑加工' if avg_q>=0.7 else '需要大幅修改'}"},
        "人物塑造": {"score": min(10, len(novel.get("characters",[]))*2 + 3), "max": 10,
                    "note": f"{len(novel.get('characters',[]))}个角色——{'角色群像丰满' if len(novel.get('characters',[]))>=3 else '建议增加配角深度'}"},
        "商业潜力": {"score": min(10, 5 + int(novel.get("total_words",0)/10000)),
                    "max": 10, "note": f"{novel.get('total_words',0)}字——{'已达到商业出版字数' if novel.get('total_words',0)>=50000 else '建议扩充'}，体裁{novel.get('genre','')}"},
        "原创性": {"score": 7, "max": 10, "note": f"体裁{novel.get('genre','')}——需人工判断创新度"},
    }

    total = sum(int(c["score"]) for c in criteria.values())
    max_total = sum(int(c["max"]) for c in criteria.values())
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
        "verdict": verdict, "rating": f"{rating:.0%}", "offer_range": offer_range,
        "criteria": criteria,
        "acquisition_note": f"经过{len(gen_chs)}章的系统评估，该书{'已经达到出版水准' if rating>=0.7 else '还需要编辑打磨'}。{'建议提交出版社编辑部做最终审读。' if rating>=0.8 else '建议在提交前先解决上述问题。'}",
    }


@router.get("/api/novels/{novel_id}/cockpit")
def writers_cockpit(novel_id: str) -> dict:
    """作家驾驶舱：一页看全部——质量、收入、算法、留存、待办、风险。"""
    novel = db.get_novel(novel_id)
    if not novel: raise HTTPException(404)
    gen_chs = [c for c in novel.get("chapters",[]) if c.get("word_count",0) > 0]
    scores = [c.get("quality_score",0) for c in gen_chs]
    avg_q = sum(scores)/len(scores) if scores else 0

    # Alerts
    alerts = []
    if len(gen_chs) >= 5:
        last5 = scores[-5:]
        if sum(last5)/5 < avg_q - 0.1:
            alerts.append({"level":"warning","msg":f"最近5章质量下降(均{sum(last5)/5:.2f} vs 总均{avg_q:.2f})——建议检查并重写弱章"})
    if len(gen_chs) >= 3:
        hooks = [c.get("ending_hook","") for c in gen_chs[-5:]]
        weak = sum(1 for h in hooks if len(h) < 30) if hooks else 0
        if weak >= 3: alerts.append({"level":"critical","msg":f"最近5章{weak}章钩子偏弱——追读率会下降"})
    if novel.get("total_words",0) > 0 and len(gen_chs) > 0:
        avg_len = novel["total_words"] / len(gen_chs)
        if avg_len > 3500: alerts.append({"level":"info","msg":f"章节均长{avg_len:.0f}字——手机阅读建议控制在2500字以内"})

    # Milestones
    ms_list = []
    for chs, reward in [(20,"签约资格"),(50,"推荐位"),(100,"全勤奖"),(200,"精品频道")]:
        if len(gen_chs) < chs:
            ms_list.append({"need": chs - len(gen_chs), "total": chs, "reward": reward})

    # Next actions
    actions = []
    if len(gen_chs) < 3: actions.append("📝 生成至少3章以完成首秀数据采集")
    elif avg_q < 0.7: actions.append("⚠️ 经典模式重写弱章")
    elif len(gen_chs) < 20: actions.append("📖 继续生成至20章以申请签约")
    elif len(gen_chs) < 50: actions.append("🚀 继续生成至50章以获取推荐位")
    else: actions.append("✅ 书籍已进入稳定运营阶段")

    return {
        "novel": novel["title"], "genre": novel.get("genre","?"),
        "chapters": len(gen_chs), "words": novel.get("total_words",0),
        "avg_quality": round(avg_q,2),
        "alerts": alerts,
        "milestones": ms_list,
        "next_actions": actions,
        "retention": retention_score(novel_id) if len(gen_chs)>=3 else {},
        "revenue": revenue_estimate(novel_id),
        "publish_status": {"published": 0, "pending": len(gen_chs)},
    }


@router.get("/api/novels/{novel_id}/retention-score")
def retention_score(novel_id: str) -> dict:
    """留存预测：基于章节质量、钩子强度和更新节奏，估算读者留存率。"""
    novel = db.get_novel(novel_id)
    if not novel: raise HTTPException(404)
    gen_chs = [c for c in novel.get("chapters",[]) if c.get("word_count",0) > 0]
    if len(gen_chs) < 3: return {"error": "至少需要3章"}

    # Calculate retention signals
    scores = [c.get("quality_score",0) for c in gen_chs]
    hooks = [c.get("ending_hook","") for c in gen_chs]
    strong_hooks = sum(1 for h in hooks[-10:] if len(h) > 30 and any(k in h for k in ['？','！','……']))
    quality_trend = "up" if scores[-3:] and scores[-1] > scores[0] else "down" if scores[-1] < scores[0] else "flat"
    avg_q = sum(scores)/len(scores)

    # Drop-off risk chapters (quality < 0.65)
    weak = [(c["number"], c.get("quality_score",0)) for c in gen_chs if c.get("quality_score",0) < 0.65]

    return {
        "estimated_retention": f"{min(95, int(avg_q * 100))}%",
        "strong_hook_ratio": f"{strong_hooks}/{min(10,len(hooks[-10:]))}章",
        "quality_trend": quality_trend,
        "drop_off_risk_chapters": weak if weak else "无",
        "platform_revenue_impact": "高质量→高留存→算法给量→广告分成增加" if avg_q >= 0.75 else "质量不稳定→留存下降→算法降权→收入减少",
        "daily_readers_estimate": max(100, int(novel.get("total_words",0) / 500 * (avg_q / 0.8))),
    }


@router.get("/api/novels/{novel_id}/monetization-status")
def monetization_status(novel_id: str) -> dict:
    """付费转化看板：免费章→VIP章的漏斗状态。"""
    novel = db.get_novel(novel_id)
    if not novel: raise HTTPException(404)
    gen_chs = [c for c in novel.get("chapters",[]) if c.get("word_count",0) > 0]
    total = len(gen_chs)
    # Use 20章作为默认付费墙
    free_chs = min(total, 20)
    vip_chs = max(0, total - free_chs)
    free_quality = sum(c.get("quality_score",0) for c in gen_chs[:free_chs]) / max(free_chs, 1)
    vip_quality = sum(c.get("quality_score",0) for c in gen_chs[free_chs:]) / max(vip_chs, 1) if vip_chs > 0 else 0
    return {
        "total_chapters": total,
        "free_chapters": free_chs,
        "vip_chapters": vip_chs,
        "paywall_position": 20,
        "free_avg_quality": round(free_quality, 2),
        "vip_avg_quality": round(vip_quality, 2),
        "conversion_ready": free_quality >= 0.75 and total >= 15,
        "vip_quality_warning": vip_quality < free_quality and vip_chs > 0,
        "tips": [
            "付费墙前的最后一章(第20章)必须是全书最强钩子——读者在这一点'购买下一章'",
            f"当前免费章均分{free_quality:.2f}, 付费章均分{vip_quality:.2f}" + ("——⚠️ 付费章质量低于免费章，读者会觉得自己上当了" if vip_quality < free_quality and vip_chs > 0 else "——✅ 付费内容对得起读者的钱"),
            "每50章建议插入一章'付费读者专属番外'——提升续费率",
        ] if total > 0 else []
    }


@router.get("/api/novels/{novel_id}/optimal-publish-time")
def optimal_publish_time(novel_id: str) -> dict:
    """最佳发布时间：基于平台用户活跃时段，建议每天几点发布。"""
    return {
        "best_times": ["12:00-13:00（午休阅读高峰）", "18:00-20:00（通勤+晚饭后）", "21:00-23:00（睡前黄金档）"],
        "worst_times": ["02:00-06:00（没人醒着）", "09:00-11:00（工作时间）"],
        "recommendation": "每天固定18:00和21:00各发1章——培养读者追更习惯",
        "weekend_bonus": "周末多发1章——读者周末阅读时长是工作日2倍",
    }


@router.get("/api/novels/{novel_id}/estimate")
def estimate_cost(novel_id: str) -> dict:
    """预估生成成本。传入目标章数，返回预计花费。"""
    novel = db.get_novel(novel_id)
    if not novel: raise HTTPException(404)
    gen_chs = [c for c in novel.get("chapters",[]) if c.get("word_count",0) > 0]
    avg_words = sum(c["word_count"] for c in gen_chs) / len(gen_chs) if gen_chs else 2500
    provider = _get_provider(novel_id)
    model = provider.get("models","deepseek-v4-pro")[0] if provider else "gpt-4o"
    # Rough estimate: ~20000 input tokens + avg_words*3 output tokens per chapter
    from ..generator import Generator
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
    """崩溃恢复：检测最后一个完整生成的章节，从未完成的下一章继续。"""
    novel = db.get_novel(novel_id)
    if not novel: raise HTTPException(404)
    gen_chs = [c for c in novel.get("chapters",[]) if c.get("word_count",0) > 0]
    last_complete = max(c["number"] for c in gen_chs) if gen_chs else 0
    # Check if last chapter looks truncated
    if gen_chs:
        last_ch = gen_chs[-1]
        content = last_ch.get("content","")
        truncated = len(content) < 200 or content.endswith("...") or "未完" in content[-50:]
    else:
        truncated = False
    return {
        "last_complete_chapter": last_complete,
        "next_chapter": last_complete + 1,
        "last_chapter_truncated": truncated,
        "action": "regenerate_last" if truncated else "generate_next",
        "total_chapters": len(gen_chs),
    }


def generate_status(novel_id: str):
    return _get_status(novel_id)


@router.get("/api/novels/{novel_id}/generate/stream")
async def generate_stream_sse(novel_id: str) -> dict:
    """Server-Sent Events stream for real-time generation status."""
    import asyncio

    from fastapi.responses import StreamingResponse

    async def event_stream():
        last_progress = -1
        last_status = ""
        while True:
            status = _get_status(novel_id)
            # Only send if status changed
            current = f"{status.get('status')}-{status.get('progress')}"
            if current != last_status:
                last_status = current
                data = json.dumps(status)
                yield f"data: {data}\n\n"
            if status.get("status") in ("complete", "error", "idle"):
                if status.get("status") != "idle":
                    yield f"data: {json.dumps(status)}\n\n"
                break
            await asyncio.sleep(0.5)

    return StreamingResponse(event_stream(), media_type="text/event-stream",
                           headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

@router.get("/api/novels/{novel_id}/chapters/{chapter_num}/versions")
def chapter_versions(novel_id: str, chapter_num: int) -> dict:
    """Get version history for a chapter."""
    return {"versions": db.get_chapter_versions(novel_id, chapter_num)}


@router.get("/api/novels/{novel_id}/chapters/{chapter_num}/versions/{version_id}")
def chapter_version_content(version_id: int) -> dict:
    """Get a specific version's content."""
    content = db.get_chapter_version_content(version_id)
    if not content:
        raise HTTPException(404)
    return {"content": content}


# P2: Export chapter as TXT
@router.get("/api/novels/{novel_id}/chapters/{chapter_num}/export")
def export_chapter(novel_id: str, chapter_num: int) -> dict:
    ch = db.get_chapter(novel_id, chapter_num)
    if not ch:
        raise HTTPException(404, "Not found")
    from fastapi.responses import PlainTextResponse
    content = f"{ch['title']}\n\n{ch.get('content', '')}"
    return PlainTextResponse(content, media_type="text/plain; charset=utf-8",
                             headers={"Content-Disposition": f"attachment; filename=chapter_{chapter_num}.txt"})


@router.get("/api/novels/{novel_id}/export")
def export_novel(novel_id: str, fmt: str = "txt") -> dict:
    """Export entire novel as TXT or markdown."""
    novel = db.get_novel(novel_id)
    if not novel:
        raise HTTPException(404, "Novel not found")
    chapters = novel.get("chapters", [])
    gen = [c for c in chapters if c.get("word_count", 0) > 0]
    if not gen:
        raise HTTPException(400, "No generated chapters")

    if fmt == "md":
        lines = [f"# {novel['title']}", f"\n_{novel.get('synopsis','')}_\n"]
        for ch in gen:
            lines.append(f"## 第{ch['number']}章 {ch['title']}\n")
            lines.append(ch.get("content", ""))
            lines.append("")
        content = "\n\n".join(lines)
        media = "text/markdown; charset=utf-8"
    else:
        lines = [f"{novel['title']}", novel.get('synopsis',''), ""]
        for ch in gen:
            lines.append(f"\n{'─'*40}")
            lines.append(f"第{ch['number']}章 {ch['title']}")
            lines.append(f"{'─'*40}\n")
            content = ch.get("content", "")
            # Strip markdown headers from body
            import re
            content = re.sub(r'^#+\s*.*$', '', content, flags=re.MULTILINE).strip()
            lines.append(content)
        out = "\n".join(lines)
        content = out
        media = "text/plain; charset=utf-8"

    fn = f"{novel['title']}_{len(gen)}chapters.{fmt}"
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse(content, media_type=media,
                             headers={"Content-Disposition": f"attachment; filename*=UTF-8''{fn}"})

# P2: Delete chapter
@router.delete("/api/novels/{novel_id}/characters/{char_key}")
def delete_character(novel_id: str, char_key: str) -> dict:
    if not db.get_novel(novel_id):
        raise HTTPException(404, "Novel not found")
    with db.conn() as conn:
        conn.execute("DELETE FROM characters WHERE novel_id=? AND char_key=?", (novel_id, char_key))
    return {"ok": True}

@router.delete("/api/novels/{novel_id}/chapters/{chapter_num}")
def delete_chapter(novel_id: str, chapter_num: int) -> dict:
    with db.conn() as conn:
        conn.execute("DELETE FROM chapters WHERE novel_id=? AND number=?", (novel_id, chapter_num))
    return {"ok": True}

# P1: One-click demo
@router.post("/api/autonomous-novel")
def autonomous_novel(data: dict, background: BackgroundTasks) -> dict:
    """
    一键成书：输入简介和题材，全自动生成一本完整小说。
    自动：A/B测试选最优声音 → 生成全章 → 管线 → 书名 → 报告 → 导出
    """
    synopsis = data.get("synopsis", "").strip()
    genre = data.get("genre", "玄幻")
    title = data.get("title", "")
    chapters_count = data.get("chapters", 30)
    if not synopsis: raise HTTPException(400, "synopsis required")
    nid = data.get("id", f"auto-{int(__import__('time').time())%100000}")
    # Create novel
    if not db.get_novel(nid):
        from ..generator import random_protagonist_name
        name, _ = random_protagonist_name(genre)
        db.create_novel(id=nid, title=title or synopsis[:20], author="AI", synopsis=synopsis,
                        genre=genre, char_key="protagonist", name=name, role="主角")
    background.add_task(_run_autonomous, nid, chapters_count)
    return {"status": "autonomous", "novel_id": nid, "message": f"全自动生成{chapters_count}章中..."}


@router.post("/api/demo")
def create_demo(background: BackgroundTasks) -> dict:
    """Create a demo novel and generate the first chapter"""
    # Hard-delete any existing demo rows (including soft-deleted ones)
    with db.conn() as conn:
        conn.execute("DELETE FROM chapters WHERE novel_id='demo'")
        conn.execute("DELETE FROM characters WHERE novel_id='demo'")
        conn.execute("DELETE FROM factions WHERE novel_id='demo'")
        conn.execute("DELETE FROM novel_tags WHERE novel_id='demo'")
        conn.execute("DELETE FROM novels WHERE id='demo'")
    db.create_novel(
        id="demo", title="修仙从炼丹开始", author="AI", genre="玄幻",
        synopsis="一个普通药师，意外获得上古丹方，从此踏上修仙之路",
        world_name="九天大陆", world_era="上古", power_system="练气→筑基→金丹→元婴→化神",
        main_arc="从普通药师到丹帝的逆袭之路", current_arc="开篇",
        char_key="protagonist", name=_random_name("玄幻"), role="主角",
        personality="坚韧不拔，心思缜密", background="普通药师，自幼父母双亡",
        tags=["炼丹", "系统流", "逆袭"],
    )
    background.add_task(_run_generation, "demo")
    return {"status": "ok", "novel_id": "demo", "message": "Demo novel created, generating first chapter..."}


# ═══════════════ V5: World/Character Editor ═══════════════

@router.put("/api/novels/{novel_id}/world")
def update_world(novel_id: str, data: dict) -> dict:
    """Update world settings"""
    if not db.get_novel(novel_id):
        raise HTTPException(404)
    updates = {}
    for k in ['world_name','world_era','world_geo','power_system','main_arc','current_arc']:
        if k in data: updates[k] = data[k]
    # Handle world_rules: accept both list and JSON string
    if 'world_rules' in data:
        val = data['world_rules']
        updates['world_rules'] = json.dumps(val) if isinstance(val, list) else str(val)
    if updates:
        db.update_novel(novel_id, **updates)
    return {"ok": True}

@router.put("/api/novels/{novel_id}/characters/{char_key}")
def update_character(novel_id: str, char_key: str, data: dict) -> dict:
    """Update a character"""
    with db.conn() as conn:
        row = conn.execute("SELECT id FROM characters WHERE novel_id=? AND char_key=?",
                          (novel_id, char_key)).fetchone()
        if not row:
            raise HTTPException(404, "Character not found")
        fields = {k: data[k] for k in ['name','role','personality','background','power_level','status'] if k in data}
        if fields:
            sets = ", ".join(f"{k}=?," for k in fields)
            conn.execute(f"UPDATE characters SET {sets} updated_at=datetime('now') WHERE id=?",
                        list(fields.values()) + [row['id']])
    return {"ok": True}

@router.post("/api/novels/{novel_id}/characters")
def add_character(novel_id: str, data: dict) -> dict:
    """Add a new character"""
    if not db.get_novel(novel_id):
        raise HTTPException(404)
    char_key = data.get('char_key', '').strip()
    if not char_key: raise HTTPException(400, "char_key required")
    with db.conn() as conn:
        conn.execute("""INSERT INTO characters (novel_id,char_key,name,role,personality,background,power_level)
            VALUES (?,?,?,?,?,?,?)""",
            (novel_id, char_key, data.get('name',char_key), data.get('role','配角'),
             data.get('personality',''), data.get('background',''), data.get('power_level','')))
    return {"ok": True}

# ═══════════════ V5: Faction CRUD ═══════════════

@router.post("/api/novels/{novel_id}/factions")
def add_faction(novel_id: str, data: dict) -> dict:
    if not db.get_novel(novel_id):
        raise HTTPException(404)
    name = data.get('name', '').strip()
    if not name: raise HTTPException(400, "name required")
    with db.conn() as conn:
        conn.execute("INSERT INTO factions (novel_id,name,description,leader,sort_order) VALUES (?,?,?,?,?)",
                     (novel_id, name, data.get('description',''), data.get('leader',''), data.get('sort_order',0)))
    return {"ok": True}

@router.put("/api/novels/{novel_id}/factions/{faction_id}")
def update_faction(novel_id: str, faction_id: int, data: dict) -> dict:
    with db.conn() as conn:
        row = conn.execute("SELECT id FROM factions WHERE id=? AND novel_id=?", (faction_id, novel_id)).fetchone()
        if not row: raise HTTPException(404)
        fields = {k: data[k] for k in ['name','description','leader','sort_order'] if k in data}
        if fields:
            sets = ", ".join(f"{k}=?" for k in fields)
            conn.execute(f"UPDATE factions SET {sets} WHERE id=?", list(fields.values()) + [faction_id])
    return {"ok": True}

@router.delete("/api/novels/{novel_id}/factions/{faction_id}")
def delete_faction(novel_id: str, faction_id: int) -> dict:
    with db.conn() as conn:
        conn.execute("DELETE FROM factions WHERE id=? AND novel_id=?", (faction_id, novel_id))
    return {"ok": True}

# ═══════════════ V5: Chapter Outline ═══════════════

@router.get("/api/novels/{novel_id}/outline")
def get_outline(novel_id: str) -> dict:
    """Get chapter outline — planned (word_count=0) chapters"""
    if not db.get_novel(novel_id):
        raise HTTPException(404)
    with db.conn() as conn:
        # Outline: chapters with word_count=0 (planned but not yet generated)
        outline_rows = conn.execute("""SELECT number, title, summary FROM chapters 
            WHERE novel_id=? AND word_count=0 ORDER BY number""", (novel_id,)).fetchall()
        # Generated chapters summary for context
        gen_rows = conn.execute("""SELECT number, title, summary FROM chapters 
            WHERE novel_id=? AND word_count>0 ORDER BY number DESC LIMIT 5""", (novel_id,)).fetchall()
    return {
        "outline": [{"number": r["number"], "title": r["title"], "summary": r["summary"]} for r in outline_rows],
        "recent_chapters": [{"number": r["number"], "title": r["title"], "summary": r["summary"]} for r in gen_rows],
        "next_number": (max([r["number"] for r in outline_rows], default=0)
                        if outline_rows else (gen_rows[0]["number"] + 1 if gen_rows else 1)),
    }

@router.post("/api/novels/{novel_id}/outline")
def save_outline(novel_id: str, data: dict) -> dict:
    """Save chapter outline items — only for chapters not yet generated"""
    if not db.get_novel(novel_id):
        raise HTTPException(404)
    items = data.get('items', [])
    with db.conn() as conn:
        for item in items:
            num = item.get('number', 0)
            if num <= 0: continue
            # Check if chapter already has content (don't overwrite)
            existing = conn.execute(
                "SELECT word_count FROM chapters WHERE novel_id=? AND number=?", (novel_id, num)
            ).fetchone()
            if existing and existing['word_count'] > 0:
                continue  # Skip — don't overwrite generated chapters
            conn.execute("""INSERT OR REPLACE INTO chapters (novel_id,number,title,summary,word_count)
                VALUES (?,?,?,?,0)""", (novel_id, num, item.get('title',''), item.get('summary','')))
    return {"ok": True}

@router.delete("/api/novels/{novel_id}/outline/{chapter_num}")
def delete_outline_item(novel_id: str, chapter_num: int) -> dict:
    """Delete an outline item (only if it has no content)"""
    with db.conn() as conn:
        existing = conn.execute(
            "SELECT word_count FROM chapters WHERE novel_id=? AND number=?", (novel_id, chapter_num)
        ).fetchone()
        if not existing:
            raise HTTPException(404)
        if existing['word_count'] > 0:
            raise HTTPException(400, "Cannot delete outline for a generated chapter")
        conn.execute("DELETE FROM chapters WHERE novel_id=? AND number=? AND word_count=0",
                     (novel_id, chapter_num))
    return {"ok": True}

# ═══════════════ Outline Suggestions (AI) ═══════════════

@router.post("/api/novels/{novel_id}/suggest-outline")
def suggest_outline(novel_id: str) -> dict:
    """AI suggests 3 next-chapter directions based on current novel state."""
    novel = db.get_novel(novel_id)
    if not novel:
        raise HTTPException(404, "Novel not found")

    # Gather context: recent chapters, synopsis, genre
    chapters = novel.get("chapters", [])
    gen_chapters = [c for c in chapters if c.get("word_count", 0) > 0]
    recent_titles = [c.get("title", "") for c in gen_chapters[-5:]]
    recent_hooks = [c.get("ending_hook", "") for c in gen_chapters[-3:] if c.get("ending_hook")]
    synopsis = novel.get("synopsis", "")
    genre = novel.get("genre", "玄幻")
    next_ch = len(gen_chapters) + 1

    prompt = f"""你是资深网文编辑。基于以下小说信息，建议第{next_ch}章的3个不同走向。

小说类型：{genre}
简介：{synopsis}
最近章节：{' -> '.join(recent_titles) if recent_titles else '无'}
{'上章钩子：' + '；'.join(recent_hooks) if recent_hooks else ''}

请给出3个不同的下一章方向。每个方向20-40字，格式严格如下（每行一个方向，共3行）：
标题：xxx | 钩子：xxx | 摘要：xxx | 基调：xxx
"""

    try:
        from ..config import Config
        from ..generator import Generator
        provider = _get_provider(novel_id)
        cfg = Config(
            openai_api_key=provider.get("api_key", ""),
            openai_base_url=provider.get("base_url", ""),
            model=provider.get("models", "deepseek-v4-pro")[0] if provider.get("models") else "gpt-4o",
        )
        gen = Generator(cfg)
        raw = gen._call_llm_with_retry(
            [{"role": "user", "content": prompt}],
            max_tokens=256,
        )
    except Exception as e:
        raise HTTPException(500, f"LLM call failed: {e}")

    # Parse response into structured suggestions
    suggestions = []
    for line in raw.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        parts = {}
        for segment in line.split("|"):
            segment = segment.strip()
            if "：" in segment:
                k, v = segment.split("：", 1)
                parts[k] = v
        if "标题" in parts:
            suggestions.append({
                "title": parts.get("标题", "").strip(),
                "hook": parts.get("钩子", parts.get("钩子", "")).strip(),
                "summary": parts.get("摘要", "").strip(),
                "tone": parts.get("基调", "").strip(),
            })
        if len(suggestions) >= 3:
            break

    # Fallback: if parsing failed, return raw as single suggestion
    if not suggestions:
        suggestions = [{"title": f"第{next_ch}章", "hook": raw[:80], "summary": raw[:150], "tone": genre}]

    return {"next_chapter": next_ch, "suggestions": suggestions[:3]}


# ═══════════════ Cover Generation ═══════════════

@router.post("/api/novels/{novel_id}/generate-cover")
def generate_cover(novel_id: str) -> dict:
    """Generate an AI image prompt + placeholder SVG cover for the novel."""
    novel = db.get_novel(novel_id)
    if not novel:
        raise HTTPException(404, "Novel not found")

    title = novel.get("title", "未命名")
    synopsis = novel.get("synopsis", "")
    genre = novel.get("genre", "玄幻")
    author = novel.get("author", "AI")

    # Generate image prompt via LLM
    img_prompt = ""
    try:
        from ..config import Config
        from ..generator import Generator
        provider = _get_provider(novel_id)
        cfg = Config(
            openai_api_key=provider.get("api_key", ""),
            openai_base_url=provider.get("base_url", ""),
            model=provider.get("models", "deepseek-v4-pro")[0] if provider.get("models") else "gpt-4o",
        )
        gen = Generator(cfg)
        prompt_text = f"""你是一个小说封面设计师。为以下小说生成一个AI绘图提示词（英文，50词以内），用于生成封面图。

小说名：《{title}》
类型：{genre}
简介：{synopsis}

要求：风格适配{genre}类型，有意境，适合做封面。只输出英文提示词。"""
        img_prompt = gen._call_llm_with_retry(
            [{"role": "user", "content": prompt_text}],
            max_tokens=128,
        )
    except Exception:
        img_prompt = f"A mystical {genre} novel cover with atmospheric lighting, cinematic composition"

    # Generate placeholder SVG cover with Chinese text
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

    # Escape text for SVG
    import html
    title_esc = html.escape(title)
    author_esc = html.escape(author)
    genre_esc = html.escape(genre)

    # Truncate long titles for SVG display
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
  <text x="200" y="340" text-anchor="middle" font-family="SimSun, STSong, serif" font-size="14" fill="#ffffff99" letter-spacing="8">{genre_esc}</text>
  <text x="200" y="460" text-anchor="middle" font-family="SimSun, STSong, serif" font-size="12" fill="#ffffff60" letter-spacing="3">{author_esc}</text>
  <text x="200" y="560" text-anchor="middle" font-family="SimSun, STSong, serif" font-size="10" fill="#ffffff30">AI Lingmo</text>
</svg>'''

    return {
        "prompt": img_prompt.strip(),
        "svg_cover": svg_cover,
        "title": title,
        "genre": genre,
    }


# ═══════════════ V6: Clone Novel ═══════════════

@router.post("/api/novels/{novel_id}/clone")
def clone_novel(novel_id: str, data: dict | None = None) -> dict:
    """Clone a novel: copy world, characters, factions, outline (not generated chapters)."""
    original = db.get_novel(novel_id)
    if not original:
        raise HTTPException(404, "Original novel not found")

    data = data or {}
    new_genre = data.get("genre", original.get("genre", "玄幻"))
    new_title = data.get("title", original.get("title", "") + "（副本）")
    new_name = data.get("protagonist_name", "").strip() or (
        _random_name(new_genre) if new_genre != original.get("genre") else "")

    # Generate unique ID
    import random as _random
    for _ in range(10):
        suffix = str(_random.randint(10, 99))
        new_id = f"{novel_id}-copy-{suffix}"
        if not db.get_novel(new_id):
            break
    else:
        new_id = f"{novel_id}-copy-{int(__import__('time').time())}"

    # Create the clone with same world settings
    novel = db.create_novel(
        id=new_id, title=new_title, author=original.get("author", "AI"),
        synopsis=original.get("synopsis", ""), genre=new_genre,
        world_name=original.get("world_name", ""),
        world_era=original.get("world_era", ""),
        world_geo=original.get("world_geo", ""),
        power_system=original.get("power_system", ""),
        world_rules=original.get("world_rules", "[]"),
        main_arc=original.get("main_arc", ""),
        current_arc=original.get("current_arc", "开篇"),
        arc_chapter_start=1,
        tags=json.loads(original.get("tags", "[]")) if isinstance(original.get("tags"), str) else original.get("tags", []),
        char_key="protagonist",
        name=new_name or original.get("characters", [{}])[0].get("name", "主角") if original.get("characters") else "主角",
        role="主角",
        personality=original.get("characters", [{}])[0].get("personality", "") if original.get("characters") else "",
        background=original.get("characters", [{}])[0].get("background", "") if original.get("characters") else "",
        power_level=original.get("characters", [{}])[0].get("power_level", "") if original.get("characters") else "",
    )

    # Copy extra characters (skip protagonist, already created)
    for ch in original.get("characters", []):
        if ch.get("char_key") == "protagonist":
            continue
        try:
            with db.conn() as conn:
                conn.execute("""INSERT INTO characters (novel_id,char_key,name,role,personality,background,power_level,status)
                    VALUES (?,?,?,?,?,?,?,?)""",
                    (new_id, ch.get("char_key", ""), ch.get("name", ""), ch.get("role", "配角"),
                     ch.get("personality", ""), ch.get("background", ""),
                     ch.get("power_level", ""), ch.get("status", "alive")))
        except Exception:
            pass

    # Copy factions
    for faction in original.get("factions", []):
        try:
            with db.conn() as conn:
                conn.execute("INSERT INTO factions (novel_id,name,description,leader,sort_order) VALUES (?,?,?,?,?)",
                    (new_id, faction.get("name", ""), faction.get("description", ""),
                     faction.get("leader", ""), faction.get("sort_order", 0)))
        except Exception:
            pass

    # Copy outline chapters (word_count=0 only)
    for ch in original.get("chapters", []):
        if ch.get("word_count", 0) == 0:
            try:
                with db.conn() as conn:
                    conn.execute("INSERT INTO chapters (novel_id,number,title,summary,word_count) VALUES (?,?,?,?,0)",
                        (new_id, ch.get("number", 0), ch.get("title", ""), ch.get("summary", "")))
            except Exception:
                pass

    # Copy plot points
    for pp in original.get("plot_points", []):
        try:
            with db.conn() as conn:
                conn.execute("INSERT INTO plot_points (novel_id,type,content,is_resolved,sort_order) VALUES (?,?,?,?,?)",
                    (new_id, pp.get("type", "plot"), pp.get("content", ""), pp.get("is_resolved", 0), pp.get("sort_order", 0)))
        except Exception:
            pass

    # Copy style profile
    try:
        old_style = db.get_style_profile(novel_id)
        if old_style:
            old_style.pop("novel_id", None)
            old_style["version"] = 1
            db.save_style_profile(new_id, old_style)
    except Exception:
        pass
    db.log(novel_id, "novel.cloned", {"new_id": new_id, "genre": new_genre, "title": new_title})
    return {"status": "ok", "novel_id": new_id, "title": new_title}

# ═══════════════ V7: Analytics & Prompt Optimization ═══════════════

def _compute_analytics(novel_id: str) -> dict:
    """Compute retention curve and insights from performance_logs + chapters."""
    chapters_data = []
    with db.conn() as conn:
        # Join chapters with performance_logs
        rows = conn.execute("""
            SELECT c.number, c.title, c.word_count, c.quality_score,
                   c.ending_hook,
                   COALESCE(p.views, 0) as views,
                   COALESCE(p.comments, 0) as comments
            FROM chapters c
            LEFT JOIN performance_logs p ON p.novel_id = c.novel_id AND p.chapter_number = c.number
            WHERE c.novel_id = ? AND c.word_count > 0
            ORDER BY c.number
        """, (novel_id,)).fetchall()

        if not rows:
            return {"chapters": [], "drop_off_points": [], "insights": []}

        for r in rows:
            # Score hook strength from ending_hook
            hook_keywords = ['？', '！', '突然', '竟然', '难道', '什么', '怎么', '为何', '……']
            hook = r["ending_hook"] or ""
            hook_score = sum(1 for kw in hook_keywords if kw in hook) / max(len(hook_keywords), 1)
            hook_score = min(hook_score * 2, 1.0)  # normalize to 0-1

            chapters_data.append({
                "number": r["number"],
                "title": r["title"],
                "word_count": r["word_count"],
                "quality_score": round(r["quality_score"] or 0, 2),
                "hook_score": round(hook_score, 2),
                "views": r["views"] or 0,
                "comments": r["comments"] or 0,
            })

    # Compute retention between consecutive chapters
    drop_off_points = []
    quality_scores = []
    retention_rates = []
    for i in range(len(chapters_data) - 1):
        curr = chapters_data[i]
        nxt = chapters_data[i + 1]
        curr_views = max(curr["views"], 1)
        nxt_views = nxt["views"]
        retention = round(nxt_views / curr_views, 2) if curr_views > 0 else 0
        curr["retention_to_next"] = retention
        if nxt_views > 0 and retention < 0.5:
            drop_off_points.append(nxt["number"])
        if nxt_views > 0:
            quality_scores.append(nxt["quality_score"])
            retention_rates.append(retention)

    # Quality vs retention correlation (Pearson simplified)
    correlation = 0
    if len(quality_scores) >= 3:
        n = len(quality_scores)
        mean_q = sum(quality_scores) / n
        mean_r = sum(retention_rates) / n
        cov = sum((quality_scores[i] - mean_q) * (retention_rates[i] - mean_r) for i in range(n))
        var_q = sum((q - mean_q) ** 2 for q in quality_scores)
        var_r = sum((r - mean_r) ** 2 for r in retention_rates)
        if var_q > 0 and var_r > 0:
            correlation = round(cov / ((var_q * var_r) ** 0.5), 2)

    # Generate insights
    insights = []
    # Drop-off chapters
    for dp in drop_off_points[:5]:
        ch = next((c for c in chapters_data if c["number"] == dp), None)
        if ch and ch["quality_score"] < 0.6:
            insights.append(f"第{dp}章质量分{ch['quality_score']}，读者流失——建议重写或加强钩子")
        elif ch:
            insights.append(f"第{dp}章读者流失，质量分{ch['quality_score']}正常，检查开头是否吸引力不足")

    # Hook score analysis
    low_hook_chapters = [c for c in chapters_data[-5:] if c.get("hook_score", 0) < 0.4]
    if low_hook_chapters:
        nums = ", ".join(str(c["number"]) for c in low_hook_chapters)
        insights.append(f"第{nums}章钩子评分偏低，建议加强结尾悬念")

    # Word count analysis
    if chapters_data:
        short_chapters = [c for c in chapters_data[-5:] if c["word_count"] < 1800]
        if short_chapters:
            nums = ", ".join(str(c["number"]) for c in short_chapters)
            insights.append(f"第{nums}章字数<1800，章节过短可能导致留存下降")

    # Correlation insight
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
    """Get chapter analytics: retention, drop-off points, quality correlation."""
    if not db.get_novel(novel_id):
        raise HTTPException(404, "Novel not found")
    return _compute_analytics(novel_id)


@router.get("/api/novels/{novel_id}/foreshadowing")
def get_foreshadowing_audit(novel_id: str) -> dict:
    """Get foreshadowing audit: open, stale, recovered stats."""
    if not db.get_novel(novel_id):
        raise HTTPException(404, "Novel not found")
    from ..config import Config
    from ..generator import Generator
    provider = _get_provider(novel_id)
    cfg = Config(openai_api_key=provider.get("api_key",""), openai_base_url=provider.get("base_url",""),
                 model=provider.get("models","deepseek-v4-pro")[0] if provider.get("models") else "gpt-4o")
    gen = Generator(cfg)
    state = _load_state(novel_id)
    if not state:
        raise HTTPException(500, "Failed to load state")
    return gen.audit_foreshadowing(state)


@router.get("/api/novels/{novel_id}/continuity")
def chapter_continuity(novel_id: str) -> dict:
    """章节间连续性热力图：每对相邻章节的连贯性评分。"""
    novel = db.get_novel(novel_id)
    if not novel: raise HTTPException(404)
    gen_chs = [c for c in novel.get("chapters",[]) if c.get("word_count",0) > 0]
    if len(gen_chs) < 2: return {"pairs": [], "issues": []}
    pairs = []
    issues = []
    for i in range(len(gen_chs) - 1):
        curr, nxt = gen_chs[i], gen_chs[i+1]
        # Check continuity signals
        curr_end = (curr.get("ending_hook") or "")[-100:]
        nxt_start = (nxt.get("content") or "")[:100]
        # Score: do hook keywords from curr_end appear in nxt_start?
        hook_kw = ['？','！','……','突然','竟然','发现','知道','原来']
        hook_hits = sum(1 for kw in hook_kw if kw in curr_end)
        # Score: does nxt_start address the hook?
        addressed = any(kw in nxt_start for kw in ['？','！','但','可是','然后','于是'])
        continuity = min(1.0, (hook_hits * 0.3 + (1 if addressed else 0) * 0.5 + 0.2))
        pairs.append({
            "from": curr["number"], "to": nxt["number"],
            "continuity": round(continuity, 2),
            "hook_present": hook_hits > 0,
            "hook_addressed": addressed,
        })
        if continuity < 0.5:
            issues.append(f"第{curr['number']}→{nxt['number']}章连续性弱({continuity:.2f})")
    return {"pairs": pairs, "issues": issues}


@router.get("/api/costs")
def get_costs(novel_id: str = "") -> dict:
    """Get cost summary for a novel or all novels."""
    return db.get_cost_summary(novel_id)


@router.get("/api/costs/summary")
def costs_summary() -> dict:
    """Get full cost summary with by-novel breakdown for dashboard display."""
    summary = db.get_cost_summary()
    # Compute chapter-level costs from chapters table as a fallback if cost_logs is empty
    if summary["total_cost"] == 0:
        with db.conn() as c:
            rows = c.execute("""SELECT novel_id, COUNT(*) as chapters,
                SUM(cost) as cost FROM chapters WHERE cost > 0 GROUP BY novel_id""").fetchall()
            if rows:
                summary["by_novel"] = [dict(r) for r in rows]
                summary["total_cost"] = round(sum(r["cost"] for r in rows), 4)
    return summary


@router.post("/api/novels/{novel_id}/optimize-prompt")
def optimize_prompt(novel_id: str, background: BackgroundTasks) -> dict:
    """Analyze performance and auto-tune StyleProfile parameters."""
    if not db.get_novel(novel_id):
        raise HTTPException(404, "Novel not found")

    analytics = _compute_analytics(novel_id)
    chapters = analytics.get("chapters", [])
    adjustments = []

    # Load current style
    from dataclasses import asdict
    from ..generator import StyleProfile, _get_style_for_genre
    novel = db.get_novel(novel_id)
    style_data = db.get_style_profile(novel_id)
    if style_data:
        style = StyleProfile(**{k: v for k, v in style_data.items() if k in StyleProfile.__dataclass_fields__})
    else:
        style = _get_style_for_genre(novel.get("genre", "玄幻") if novel else "玄幻")

    old_profile = asdict(style)

    if chapters:
        recent = chapters[-5:]
        # Hook density tuning
        avg_hook = sum(c.get("hook_score", 0) for c in recent) / len(recent)
        if avg_hook < 0.4:
            old_hook = style.hook_interval_words
            style.hook_interval_words = max(400, style.hook_interval_words - 100)
            adjustments.append(f"钩子密度+{int((1-old_hook/style.hook_interval_words)*100)}%（{old_hook}→{style.hook_interval_words}字/钩）")
            if "结尾钩子前加一句角色内心独白制造悬念" not in style.special_rules:
                style.special_rules.append("结尾钩子前加一句角色内心独白制造悬念")

        # Word count tuning
        avg_wc = sum(c["word_count"] for c in recent) / len(recent)
        if avg_wc < style.target_word_count[0]:
            old_min = style.target_word_count[0]
            style.target_word_count = (max(1200, style.target_word_count[0] - 200), style.target_word_count[1])
            adjustments.append(f"目标字数下限下调 {old_min - style.target_word_count[0]} 字")

        # Retention-based pace tuning
        retentions = [c.get("retention_to_next", 0) for c in chapters[-4:-1] if c.get("retention_to_next", 0) > 0]
        if len(retentions) >= 3 and all(r < 0.7 for r in retentions):
            if style.pace_pattern != "三强一缓":
                style.pace_pattern = "三强一缓"
                adjustments.append("节奏切换为三强一缓")
            if "本章必须发生一个改变故事走向的事件" not in style.special_rules:
                style.special_rules.append("本章必须发生一个改变故事走向的事件（新角色登场/旧角色死亡/秘密揭露）")

        # Check if certain climax types are absent for 5+ chapters
        if len(chapters) >= 5:
            recent_bodies = [""] * 5  # simplified — would need actual content
            missing_types = [
                ct for ct in style.climax_types
                if not any(ct in (c.get("title", "") + c.get("ending_hook", "")) for c in recent)
            ]
            if missing_types:
                adjustments.append(f"爽点类型'{missing_types[0]}'已连续多章未出现")
                if f"本章应包含{missing_types[0]}类型事件" not in style.special_rules:
                    style.special_rules.append(f"本章应包含{missing_types[0]}类型事件")

    # Save
    try:
        db.save_style_profile(novel_id, asdict(style))
    except Exception:
        db.save_style_profile(novel_id, style.__dict__)

    new_profile = asdict(style)

    return {
        "adjustments": adjustments,
        "old_profile": old_profile,
        "new_profile": new_profile,
        "analytics_summary": {
            "total_chapters": len(chapters),
            "avg_quality": round(sum(c["quality_score"] for c in chapters[-5:]) / min(5, len(chapters)), 2) if chapters else 0,
            "drop_off_count": len(analytics.get("drop_off_points", [])),
        },
    }

# ═══════════════ AI Proofread ═══════════════

@router.post("/api/novels/{novel_id}/chapters/{chapter_num}/proofread")
def proofread_chapter(novel_id: str, chapter_num: int) -> dict:
    """AI校对：找出错别字、重复用词、逻辑不连贯、标点错误。"""
    ch = db.get_chapter(novel_id, chapter_num)
    if not ch:
        raise HTTPException(404, "Chapter not found")
    content = ch.get("content", "")
    if not content:
        raise HTTPException(400, "Chapter has no content")

    from ..config import Config
    from ..generator import Generator
    provider = _get_provider(novel_id)
    cfg = Config(
        openai_api_key=provider.get("api_key", ""),
        openai_base_url=provider.get("base_url", ""),
        model=provider.get("models", ["deepseek-v4-pro"])[0] if provider.get("models") else "gpt-4o",
    )
    gen = Generator(cfg)

    # Process content in chunks if too long (max ~3000 chars per chunk)
    chunk_size = 3000
    chunks = [content[i:i+chunk_size] for i in range(0, len(content), chunk_size)]
    all_issues: list[dict] = []

    for ci, chunk in enumerate(chunks):
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

        result = gen._call_llm_with_retry([
            {"role": "system", "content": "你是一位专业的中文校对编辑。你只返回JSON数组，不返回任何其他内容。"},
            {"role": "user", "content": prompt},
        ], max_tokens=4096)

        try:
            # Extract JSON from response (may be wrapped in markdown code blocks)
            json_str = result.strip()
            if json_str.startswith("```"):
                json_str = re.sub(r'^```(?:json)?\s*', '', json_str)
                json_str = re.sub(r'\s*```$', '', json_str)
            issues = json.loads(json_str)
            if isinstance(issues, list):
                all_issues.extend(issues)
        except (json.JSONDecodeError, TypeError):
            # If parsing fails, try to extract JSON array from the text
            match = re.search(r'\[.*\]', result, re.DOTALL)
            if match:
                try:
                    issues = json.loads(match.group())
                    if isinstance(issues, list):
                        all_issues.extend(issues)
                except (json.JSONDecodeError, TypeError):
                    pass

    return {
        "novel_id": novel_id,
        "chapter": chapter_num,
        "issues": all_issues,
        "total": len(all_issues),
    }


# ═══════════════ Import External Novels ═══════════════

@router.post("/api/novels/import")
async def import_novel(
    title: str = Form(...),
    genre: str = Form("玄幻"),
    file: UploadFile = File(...),
):
    """从外部文件导入小说（支持 TXT 和 EPUB）。"""
    import io

    if not title.strip():
        raise HTTPException(400, "title required")

    # Read file content
    raw_bytes = await file.read()
    filename = (file.filename or "").lower()

    if filename.endswith(".epub"):
        # EPUB parsing
        try:
            import ebooklib
            from ebooklib import epub
        except ImportError:
            raise HTTPException(500, "ebooklib not installed. Run: pip install ebooklib")

        book = epub.read_epub(io.BytesIO(raw_bytes))
        chapters_data: list[tuple[str, str]] = []

        # Try to get chapters from TOC/spine
        toc_items: list = []
        for item in book.toc:
            if isinstance(item, tuple):
                _extract_toc_items(item, toc_items)
            elif hasattr(item, 'get_name'):
                toc_items.append(item)

        # If no TOC, use all document items in spine order
        if not toc_items:
            toc_items = [doc for doc in book.get_items_of_type(ebooklib.ITEM_DOCUMENT)]

        for item in toc_items:
            try:
                html_content = item.get_content().decode("utf-8", errors="ignore") if isinstance(item.get_content(), bytes) else item.get_content()
                # Strip HTML tags
                text = re.sub(r'<[^>]+>', '', html_content)
                text = re.sub(r'\n{3,}', '\n\n', text).strip()
                if text and len(text) > 50:  # Skip very short sections
                    # Try to extract chapter title from first meaningful line
                    lines = text.split("\n")
                    title_line = ""
                    for line in lines:
                        stripped = line.strip()
                        if stripped and len(stripped) < 50:
                            title_line = stripped
                            break
                    chapters_data.append((title_line or f"第{len(chapters_data)+1}章", text))
            except Exception:
                continue

    elif filename.endswith(".txt"):
        # TXT parsing
        text = raw_bytes.decode("utf-8", errors="ignore")
        chapters_data = _detect_chapters_from_text(text)

    else:
        raise HTTPException(400, "Unsupported file format. Please upload .txt or .epub")

    if not chapters_data:
        raise HTTPException(400, "No chapter content found in the uploaded file")

    # Create novel
    novel_id = re.sub(r'[^a-z0-9-]', '', title.lower().replace(' ', '-')[:40])
    if not novel_id:
        from uuid import uuid4
        novel_id = uuid4().hex[:12]

    # Ensure unique ID
    base_id = novel_id
    counter = 1
    while db.get_novel(novel_id):
        novel_id = f"{base_id}-{counter}"
        counter += 1

    novel = db.create_novel(
        id=novel_id,
        title=title.strip(),
        genre=genre,
        synopsis="",
    )

    # Add chapters
    for i, (ch_title, ch_content) in enumerate(chapters_data, 1):
        word_count = len(ch_content)
        summary = ch_content[:200].replace("\n", " ")
        db.add_chapter(
            novel_id=novel_id,
            number=i,
            title=ch_title or f"第{i}章",
            word_count=word_count,
            summary=summary,
            content=ch_content,
            ending_hook="",
        )

    return {
        "novel_id": novel_id,
        "title": title.strip(),
        "chapters_imported": len(chapters_data),
        "total_words": sum(len(c[1]) for c in chapters_data),
    }


def _extract_toc_items(item, result: list):
    """Recursively extract items from EPUB TOC tuples."""
    if isinstance(item, tuple) and len(item) >= 2:
        # item[1] could be a list of sub-items
        if isinstance(item[1], list):
            for sub in item[1]:
                _extract_toc_items(sub, result)
        elif hasattr(item[1], 'get_name'):
            result.append(item[1])
    elif hasattr(item, 'get_name'):
        result.append(item)


def _detect_chapters_from_text(text: str) -> list[tuple[str, str]]:
    """Detect chapter breaks from plain text and return [(title, content), ...]."""
    # Common chapter break patterns
    patterns = [
        r'(第[一二三四五六七八九十百千\d]+[章节回卷部集幕])',
        r'(Chapter\s+\d+)',
        r'(CHAPTER\s+\d+)',
        r'(第\d+[章节回卷部集幕])',
    ]

    lines = text.split("\n")
    chapter_indices = []

    for i, line in enumerate(lines):
        stripped = line.strip()
        for pat in patterns:
            if re.match(pat, stripped):
                chapter_indices.append(i)
                break

    if len(chapter_indices) < 2:
        # No chapter structure detected, return entire text as one chapter
        return [("", text.strip())]

    chapters = []
    for idx, line_idx in enumerate(chapter_indices):
        title = lines[line_idx].strip()
        start = line_idx + 1
        end = chapter_indices[idx + 1] if idx + 1 < len(chapter_indices) else len(lines)
        content = "\n".join(lines[start:end]).strip()
        if content:
            chapters.append((title, content))

    return chapters


# ═══════════════ Cloud Backup ═══════════════

import datetime as dt
import io as _io
import os
import zipfile as _zipfile

_BACKUP_STATUS_FILE = Path("data") / ".backup_status.json"


def _read_backup_status() -> dict:
    """Read last backup status from disk."""
    try:
        if _BACKUP_STATUS_FILE.exists():
            return json.loads(_BACKUP_STATUS_FILE.read_text())
    except Exception:
        pass
    return {}


def _write_backup_status(status: dict) -> None:
    """Write last backup status to disk."""
    try:
        _BACKUP_STATUS_FILE.write_text(json.dumps(status, default=str))
    except Exception:
        pass


@router.post("/api/backup/cloud")
def cloud_backup() -> dict:
    """Create a timestamped zip of data/novel_writer.db and upload to S3-compatible storage.

    Requires environment variables: S3_ENDPOINT, S3_BUCKET, S3_ACCESS_KEY, S3_SECRET_KEY.
    Returns {"status": "not_configured"} if any are missing.
    """
    s3_endpoint = os.environ.get("S3_ENDPOINT", "").strip()
    s3_bucket = os.environ.get("S3_BUCKET", "").strip()
    s3_access_key = os.environ.get("S3_ACCESS_KEY", "").strip()
    s3_secret_key = os.environ.get("S3_SECRET_KEY", "").strip()

    if not all([s3_endpoint, s3_bucket, s3_access_key, s3_secret_key]):
        return {"status": "not_configured"}

    db_path = Path("data/novel_writer.db")
    if not db_path.exists():
        raise HTTPException(500, "Database file not found at data/novel_writer.db")

    now = dt.datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    key = f"backup-{date_str}.zip"

    try:
        import boto3

        # Create zip in memory
        buf = _io.BytesIO()
        with _zipfile.ZipFile(buf, "w", _zipfile.ZIP_DEFLATED) as zf:
            zf.write(db_path, arcname="novel_writer.db")
        buf.seek(0)
        data = buf.read()
        size = len(data)

        # Upload to S3-compatible storage
        client = boto3.client(
            "s3",
            endpoint_url=s3_endpoint,
            aws_access_key_id=s3_access_key,
            aws_secret_access_key=s3_secret_key,
        )
        client.put_object(Bucket=s3_bucket, Key=key, Body=data, ContentType="application/zip")

        # Keep last 30 backups, delete older ones
        resp = client.list_objects_v2(Bucket=s3_bucket, Prefix="backup-")
        if resp.get("Contents"):
            backups = sorted(resp["Contents"], key=lambda o: o["Key"], reverse=True)
            for obj in backups[30:]:
                client.delete_object(Bucket=s3_bucket, Key=obj["Key"])

        # Persist backup status
        status = {
            "last_backup": now.isoformat(),
            "last_backup_key": key,
            "last_backup_size": size,
            "configured": True,
        }
        _write_backup_status(status)

        return {"status": "ok", "key": key, "size": size}
    except ImportError:
        raise HTTPException(500, "boto3 not installed. Run: pip install boto3")
    except Exception as e:
        raise HTTPException(500, f"Backup failed: {str(e)[:300]}")


@router.get("/api/backup/status")
def backup_status() -> dict:
    """Return whether cloud backup is configured and the last backup time."""
    s3_endpoint = os.environ.get("S3_ENDPOINT", "").strip()
    s3_bucket = os.environ.get("S3_BUCKET", "").strip()
    s3_access_key = os.environ.get("S3_ACCESS_KEY", "").strip()
    s3_secret_key = os.environ.get("S3_SECRET_KEY", "").strip()
    configured = all([s3_endpoint, s3_bucket, s3_access_key, s3_secret_key])

    status = _read_backup_status()
    return {
        "configured": configured,
        "last_backup": status.get("last_backup"),
        "last_backup_key": status.get("last_backup_key"),
        "last_backup_size": status.get("last_backup_size"),
    }


# ═══════════════ Static ═══════════════

# SPA fallback: serve static files if they exist, otherwise index.html
# ═══════════════ Unsaid Book + Story Bible API ═══════════════

@router.get("/api/novels/{novel_id}/unsaid")
def get_unsaid(novel_id: str) -> dict:
    if not db.get_novel(novel_id): raise HTTPException(404)
    return {"entries": db.get_unsaid(novel_id)}

@router.post("/api/novels/{novel_id}/unsaid")
def add_unsaid(novel_id: str, data: dict) -> dict:
    entry = (data.get("entry") or "").strip()
    if not entry or len(entry) < 2: raise HTTPException(400, "Entry too short")
    db.save_unsaid(novel_id, entry)
    return {"ok": True}

@router.delete("/api/novels/{novel_id}/unsaid/{entry_id}")
def remove_unsaid(novel_id: str, entry_id: int) -> dict:
    db.delete_unsaid(entry_id)
    return {"ok": True}

# ═══════════════ Story Bible API ═══════════════

@router.get("/api/novels/{novel_id}/story-bible")
def get_story_bible(novel_id: str) -> dict:
    """Get complete story bible for a novel."""
    if not db.get_novel(novel_id):
        raise HTTPException(404, "Novel not found")
    return {
        "characters": db.get_character_state(novel_id),
        "foreshadowing": db.get_active_foreshadowing(novel_id),
        "locations": db.get_location_history(novel_id),
        "timeline": db.get_timeline(novel_id),
        "world_rules": db.get_world_state(novel_id),
        "consistency_log": db.get_consistency_log(novel_id)[:20],
        "cost_ledger": db.get_cost_ledger(novel_id),
    }


# ═══════════════ Text Analysis API ═══════════════

@router.post("/api/text/analyze")
def analyze_text(data: dict) -> dict:
    """Run all client-side analyses server-side for a given text."""
    text = (data.get("text") or data.get("content") or "").strip()
    if not text or len(text) < 10:
        raise HTTPException(400, "Text too short")

    import re
    chars = len(text.replace('\n', '').replace(' ', ''))

    # Density
    contradictions = len(re.findall(r'但是|可是|然而|却|不过|只是', text))
    questions = len(re.findall(r'[？?]', text))
    suspensions = len(re.findall(r'…|\.\.\.', text))
    surprises = len(re.findall(r'[！!]', text))
    density = round((contradictions + questions + suspensions + surprises) / max(1, chars / 100), 1)

    # Forces
    reversals = len(re.findall(r'但是|可是|然而|却|不过|没想到|谁知|不料', text))
    sentences = [s for s in re.split(r'[。！？.!?\n]+', text) if s.strip()]
    torque = round(min(1, reversals / max(1, len(sentences) * 0.1)), 2)

    # Body sense
    visual = len(re.findall(r'看|见|望|盯|瞪|光|亮|暗|黑|白|红|蓝|绿|色', text))
    tactile = len(re.findall(r'碰|触|摸|握|抓|按|压|冷|热|凉|暖|烫|疼|痛', text))
    auditory = len(re.findall(r'听|闻|声|响|音|说|道|问|答|喊|叫|吼|静|默', text))

    # Opening strength
    first_sentences = sentences[:3]
    has_body = any(re.findall(r'碰|触|摸|握|冷|热|疼|痛|看|见|听|闻', '。'.join(first_sentences)))
    has_expect = any(re.findall(r'[？?…]|但是|可是|然而|不过', '。'.join(first_sentences)))
    opening_strength = (1 if has_body else 0) + (1 if has_expect else 0)

    return {
        "chars": chars, "sentences": len(sentences),
        "density": density,
        "forces": {"torque": torque},
        "body_sense": {"visual": visual, "tactile": tactile, "auditory": auditory, "total": visual+tactile+auditory},
        "opening": {"strength": opening_strength, "assessment": "强" if opening_strength >= 2 else "可" if opening_strength >= 1 else "弱"},
        "style_fingerprint": {
            "sentence_length": round(chars / max(1, len(sentences))),
            "dialogue_ratio": round(len(re.findall(r'「|」|"', text)) / max(1, chars) * 100, 1),
            "description_ratio": round(len(re.findall(r'看|见|望|光|色|影', text)) / max(1, chars) * 100, 1),
        },
    }


# ═══════════════ Wound Agent (§48) + Energy Form (§63) ═══════════════

@router.get("/api/novels/{novel_id}/wound-arc")
def get_wound_arc(novel_id: str) -> dict:
    """Track the narrative wound arc across chapters (§48)."""
    if not db.get_novel(novel_id): raise HTTPException(404)
    chars = db.get_character_state(novel_id)
    timeline = db.get_timeline(novel_id)
    costs = db.get_cost_ledger(novel_id)

    # Wound = cumulative losses / total chapters = how much the story "costs"
    losses = [e for e in costs if e.get('loss')]
    wound_score = len(losses) / max(1, len(timeline)) if timeline else 0

    # Find the primary wound carrier (character with most losses)
    char_losses: dict[str, int] = {}
    for e in costs:
        if e.get('loss') and e.get('character_name'):
            char_losses[e['character_name']] = char_losses.get(e['character_name'], 0) + 1
    primary = max(char_losses, key=lambda k: char_losses[k]) if char_losses else "未知"

    return {
        "primary_carrier": primary,
        "wound_score": round(wound_score, 2),
        "total_losses": len(losses),
        "arc_stage": "深化" if wound_score > 0.3 else "建立" if wound_score > 0 else "未启动",
        "suggestion": "伤口足够深，可以开始愈合弧线" if wound_score > 0.3 else "需要更多代价来建立伤口深度",
    }


@router.get("/api/novels/{novel_id}/energy-form")
def get_energy_form(novel_id: str) -> dict:
    """Track energy transformation across chapters (§63)."""
    if not db.get_novel(novel_id): raise HTTPException(404)
    tl = db.get_timeline(novel_id)
    costs = db.get_cost_ledger(novel_id)
    chars = db.get_character_state(novel_id)

    if not tl:
        return {"current": "潜在", "history": [], "suggestion": "故事尚未开始"}

    # Map energy: gains=kinetic, losses=potential, emotions=thermal, reveals=explosive
    recent_losses = [e for e in costs if e.get('loss')][-3:]
    recent_emotions = [c.get('emotion','') for c in chars[-5:] if c.get('emotion')]

    # Determine current energy form
    if any('愤怒' in e or '恨' in e for e in recent_emotions):
        current = "动能"
    elif len(recent_losses) >= 2:
        current = "势能"
    elif any('悲伤' in e or '悔' in e for e in recent_emotions):
        current = "热"
    elif len(costs) > len(tl) * 0.5:
        current = "爆炸"
    else:
        current = "潜在"

    return {
        "current": current,
        "chapter_count": len(tl),
        "loss_density": round(len(recent_losses) / max(1, len(tl)), 2),
        "suggestion": (
            "能量积累充足，适合释放（高潮章节）" if current == "势能"
            else "能量正在释放，注意释放后的余波处理" if current == "爆炸"
            else "能量平稳，适合推进或铺垫"
        ),
    }


# ═══════════════ System Self-Check Matrix (§57) ═══════════════

@router.get("/api/novels/{novel_id}/self-check")
def system_self_check(novel_id: str) -> dict:
    """Run all agents and return a unified confidence report."""
    if not db.get_novel(novel_id): raise HTTPException(404)

    results = {}
    confidence = 100

    # Bible extraction
    chars = db.get_character_state(novel_id)
    results['bible'] = {"status": "ok" if chars else "empty", "chars": len(chars)}
    if not chars: confidence -= 25

    # Foreshadowing
    fs = db.get_active_foreshadowing(novel_id)
    overdue = [f for f in fs if f.get('status') == 'overdue']
    results['foreshadowing'] = {"active": len(fs), "overdue": len(overdue)}
    if overdue: confidence -= len(overdue) * 10

    # Consistency
    issues = db.get_consistency_log(novel_id)
    errors = [i for i in issues if i.get('severity') == 'error']
    unfixed = [i for i in issues if not i.get('was_fixed')]
    results['consistency'] = {"total": len(issues), "errors": len(errors), "unfixed": len(unfixed)}
    confidence -= len(errors) * 15 - len([i for i in issues if i.get('was_fixed')]) * 10

    # Cost balance
    costs = db.get_cost_ledger(novel_id)
    gains = len([e for e in costs if e.get('gain')])
    losses = len([e for e in costs if e.get('loss')])
    bal = gains - losses
    results['costs'] = {"gains": gains, "losses": losses, "balance": bal}
    if abs(bal) > 3: confidence -= 10

    # Voice profile
    voice = db.get_voice_samples(novel_id)
    results['voice'] = {"samples": len(voice)}
    if not voice: confidence -= 5

    # Unsaid
    unsaid = db.get_unsaid(novel_id)
    results['unsaid'] = {"entries": len(unsaid)}

    confidence = max(0, min(100, confidence))

    return {
        "results": results,
        "confidence": confidence,
        "grade": "S" if confidence >= 90 else "A" if confidence >= 75 else "B" if confidence >= 60 else "C" if confidence >= 40 else "D",
        "ready_for_next": confidence >= 60,
    }


# ═══════════════ Reader Agent API ═══════════════

@router.get("/api/novels/{novel_id}/reader-state")
def get_reader_state(novel_id: str) -> dict:
    if not db.get_novel(novel_id): raise HTTPException(404)
    novel = db.get_novel(novel_id)
    total = novel.get("total_chapters", 0)
    chars = db.get_character_state(novel_id)
    known = [{"name": c['char_name'], "emotion": c.get('emotion','')} for c in chars[-5:]]
    active_fs = db.get_active_foreshadowing(novel_id)
    expecting = [{"desc": f['description'][:60], "due": f.get('due_by_chapter')} for f in active_fs[:3]]
    costs = db.get_cost_ledger(novel_id)
    gains = len([e for e in costs if e.get('gain')])
    losses = len([e for e in costs if e.get('loss')])
    return {
        "current_chapter": total, "known_characters": known, "expecting": expecting,
        "cost_balance": {"gains": gains, "losses": losses},
        "reader_mood": "engaged" if len(expecting) >= 2 else "drifting",
        "suggestion": "读者期待值高" if len(expecting) >= 2 else "可推进主线",
    }


# ═══════════════ Narrative Distance Agent (§22) ═══════════════

@router.get("/api/novels/{novel_id}/narrative-distance")
def get_narrative_distance(novel_id: str) -> dict:
    """Measure narrative distance: immersion (近距离) vs observation (远距离)."""
    if not db.get_novel(novel_id):
        raise HTTPException(404, "Novel not found")
    novel = db.get_novel(novel_id)
    total = novel.get("total_chapters", 0)
    if total == 0:
        return {"distance_0_pct": 0, "distance_1_pct": 0, "distance_2_pct": 0,
                "assessment": "无章节数据"}

    # Read up to 3 latest chapters
    start = max(1, total - 2)
    texts: list[str] = []
    for n in range(start, total + 1):
        ch = db.get_chapter(novel_id, n)
        if ch:
            texts.append(ch.get("content", ""))
    all_text = " ".join(texts)

    if len(all_text) < 50:
        return {"distance_0_pct": 0, "distance_1_pct": 0, "distance_2_pct": 0,
                "assessment": "内容不足"}

    # Immersion signals (近距离): 1st-person markers, sensory immediacy, interior thought
    first_person = len(re.findall(r'我|我的|我们', all_text))
    sensory = len(re.findall(r'疼|痛|冷|热|凉|暖|触|摸|碰|气味|味道|听见|闻到', all_text))
    interior = len(re.findall(r'想|觉得|知道|明白|心里|暗自|心底|记得|忘了', all_text))
    immersion = first_person + sensory + interior

    # Observation signals (远距离): 3rd-person markers, visual description, measurement
    third_person = len(re.findall(r'他|她|他们|她们|它', all_text))
    visual = len(re.findall(r'看|见|望|看见|望去|凝望|远望|眺|盯|瞪', all_text))
    measurement = len(re.findall(r'米|公里|步|分钟|小时|秒|丈|尺|寸', all_text))
    observation = third_person + visual + measurement

    total_signals = immersion + observation
    if total_signals == 0:
        return {"distance_0_pct": 0, "distance_1_pct": 0, "distance_2_pct": 0,
                "assessment": "无法判定"}

    # Distance 0: immediate (close, immersive) — mainly immersion signals
    d0 = round(immersion / total_signals * 100, 1)
    # Distance 2: distant (observer) — mainly observation signals
    d2 = round(observation / total_signals * 100, 1)
    # Distance 1: intermediate (mixed signals)
    d1 = round(100 - d0 - d2, 1)

    if d0 > 55:
        assessment = "近距离主导：读者高度沉浸于角色感知"
    elif d2 > 55:
        assessment = "远距离主导：叙述者保持旁观距离"
    else:
        assessment = "中距离：沉浸与观察交替"

    return {"distance_0_pct": d0, "distance_1_pct": max(0, d1), "distance_2_pct": d2,
            "assessment": assessment}


# ═══════════════ Information Gradient Agent (§43) ═══════════════

@router.get("/api/novels/{novel_id}/info-gradient")
def get_info_gradient(novel_id: str, chapter: int = 0) -> dict:
    """Analyze dialogue for information asymmetry between characters."""
    if not db.get_novel(novel_id):
        raise HTTPException(404, "Novel not found")

    novel = db.get_novel(novel_id)
    total = novel.get("total_chapters", 0)
    if total == 0:
        return {"gradient_level": 1, "hot_spots": [], "assessment": "无章节数据"}

    # Use specified chapter or latest
    target = chapter if chapter > 0 else total
    ch = db.get_chapter(novel_id, target)
    if not ch:
        raise HTTPException(404, f"Chapter {target} not found")
    content = ch.get("content", "")

    if len(content) < 50:
        return {"gradient_level": 1, "hot_spots": [], "assessment": "内容不足"}

    # Extract dialogue lines (lines between quotes)
    dialogue_pattern = re.compile(r'[「『"](.+?)[」』"]')
    dialogues = dialogue_pattern.findall(content)

    # Negation + subtext markers: information is being hidden or distorted
    negation_markers = r'没说|没有说|不说|沉默|其实|真正|不是你想的那样|不是那样的|不是这样'
    subtext_markers = r'弦外之音|言外之意|话中有话|暗示|言下之意|暗指|别有深意|意味深长'

    hot_spots: list[str] = []
    gradient_score = 0
    for d in dialogues:
        if len(d) < 5:
            continue
        neg_count = len(re.findall(negation_markers, d))
        sub_count = len(re.findall(subtext_markers, d))
        if neg_count + sub_count > 0:
            hot_spots.append(d[:80] + ("..." if len(d) > 80 else ""))
            gradient_score += neg_count + sub_count

    # Normalize to 1-5 scale
    if len(dialogues) == 0:
        gradient_level = 1
    elif gradient_score >= 6:
        gradient_level = 5
    elif gradient_score >= 4:
        gradient_level = 4
    elif gradient_score >= 2:
        gradient_level = 3
    elif gradient_score >= 1:
        gradient_level = 2
    else:
        gradient_level = 1

    level_labels = {1: "信息透明", 2: "轻微不对称", 3: "明显不对称", 4: "高度不对称", 5: "信息极致失衡"}
    assessment = f"{len(hot_spots)}处信息不对称，梯度等级{gradient_level}：{level_labels[gradient_level]}"

    return {"gradient_level": gradient_level, "hot_spots": hot_spots[:10],
            "dialogue_count": len(dialogues), "assessment": assessment}


# ═══════════════ POV Shift Agent (§54) ═══════════════

@router.get("/api/novels/{novel_id}/pov-shifts")
def get_pov_shifts(novel_id: str) -> dict:
    """Detect POV per chapter and track when it shifts between chapters."""
    if not db.get_novel(novel_id):
        raise HTTPException(404, "Novel not found")

    novel = db.get_novel(novel_id)
    total = novel.get("total_chapters", 0)
    if total == 0:
        return {"shifts": [], "consistency": "consistent", "assessment": "无章节数据"}
    if total < 2:
        return {"shifts": [], "consistency": "consistent", "assessment": "仅一章，无法判断切换"}

    # Get character states for available character names
    chars = db.get_character_state(novel_id)
    known_names = [c.get("char_name", "") for c in chars if c.get("char_name")]

    # Per chapter: count name mentions to find dominant POV character
    pov_per_chapter: list[dict] = []
    for n in range(1, total + 1):
        ch = db.get_chapter(novel_id, n)
        if not ch:
            continue
        content = ch.get("content", "")
        if len(content) < 20:
            continue

        name_counts: dict[str, int] = {}
        for name in known_names:
            count = content.count(name)
            if count > 0:
                name_counts[name] = count

        # Fallback: generic pronouns as POV indicator
        first_person = content.count("我") - content.count("我们") // 2
        if name_counts:
            dominant = max(name_counts, key=lambda k: name_counts[k])
            dominant_count = name_counts[dominant]
        elif first_person > 3:
            dominant = "我(第一人称)"
            dominant_count = first_person
        else:
            dominant = "未知"
            dominant_count = 0

        pov_per_chapter.append({
            "chapter": n,
            "dominant_char": dominant,
            "mentions": dominant_count,
            "all_mentions": name_counts,
        })

    # Track shifts: when dominant character changes between adjacent chapters
    shifts: list[dict] = []
    for i in range(1, len(pov_per_chapter)):
        prev = pov_per_chapter[i - 1]
        curr = pov_per_chapter[i]
        if prev["dominant_char"] != curr["dominant_char"] and prev["dominant_char"] != "未知":
            shifts.append({
                "from_chapter": prev["chapter"],
                "from_char": prev["dominant_char"],
                "to_chapter": curr["chapter"],
                "to_char": curr["dominant_char"],
            })

    shift_ratio = len(shifts) / max(1, len(pov_per_chapter) - 1)
    if shift_ratio == 0:
        consistency = "consistent"
    elif shift_ratio < 0.3:
        consistency = "mostly_consistent"
    elif shift_ratio < 0.6:
        consistency = "shifting"
    else:
        consistency = "highly_shifting"

    return {"shifts": shifts, "pov_per_chapter": pov_per_chapter,
            "consistency": consistency,
            "assessment": f"共{len(shifts)}次POV切换，{total}章"}


# ═══════════════ Narrative Voice Agent (§47) ═══════════════

@router.get("/api/novels/{novel_id}/narrative-voice")
def get_narrative_voice(novel_id: str) -> dict:
    """Determine narrative person (1st vs 3rd) and tense hint."""
    if not db.get_novel(novel_id):
        raise HTTPException(404, "Novel not found")

    novel = db.get_novel(novel_id)
    total = novel.get("total_chapters", 0)
    if total == 0:
        return {"person": "unknown", "tense_hint": "unknown",
                "consistency": "unknown", "assessment": "无章节数据"}

    # Read first 3 chapters (or as many as available)
    texts: list[str] = []
    for n in range(1, min(4, total + 1)):
        ch = db.get_chapter(novel_id, n)
        if ch:
            texts.append(ch.get("content", ""))
    all_text = " ".join(texts)

    if len(all_text) < 50:
        return {"person": "unknown", "tense_hint": "unknown",
                "consistency": "unknown", "assessment": "内容不足"}

    # Count 1st vs 3rd person markers
    first_count = len(re.findall(r'我[^们]|我的', all_text))  # Exclude collective "we"
    third_count = len(re.findall(r'他[^们]|她[^们]|他的|她的', all_text))

    total_person = first_count + third_count
    if total_person == 0:
        person = "unknown"
    elif first_count > third_count * 2:
        person = "first"
    elif third_count > first_count * 2:
        person = "third"
    else:
        person = "mixed"

    # Tense hint: check common past/present markers
    past_markers = len(re.findall(r'了|过|曾经|那时|当年|从前|已经|已', all_text))
    present_markers = len(re.findall(r'正在|现在|此刻|着|在(?!了)', all_text))

    if past_markers > present_markers * 3:
        tense_hint = "past"
    elif present_markers > past_markers * 3:
        tense_hint = "present"
    else:
        tense_hint = "mixed"

    # Check consistency: sample later chapters for shifts
    if total >= 5:
        mid = total // 2
        late_texts: list[str] = []
        for n in [mid, total]:
            ch = db.get_chapter(novel_id, n)
            if ch:
                late_texts.append(ch.get("content", ""))
        late_text = " ".join(late_texts)
        late_first = len(re.findall(r'我[^们]|我的', late_text))
        late_third = len(re.findall(r'他[^们]|她[^们]|他的|她的', late_text))

        if person == "first" and late_third > late_first * 2:
            consistency = "shifting"
        elif person == "third" and late_first > late_third * 2:
            consistency = "shifting"
        else:
            consistency = "consistent"
    else:
        consistency = "consistent"

    person_labels = {"first": "第一人称", "third": "第三人称", "mixed": "混合人称", "unknown": "未确定"}
    ratio = round(first_count / max(1, total_person) * 100, 1)

    return {"person": person, "tense_hint": tense_hint,
            "first_pct": ratio, "third_pct": round(100 - ratio, 1),
            "consistency": consistency,
            "assessment": f"{person_labels[person]}主导，{consistency}"}


# ═══════════════ Anti-Narrative Agent (§60) ═══════════════

@router.post("/api/novels/{novel_id}/anti-narrative")
def get_anti_narrative(novel_id: str, data: dict) -> dict:
    """Generate the anti-narrative: what happens when conventions are inverted."""
    if not db.get_novel(novel_id):
        raise HTTPException(404, "Novel not found")

    chapter_num = data.get("chapter_num", 0)
    scene_description = (data.get("scene_description") or "").strip()
    expected_next = data.get("expected_next", [])

    if not scene_description:
        raise HTTPException(400, "scene_description is required")
    if not isinstance(expected_next, list) or len(expected_next) == 0:
        raise HTTPException(400, "expected_next must be a non-empty list")

    # For each expected event, produce its opposite
    anti_events: list[str] = []
    outcome_pairs: list[dict] = []

    # Simple inversion rules based on common narrative patterns
    invert_map = {
        "成功": "失败", "失败": "成功", "赢": "输", "输": "赢",
        "活着": "死亡", "死": "复活", "相遇": "错过", "错过": "相遇",
        "拯救": "毁灭", "毁灭": "拯救", "得到": "失去", "失去": "得到",
        "和解": "决裂", "决裂": "和解", "留下": "离开", "离开": "留下",
        "前进": "后退", "后退": "前进", "开放": "封闭", "封闭": "开放",
        "战斗": "谈判", "谈判": "放弃",
        "揭露": "隐藏", "隐藏": "揭露", "坦白": "撒谎", "撒谎": "坦白",
        "爱": "恨", "恨": "理解",
    }

    for event in (expected_next or []):
        if not isinstance(event, str) or not event.strip():
            continue
        text = event.strip()
        anti_text = text
        # Apply inversion rules
        for pos, neg in invert_map.items():
            if pos in text:
                anti_text = text.replace(pos, f"__ANTI_{pos}__")
                break
        for pos, neg in invert_map.items():
            anti_text = anti_text.replace(f"__ANTI_{pos}__", neg)

        if anti_text == text:
            # No direct inversion found — add negation prefix
            anti_text = f"不是{text}，而是相反的情况"

        anti_events.append(anti_text)
        outcome_pairs.append({"expected": text, "anti": anti_text})

    # Generate suggestion
    if len(anti_events) >= 3:
        suggestion = "试完全反写：反写高潮、反写结尾、反写情感 —— 全部逆行"
    elif len(anti_events) >= 2:
        suggestion = "选一个反事件放大为核心反转"
    else:
        suggestion = f"试试'{anti_events[0]}'这个方向"

    return {
        "scene": scene_description[:120],
        "chapter_num": chapter_num,
        "expected": expected_next,
        "anti": anti_events,
        "pairs": outcome_pairs,
        "suggestion": suggestion,
    }


# ═══════════════ Reverse Reading Agent (§15) ═══════════════

@router.get("/api/novels/{novel_id}/reverse-reading")
def reverse_reading(novel_id: str) -> dict:
    """Scan earliest chapters for sentences that gain new meaning given later reveals."""
    if not db.get_novel(novel_id): raise HTTPException(404)
    novel = db.get_novel(novel_id)
    chapters = novel.get("chapters", [])
    patterns = re.compile(r'不知道|没说|没问|沉默|看起来|似乎|好像|也许|大概|其实|未必|不敢|不敢说')
    sentences: list[dict] = []
    for ch in chapters[:3]:
        content = ch.get("content", "")
        for m in re.finditer(r'[^。！？\n]{6,}[。！？]', content):
            sent = m.group().strip()
            if patterns.search(sent):
                sentences.append({
                    "chapter": ch["number"],
                    "text": sent[:100],
                    "potential_new_meaning": "读者已知后续，这句话可能另有深意"
                })
    return {"sentences": sentences[:10], "count": len(sentences)}


# ═══════════════ Scream Moment Agent (§24) ═══════════════

@router.get("/api/novels/{novel_id}/scream-moments")
def scream_moments(novel_id: str) -> dict:
    """Find hidden connections: repeated unique phrases appearing in chapters far apart."""
    if not db.get_novel(novel_id): raise HTTPException(404)
    novel = db.get_novel(novel_id)
    chapters = novel.get("chapters", [])
    phrase_map: dict[str, list[int]] = {}
    for ch in chapters:
        content = ch.get("content", "")
        words = re.findall(r'[一-鿿]{3,}', content)
        for w in set(words):
            phrase_map.setdefault(w, []).append(ch["number"])
    connections: list[dict] = []
    for phrase, chs in phrase_map.items():
        if len(chs) >= 2:
            chs_sorted = sorted(set(chs))
            for i in range(len(chs_sorted)):
                for j in range(i + 1, len(chs_sorted)):
                    gap = chs_sorted[j] - chs_sorted[i]
                    if gap > 5:
                        connections.append({"phrase": phrase, "ch1": chs_sorted[i], "ch2": chs_sorted[j], "gap": gap})
    connections.sort(key=lambda x: x["gap"], reverse=True)
    strongest = (
        f"'{connections[0]['phrase']}' 在第{connections[0]['ch1']}章和第{connections[0]['ch2']}章之间相隔{connections[0]['gap']}章出现"
        if connections else "暂无跨章节呼应"
    )
    return {"connections": connections[:15], "strongest": strongest}


# ═══════════════ Ending Agent (§35) ═══════════════

@router.get("/api/novels/{novel_id}/ending-candidates")
def ending_candidates(novel_id: str) -> dict:
    """Scan for dormant images — unique details appearing only 1-2 times across all chapters."""
    if not db.get_novel(novel_id): raise HTTPException(404)
    novel = db.get_novel(novel_id)
    chapters = novel.get("chapters", [])
    phrase_chs: dict[str, list[int]] = {}
    for ch in chapters:
        content = ch.get("content", "")
        phrases = re.findall(r'[一-鿿]{2,4}', content)
        for p in set(phrases):
            phrase_chs.setdefault(p, []).append(ch["number"])
    dormant: list[dict] = []
    for phrase, chs in phrase_chs.items():
        if 1 <= len(chs) <= 2 and len(phrase) >= 3:
            dormant.append({
                "image": phrase,
                "first_appearance_chapter": chs[0],
                "last_appearance_chapter": chs[-1],
            })
    dormant.sort(key=lambda x: x["first_appearance_chapter"])
    recommendation = (
        f"建议在终章回收意象：'{dormant[0]['image']}'（首现第{dormant[0]['first_appearance_chapter']}章）"
        if dormant else "暂无休眠意象，可继续铺垫"
    )
    return {"dormant": dormant[:20], "recommendation": recommendation}


# ═══════════════ Midpoint Agent (§64) ═══════════════

@router.get("/api/novels/{novel_id}/midpoint-health")
def midpoint_health(novel_id: str) -> dict:
    """Check if the story's midpoint has enough hangout time vs plot density."""
    if not db.get_novel(novel_id): raise HTTPException(404)
    novel = db.get_novel(novel_id)
    chapters = novel.get("chapters", [])
    total = len(chapters)
    if total == 0: return {"midpoint_chapter": 0, "plot_density": 0, "hangout_score": 0, "assessment": "暂无章节"}
    mid = max(1, total // 2)
    plot_kw = ['杀', '死', '逃', '追', '战', '打', '破', '碎', '险', '危', '急', '决', '变', '转']
    hangout_kw = ['说', '笑', '吃', '喝', '走', '看', '坐', '聊', '问', '答', '想', '等', '陪', '一起']
    start, end = max(0, mid - 2), min(total, mid + 3)
    plot_count = 0
    hangout_count = 0
    for ch in chapters[start:end]:
        content = ch.get("content", "")[:500]
        plot_count += sum(1 for kw in plot_kw if kw in content)
        hangout_count += sum(1 for kw in hangout_kw if kw in content)
    window = max(1, end - start)
    plot_density = round(plot_count / window, 1)
    hangout_score = round(hangout_count / window, 1)
    if 3 < plot_density < 8:
        assessment = "剧情密度适中，节奏良好"
    elif plot_density >= 8:
        assessment = "事件过密，缺少喘息空间——建议在中点前后插入相处场景"
    else:
        assessment = "相处时间充足，读者对角色投入足够"
    return {
        "midpoint_chapter": mid, "plot_density": plot_density,
        "hangout_score": hangout_score, "assessment": assessment,
    }


# ═══════════════ Ritual Agent (§49) ═══════════════

@router.get("/api/novels/{novel_id}/rituals")
def rituals(novel_id: str) -> dict:
    """Track repeated gestures/phrases (2-4 chars) appearing in 3+ different chapters."""
    if not db.get_novel(novel_id): raise HTTPException(404)
    novel = db.get_novel(novel_id)
    chapters = novel.get("chapters", [])
    phrase_chs: dict[str, list[int]] = {}
    for ch in chapters:
        content = ch.get("content", "")
        phrases = re.findall(r'[一-鿿]{2,4}', content)
        for p in set(phrases):
            phrase_chs.setdefault(p, []).append(ch["number"])
    result: list[dict] = []
    for phrase, chs in phrase_chs.items():
        if len(chs) >= 3:
            chs_sorted = sorted(set(chs))
            first = chs_sorted[0]
            last = chs_sorted[-1]
            total_chs = len(chapters)
            if last - first > total_chs * 0.5:
                progression = "growing"
            elif first < total_chs * 0.3 and last < total_chs * 0.3:
                progression = "fading"
            else:
                progression = "stable"
            result.append({"phrase": phrase, "chapters": chs_sorted, "meaning_progression": progression})
    result.sort(key=lambda x: len(x["chapters"]), reverse=True)
    return {"rituals": result[:15]}


# ═══════════════ Time Spiral Agent (§76) ═══════════════

@router.get("/api/novels/{novel_id}/time-spiral")
def time_spiral(novel_id: str) -> dict:
    """What would early chapters mean now that the author knows how the story ends?"""
    if not db.get_novel(novel_id): raise HTTPException(404)
    novel = db.get_novel(novel_id)
    chapters = novel.get("chapters", [])
    total = len(chapters)
    if total < 6: return {"early_state": "故事太短", "late_state": "暂无", "meaning_shift": "需要更多章节才能分析"}
    early = chapters[:3]
    late = chapters[-3:]
    early_chars = set()
    late_chars = set()
    for ch in early:
        content = ch.get("content", "")[:500]
        found = re.findall(r'(他|她|它|我|你)[一-鿿]{2,6}', content)
        early_chars.update(found[:5])
    for ch in late:
        content = ch.get("content", "")[:500]
        found = re.findall(r'(他|她|它|我|你)[一-鿿]{2,6}', content)
        late_chars.update(found[:5])
    early_state = f"前3章角色状态：{', '.join(list(early_chars)[:3]) or '未知'}"
    late_state = f"后3章角色状态：{', '.join(list(late_chars)[:3]) or '未知'}"
    meaning_shift = "回头再看开头，那些看似寻常的细节——一句话、一个眼神、一次犹豫——都在后来的故事里获得了全新的重量。读者此时才明白，那不是闲笔，是伏笔。" if early_chars != late_chars else "开篇与结尾状态一致，首尾形成闭环"
    return {"early_state": early_state, "late_state": late_state, "meaning_shift": meaning_shift}


# ═══════════════ First Draft Protection Agent (§73) ═══════════════

_protected_drafts: dict[str, set[int]] = {}

@router.post("/api/novels/{novel_id}/draft-protect")
def draft_protect(novel_id: str, body: dict) -> dict:
    """Mark a chapter as first-draft protected — no auto-analysis runs on it."""
    if not db.get_novel(novel_id): raise HTTPException(404)
    chapter_num = body.get("chapter_num")
    is_first_draft = body.get("is_first_draft", False)
    if chapter_num is None:
        raise HTTPException(400, "chapter_num is required")
    key = f"{novel_id}"
    if key not in _protected_drafts:
        _protected_drafts[key] = set()
    if is_first_draft:
        _protected_drafts[key].add(chapter_num)
    else:
        _protected_drafts[key].discard(chapter_num)
    return {
        "protected": is_first_draft,
        "note": "First draft protected. No analysis will run." if is_first_draft else "Protection removed.",
    }


# ═══════════════ Abandonment Agent (§74) ═══════════════

@router.get("/api/novels/{novel_id}/abandonment-candidates")
def abandonment_candidates(novel_id: str) -> dict:
    """Identify chapters that might be candidates for deletion or restructuring."""
    if not db.get_novel(novel_id): raise HTTPException(404)
    novel = db.get_novel(novel_id)
    chapters = novel.get("chapters", [])
    candidates: list[dict] = []
    for i, ch in enumerate(chapters):
        wc = ch.get("word_count", 0) or 0
        content = ch.get("content", "")
        chars = db.get_character_state(novel_id, ch["number"])
        reasons: list[str] = []
        if wc < 500 and wc > 0:
            reasons.append(f"字数极低({wc}字)")
        if not chars and wc > 0:
            reasons.append("未提取到角色状态")
        if i > 0 and i < len(chapters) - 1:
            prev_content = chapters[i - 1].get("content", "")[:200]
            curr_content = content[:200]
            overlap = len(set(prev_content) & set(curr_content))
            if overlap > 80:
                reasons.append("与前一章内容高度重复")
        if reasons:
            suggestion = "merge" if "重复" in reasons[0] else ("delete" if wc < 300 else "move")
            candidates.append({"chapter": ch["number"], "reason": "；".join(reasons), "suggestion": suggestion})
    assessment = f"发现{len(candidates)}个可优化章节" if candidates else "所有章节状态良好"
    return {"candidates": candidates, "assessment": assessment}


# ═══════════════ Boundary Agent (§77) ═══════════════

@router.get("/api/novels/{novel_id}/boundary-check")
def boundary_check(novel_id: str) -> dict:
    """Return rules for when the system should stay silent."""
    if not db.get_novel(novel_id): raise HTTPException(404)
    return {
        "rules": [
            "never give final answer",
            "never rush human choice",
            "never pretend to feel",
            "never exploit vulnerability",
            "never replace the moment of not-looking-away",
        ],
        "active": True,
    }


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


# --- 1. Pre-understanding Agent (§17) ---
@router.get("/api/novels/{novel_id}/pre-understanding")
def pre_understanding(novel_id: str) -> dict:
    """Simulate 3 reader types: novice, veteran, critic (pure heuristic, no LLM)."""
    novel = db.get_novel(novel_id)
    if not novel:
        raise HTTPException(404)

    genre = novel.get("genre", "") or ""
    chapters = novel.get("chapters", [])

    # Gather all available text
    all_text_parts: list[str] = []
    for ch in chapters:
        c = db.get_chapter(novel_id, ch["number"])
        if c and c.get("content"):
            all_text_parts.append(c["content"])
    all_text = " ".join(all_text_parts)
    if not all_text.strip():
        all_text = novel.get("synopsis", "") or ""

    tropes = GENRE_TROPES.get(genre, GENRE_TROPES_DEFAULT)

    # --- novice: count genre trope presence ---
    novice_hits = sum(1 for t in tropes if t in all_text)
    novice_score = min(100, round(novice_hits / max(1, len(tropes)) * 100))

    # --- veteran: count tropes that are SUBVERTED ---
    # A trope is considered subverted when a subversion signal follows within 60 chars
    veteran_hits = 0
    for trope in tropes:
        for m in re.finditer(re.escape(trope), all_text):
            after = all_text[m.end():m.end() + 60]
            if any(sig in after for sig in SUBVERSION_SIGNALS):
                veteran_hits += 1
                break
    veteran_score = min(100, round(veteran_hits / max(1, len(tropes)) * 100))

    # --- critic: count narrative technique signals ---
    critic_raw = 0
    for _technique, signals in NARRATIVE_SIGNALS.items():
        for sig in signals:
            critic_raw += all_text.count(sig)
    critic_score = min(100, critic_raw * 3)

    # --- suggested adjustment ---
    if veteran_score > novice_score:
        suggested = (
            f"资深读者感知到{veteran_score}%的反套路——建议继续强化反套路叙事，"
            f"当前套路符合度仅{novice_score}%"
        )
    elif critic_score > 50:
        suggested = (
            f"叙事技巧密度较高({critic_score}%)——适合文学向读者，"
            "但可能牺牲可读性，建议适度简化"
        )
    elif novice_score > 70:
        suggested = (
            f"套路符合度高({novice_score}%)——新手读者友好，"
            f"建议加入{veteran_hits}个反套路点提升老读者体验"
        )
    else:
        suggested = "建议明确体裁定位，增加核心套路元素以匹配读者预期"

    return {
        "novice_score": novice_score,
        "veteran_score": veteran_score,
        "critic_score": critic_score,
        "suggested_adjustment": suggested,
        "genre": genre,
    }


# --- 2. Psychological Time Agent (§51) ---
@router.get("/api/novels/{novel_id}/psych-time")
def psych_time(novel_id: str, chapter: int) -> dict:
    """Estimate reading time vs story time for a chapter."""
    ch = db.get_chapter(novel_id, chapter)
    if not ch:
        raise HTTPException(404)
    content = ch.get("content", "") or ""

    # Story time: sum all time markers weighted by their duration
    story_minutes = 0.0
    for marker, minutes in TIME_MARKERS.items():
        count = content.count(marker)
        story_minutes += count * minutes

    # Reading time: char count / 400 chars-per-min → seconds
    clean = content.replace(" ", "").replace("\n", "")
    chars = len(clean)
    reading_seconds = round(chars / 400 * 60)

    # Time stretch ratio: story_minutes : reading_minutes
    if reading_seconds > 0:
        time_stretch_ratio = round(story_minutes / (reading_seconds / 60), 2)
    else:
        time_stretch_ratio = 0.0

    if time_stretch_ratio > 10:
        assessment = "高度压缩——故事时间远大于阅读时间（跳跃式叙事）"
    elif time_stretch_ratio > 1:
        assessment = "适度拉伸——故事时间与阅读时间接近，场景描写较充分"
    elif time_stretch_ratio > 0.1:
        assessment = "实时叙事——阅读时间接近故事时间，接近'实时'体验"
    else:
        assessment = "时间膨胀——大量描写/内心活动，阅读时间远超故事时间"

    return {
        "story_minutes": round(story_minutes, 1),
        "reading_seconds": reading_seconds,
        "time_stretch_ratio": time_stretch_ratio,
        "assessment": assessment,
        "chapter": chapter,
    }


# --- 3. Attention Agent (§67) ---
@router.get("/api/novels/{novel_id}/attention-curve")
def attention_curve(novel_id: str, chapter: int) -> dict:
    """Model reader attention across a chapter in 200-char windows."""
    ch = db.get_chapter(novel_id, chapter)
    if not ch:
        raise HTTPException(404)
    content = ch.get("content", "") or ""

    if not content:
        return {"curve": [], "min_attention": 0, "recovery_points": 0, "chapter": chapter}

    window_size = 200
    attention = 100.0
    curve: list[dict] = []
    recovery_points = 0
    min_attention = 100.0

    for i in range(0, len(content), window_size):
        window = content[i:i + window_size]
        has_hook = any(hook in window for hook in ATTENTION_HOOKS)

        if has_hook:
            attention = 90.0
            recovery_points += 1
        else:
            attention = max(10.0, attention - 15.0)

        curve.append({
            "char_position": i,
            "attention_level": round(attention, 1),
        })
        min_attention = min(min_attention, attention)

    return {
        "curve": curve,
        "min_attention": round(min_attention, 1),
        "recovery_points": recovery_points,
        "chapter": chapter,
        "total_windows": len(curve),
    }


# --- 4. Expectation Management Agent (§69) ---
@router.get("/api/novels/{novel_id}/expectation-check")
def expectation_check(novel_id: str) -> dict:
    """Check genre contract compliance — what readers expect in first 3 chapters."""
    novel = db.get_novel(novel_id)
    if not novel:
        raise HTTPException(404)

    genre = novel.get("genre", "") or ""
    expected = GENRE_CONTRACT.get(genre, GENRE_CONTRACT_DEFAULT)

    chapters = novel.get("chapters", [])[:3]
    all_text_parts: list[str] = []
    for ch in chapters:
        c = db.get_chapter(novel_id, ch["number"])
        if c and c.get("content"):
            all_text_parts.append(c["content"])
    all_text = " ".join(all_text_parts)
    if not all_text.strip():
        all_text = novel.get("synopsis", "") or ""

    found = [elem for elem in expected if elem in all_text]
    missing = [elem for elem in expected if elem not in all_text]
    fulfillment_pct = round(len(found) / max(1, len(expected)) * 100)

    if fulfillment_pct >= 80:
        contract_status = "fulfilled"
    elif fulfillment_pct >= 50:
        contract_status = "partial"
    else:
        contract_status = "breached"

    return {
        "genre": genre,
        "expected_elements": expected,
        "found_elements": found,
        "missing_elements": missing,
        "fulfillment_pct": fulfillment_pct,
        "contract_status": contract_status,
    }


# --- 5. Touch Agent (§37) ---
@router.post("/api/text/touch-analysis")
def touch_analysis(data: dict) -> dict:
    """Analyze what memory (sensory) channels a text opens."""
    text = data.get("text", "")
    if not text:
        raise HTTPException(400, "text is required")

    channels: list[dict] = []

    warmth_count = sum(text.count(s) for s in WARMTH_SIGNALS)
    channels.append({"name": "温暖", "strength": min(100, warmth_count * 15)})

    care_count = sum(text.count(s) for s in CARE_SIGNALS)
    channels.append({"name": "关怀", "strength": min(100, care_count * 10)})

    pain_count = sum(text.count(s) for s in PAIN_SIGNALS)
    channels.append({"name": "疼痛", "strength": min(100, pain_count * 10)})

    dominant = max(channels, key=lambda c: c["strength"])

    if dominant["strength"] < 20:
        assessment = "文字距离较远，感官通道未充分打开——建议增加触觉细节"
    elif dominant["name"] == "疼痛":
        assessment = "疼痛通道主导——文字有强烈的身体感，读者易被卷入"
    elif dominant["name"] == "温暖":
        assessment = "温暖通道主导——营造安全/治愈氛围"
    else:
        assessment = "关怀通道主导——角色间的互动感强烈"

    return {
        "channels": channels,
        "dominant_channel": dominant["name"],
        "assessment": assessment,
    }


# --- 6. Negative Space Agent (§32) ---
@router.post("/api/text/negative-space")
def negative_space(data: dict) -> dict:
    """Estimate what the reader fills in — unsaid / implied content."""
    text = data.get("text", "")
    if not text:
        raise HTTPException(400, "text is required")

    # Split into sentences
    sentences = re.split(r'[。！？；\n]', text)
    sentences = [s.strip() for s in sentences if s.strip()]
    total_sentences = len(sentences)

    if total_sentences == 0:
        return {
            "gap_count": 0, "gap_density": 0, "optimal_zone": "under",
            "breakdown": {"action_gaps": 0, "emotional_gaps": 0, "info_gaps": 0},
            "total_sentences": 0,
        }

    # Action gaps: 3+ action verbs in one sentence = skipped intermediate steps
    action_pattern = re.compile(
        r'[打走跑跳拿放推拉开关杀砍刺射拔穿脱吃喝说喊叫哭笑坐站躺跪爬飞落升降进出]'
    )
    action_gaps = 0
    for s in sentences:
        if len(action_pattern.findall(s)) >= 3:
            action_gaps += 1

    # Emotional gaps: action present but no emotion label
    emotion_words = [
        "喜", "怒", "哀", "乐", "悲", "恐", "惊", "忧", "愁", "恨",
        "高兴", "难过", "愤怒", "害怕", "紧张", "兴奋", "失望", "感动",
        "幸福", "痛苦", "焦虑", "恐惧", "开心", "伤心",
    ]
    emotion_gaps = 0
    for s in sentences:
        has_action = bool(action_pattern.search(s))
        has_emotion = any(ew in s for ew in emotion_words)
        if has_action and not has_emotion:
            emotion_gaps += 1

    # Info gaps: sentences ending with ? minus answer signals
    question_count = sum(1 for s in sentences if s.endswith("？"))
    answer_signals = ["因为", "所以", "于是", "原来", "其实", "结果"]
    answer_count = sum(text.count(a) for a in answer_signals)
    info_gaps = max(0, question_count - answer_count)

    total_gaps = action_gaps + emotion_gaps + info_gaps
    gap_density = round(total_gaps / total_sentences, 2)

    if gap_density < 0.1:
        optimal_zone = "under"
    elif gap_density > 0.5:
        optimal_zone = "over"
    else:
        optimal_zone = "optimal"

    return {
        "gap_count": total_gaps,
        "gap_density": gap_density,
        "optimal_zone": optimal_zone,
        "breakdown": {
            "action_gaps": action_gaps,
            "emotional_gaps": emotion_gaps,
            "info_gaps": info_gaps,
        },
        "total_sentences": total_sentences,
    }


# --- 7. Negative Space Consumption (§72) ---
@router.get("/api/novels/{novel_id}/neg-space-health")
def neg_space_health(novel_id: str) -> dict:
    """Check if later chapters 'consume' negative space created earlier."""
    novel = db.get_novel(novel_id)
    if not novel:
        raise HTTPException(404)

    chapters = novel.get("chapters", [])

    if len(chapters) < 2:
        return {
            "intact_spaces": 0,
            "consumed_spaces": 0,
            "health": "healthy",
            "total_chapters": len(chapters),
            "note": "章节不足，无法判断",
        }

    mystery_signals = [
        "？", "神秘", "未知", "秘密", "谜", "不为人知", "隐藏", "到底", "究竟",
        "为何", "为什么", "是谁", "什么东西", "怎么回事",
    ]
    reveal_signals = [
        "原来", "真相", "其实", "揭秘", "答案", "原因是", "真相是", "竟然是",
    ]

    # Count mysteries in first 3 chapters
    early_chapters = chapters[:3]
    early_text_parts: list[str] = []
    for ch in early_chapters:
        c = db.get_chapter(novel_id, ch["number"])
        if c and c.get("content"):
            early_text_parts.append(c["content"])
    early_text = " ".join(early_text_parts)
    mystery_count = sum(1 for sig in mystery_signals if sig in early_text)

    # Count reveals in later chapters
    later_chapters = chapters[3:]
    later_text_parts: list[str] = []
    for ch in later_chapters:
        c = db.get_chapter(novel_id, ch["number"])
        if c and c.get("content"):
            later_text_parts.append(c["content"])
    later_text = " ".join(later_text_parts)
    reveal_count = sum(1 for sig in reveal_signals if sig in later_text)

    intact_spaces = max(0, mystery_count - reveal_count)
    consumed_spaces = min(mystery_count, reveal_count)

    # Health: if too many spaces consumed without new ones, it's depleting
    if mystery_count > 0 and consumed_spaces >= mystery_count * 0.7:
        health = "depleting"
    else:
        health = "healthy"

    return {
        "intact_spaces": intact_spaces,
        "consumed_spaces": consumed_spaces,
        "health": health,
        "total_chapters": len(chapters),
    }


@router.get("/api/novels/{novel_id}/agent-report")
def agent_report(novel_id: str) -> dict:
    """Return all agent results from the last pipeline run for this novel.

    Returns {agent_name: result_dict} for all 14 agents.
    """
    if not db.get_novel(novel_id):
        raise HTTPException(404, "Novel not found")
    memos = _agent_memos.get(novel_id, {})
    return {
        "novel_id": novel_id,
        "agent_count": len(memos),
        "agents": memos,
    }


@router.post("/api/novels/{novel_id}/seed-bible")
def seed_bible_from_existing(novel_id: str) -> dict:
    """Populate story_bible from existing chapters + character definitions. No LLM needed."""
    novel = db.get_novel(novel_id)
    if not novel: raise HTTPException(404)
    gen_chapters = [c for c in (novel.get('chapters') or []) if c.get('word_count', 0) > 0]
    if not gen_chapters: return {"status": "no_content"}
    static_chars = novel.get('characters', [])
    seeded = {"chars": 0, "tl": 0, "loc": 0}
    for ch in gen_chapters:
        cn = ch['number']
        for sc in static_chars:
            if not sc.get('name'): continue
            exists = [c for c in db.get_character_state(novel_id, cn) if c['char_name'] == sc['name']]
            if not exists:
                try:
                    db.save_character_state(novel_id, cn, sc['name'], emotion='未知',
                        physical_state=sc.get('status','健康'), goal='未知', location='未知')
                    seeded["chars"] += 1
                except: pass
        db.save_timeline_event(novel_id, cn, absolute_time=f"第{cn}章",
            relative_time="未知", event_summary=(ch.get('summary') or ch.get('title',''))[:100])
        seeded["tl"] += 1
    return {"status": "seeded", "seeded": seeded, "chapters": len(gen_chapters)}


@router.post("/api/seed-all-bibles")
def seed_all_bibles() -> dict:
    """Seed story bible for all novels with generated chapters."""
    novels = db.list_novels()
    results = {}
    for n in novels:
        if n.get("total_chapters", 0) > 0:
            try:
                r = seed_bible_from_existing(n["id"])
                results[n["id"]] = r.get("seeded", {})
            except Exception as e:
                results[n["id"]] = {"error": str(e)[:100]}
    return {"seeded": len(results), "results": results}


@router.get("/api/novels/{novel_id}/preview-constraints")
def preview_constraints(novel_id: str, level: str = "L1") -> dict:
    """Preview constraints that will be injected into next chapter generation."""
    if not db.get_novel(novel_id): raise HTTPException(404)
    from ..stations.novel.constraint_builder import ConstraintBuilder
    from ..stations.novel.constraint_compressor import ConstraintCompressor
    novel = db.get_novel(novel_id)
    next_ch = (novel.get("total_chapters") or 0) + 1

    builder = ConstraintBuilder()
    compressor = ConstraintCompressor()
    result = builder.run({"novel_id": novel_id, "chapter_num": next_ch, "db": db})
    all_levels = compressor.generate_all_levels(result)

    return {
        "next_chapter": next_ch,
        "hard_count": result["hard_count"],
        "soft_count": result["soft_count"],
        "selected_level": level,
        "preview": all_levels[level]["text"][:500],
        "all_levels": {l: {"chars": a["char_count"], "lines": a["line_count"]} for l, a in all_levels.items()},
    }


@router.get("/api/novels/{novel_id}/test-constraints")
def test_constraint_compression(novel_id: str) -> dict:
    """A/B test: compare all 4 constraint compression levels."""
    if not db.get_novel(novel_id): raise HTTPException(404)
    from ..stations.novel.compression_tester import CompressionTester
    tester = CompressionTester(db)
    novel = db.get_novel(novel_id)
    next_ch = (novel.get("total_chapters") or 0) + 1
    return tester.test_novel(novel_id, next_ch)


@router.get("/api/test-all-constraints")
def test_all_constraints() -> dict:
    """A/B test constraint compression across all novels."""
    from ..stations.novel.compression_tester import CompressionTester
    tester = CompressionTester(db)
    return tester.test_all_novels()


@router.get("/api/novels/{novel_id}/quality-gate")
def get_quality_gate(novel_id: str) -> dict:
    """Brain Agent quality gate for the latest chapter."""
    if not db.get_novel(novel_id): raise HTTPException(404)
    brain = BrainAgent(db)
    report = brain.get_quality_report(novel_id)
    # Determine gate
    errors = report.get("errors", 0)
    if errors >= 3:
        gate = "🔴 需修复"
    elif errors >= 1 or report.get("warnings", 0) >= 3:
        gate = "⚠️ 注意"
    else:
        gate = "✅ 良好"
    return {"gate": gate, **report}




@router.post("/api/novels/{novel_id}/chapters/{chapter_num}/polish-reverse")
def reverse_polish(novel_id: str, chapter_num: int) -> dict:
    """克制编辑：删除冗余词句，只删不加。"""
    ch = db.get_chapter(novel_id, chapter_num)
    if not ch or not ch.get("content"):
        raise HTTPException(400, "No content")

    try:
        from ..config import Config
        from ..generator import Generator
        provider = _get_provider(novel_id)
        models = provider.get("models", ["deepseek-v4-pro"])
        model = "deepseek-v4-pro" if "deepseek-v4-pro" in str(models) else models[0]
        cfg = Config(openai_api_key=provider.get("api_key",""), openai_base_url=provider.get("base_url",""),
                     model=model)
        gen = Generator(cfg)

        prompt = f"""以下是小说正文。你的任务是删减——只删不加，不改写。

删减规则（严格按顺序）：
1. 删掉所有「突然」「竟然」「似乎」「有些」「其实」「不由得」「仿佛」
2. 删掉所有解释情绪的句子（让动作和对话自己说话）
3. 如果上一段已经暗示的信息，下一段不要再明说——删掉重复的
4. 删掉所有「说道」「问道」「答道」中的「道」——改成「说」「问」「答」
5. 删掉所有不必要的「的」「地」「得」
6. 如果删完某段不足原来一半字数——那段不需要删，恢复原样

直接返回删减后的全文。不要加任何解释。

原文：
{ch['content'][:4000]}
"""
        messages = [{"role": "user", "content": prompt}]
        result = gen._call_llm_with_retry(messages, max_tokens=4096)
        if not result:
            raise HTTPException(500, "LLM returned empty")

        return {"polished": result, "original_length": len(ch['content']), "polished_length": len(result)}
    except Exception as e:
        raise HTTPException(500, str(e)[:200])


# ═══════════════ Foreshadowing Management ═══════════════

@router.get("/api/novels/{novel_id}/foreshadowing/all")
def get_all_foreshadowing(novel_id: str) -> dict:
    """Get all foreshadowing (active + resolved + overdue)."""
    if not db.get_novel(novel_id): raise HTTPException(404)
    with db.conn() as c:
        rows = c.execute("SELECT * FROM foreshadowing_tracker WHERE novel_id=? ORDER BY created_chapter",
            (novel_id,)).fetchall()
        return {"items": [dict(r) for r in rows]}


@router.post("/api/novels/{novel_id}/foreshadowing/{fs_id}/resolve")
def resolve_foreshadowing(novel_id: str, fs_id: int, data: dict) -> dict:
    """Mark foreshadowing as resolved."""
    chapter_num = data.get("chapter_num", 0)
    text = data.get("text", "")
    db.resolve_foreshadowing(fs_id, chapter_num, text)
    return {"ok": True}


@router.post("/api/novels/{novel_id}/foreshadowing")
def add_foreshadowing_manual(novel_id: str, data: dict) -> dict:
    """Manually add foreshadowing."""
    desc = (data.get("description") or "").strip()
    if not desc: raise HTTPException(400, "Description required")
    ch = data.get("chapter", 0)
    hint = data.get("hint", "")
    due = data.get("due_by")
    db.save_foreshadowing(novel_id, int(ch), desc, hint, int(due) if due else None)
    return {"ok": True}


# ═══════════════ Voice Profile API ═══════════════


@router.get("/api/novels/{novel_id}/cost-ledger")
def get_cost_ledger(novel_id: str) -> dict:
    if not db.get_novel(novel_id): raise HTTPException(404)
    entries = db.get_cost_ledger(novel_id)
    # Compute balance
    total_gains = len([e for e in entries if e.get('gain')])
    total_losses = len([e for e in entries if e.get('loss')])
    return {
        "entries": entries,
        "summary": {
            "total_gains": total_gains,
            "total_losses": total_losses,
            "balance": total_gains - total_losses,
            "status": "balanced" if abs(total_gains - total_losses) <= 2 else ("surplus" if total_gains > total_losses else "deficit"),
        }
    }


@router.post("/api/novels/{novel_id}/consistency/{issue_id}/fix")
def mark_consistency_fixed(novel_id: str, issue_id: int) -> dict:
    db.mark_consistency_fixed(issue_id)
    return {"ok": True}


# ═══════════════ Agent Engine: Editor Review + Targeted Rewrite ═══════════════

def _editor_review(novel_id: str, chapter_num: int, content: str, quality_issues: list[str] | None = None) -> dict:
    """Editor Agent: review chapter and give line-specific feedback (§4, §8)."""
    try:
        from ..config import Config
        from ..generator import Generator
        provider = _get_provider(novel_id)
        models = provider.get("models", ["deepseek-v4-pro"])
        model = "deepseek-v4-pro" if "deepseek-v4-pro" in str(models) else models[0]
        cfg = Config(openai_api_key=provider.get("api_key",""), openai_base_url=provider.get("base_url",""),
                     model=model)
        gen = Generator(cfg)

        # Gather bible context for editor
        chars = db.get_character_state(novel_id, chapter_num - 1) if chapter_num > 1 else []
        char_context = "\n".join(f"- {c['char_name']}: 情绪={c.get('emotion','?')}, 身体={c.get('physical_state','?')}, 位置={c.get('location','?')}"
            for c in chars[:5]) if chars else "无历史数据"

        foreshadowing = db.get_active_foreshadowing(novel_id)
        fs_context = "\n".join(f"- #{f['id']}: {f['description'][:60]} (Ch{f['created_chapter']}, 到期Ch{f.get('due_by_chapter','?')})"
            for f in foreshadowing[:5]) if foreshadowing else "无活跃伏笔"

        issues_text = "\n".join(f"- {i}" for i in (quality_issues or [])) if quality_issues else "无"

        prompt = f"""你是小说编辑。审读以下章节，给出具体的、可操作的修改意见。

# 角色状态（上一章）
{char_context}

# 活跃伏笔（需在本章或近期回收）
{fs_context}

# 质量评审发现的问题
{issues_text}

# 待审章节正文（前3000字）
{content[:3000]}

# 你的任务
给出具体的、定位到问题句子的修改意见。格式：
第X段第Y句：「原文」——> 问题：XXX ——> 建议：XXX

只指出最重要的3-5个问题。不要泛泛而谈。每个问题必须精确到一个具体句子。
不要打分。不要说"整体不错"。只说问题。
"""
        messages = [{"role": "user", "content": prompt}]
        result = gen._call_llm_with_retry(messages, max_tokens=1024)
        return {"feedback": result or "", "model": model}
    except Exception as e:
        return {"feedback": "", "error": str(e)[:100]}


def _targeted_rewrite(novel_id: str, chapter_num: int, content: str, editor_feedback: str) -> str:
    """Writer Agent: rewrite chapter based on editor's specific feedback."""
    if not editor_feedback:
        return content

    try:
        from ..config import Config
        from ..generator import Generator
        provider = _get_provider(novel_id)
        models = provider.get("models", ["deepseek-v4-pro"])
        model = "deepseek-v4-pro" if "deepseek-v4-pro" in str(models) else models[0]
        cfg = Config(openai_api_key=provider.get("api_key",""), openai_base_url=provider.get("base_url",""),
                     model=model)
        gen = Generator(cfg)

        prompt = f"""你是小说作者。编辑给了以下修改意见。请根据意见修改原文。

# 编辑意见
{editor_feedback}

# 原文
{content[:4000]}

# 规则
1. 只修改编辑指出的问题句子。不要重写整章。
2. 保持原有风格、角色声音、情节走向不变。
3. 修改后直接返回全文。不要解释修改了什么。
"""
        messages = [{"role": "user", "content": prompt}]
        result = gen._call_llm_with_retry(messages, max_tokens=4096)
        return result if result and len(result) > len(content) * 0.5 else content
    except Exception:
        return content


# ═══════════════ Agent Engine: Contrastive Generation (§18) ═══════════════

def _contrastive_generate(gen, state, rag_context, outline, style, author_input=""):
    """Generate 2 versions with different constraints, pick the less template-like one."""
    import re

    # Version A: standard generation
    chapter_a, quality_a = gen.batch_generate(state, n=1, rag_context=rag_context, outline=outline, style=style,
                                               author_input=author_input)
    body_a = chapter_a.content or chapter_a.summary

    # Version B: constraint-injected (forbidden words, sentence length limits)
    constraint_input = (author_input + "\n\n【约束】不要使用以下词汇：突然、竟然、似乎、仿佛、不由得、只见、谁知。每段不超过5句。对话每轮不超过3句。") if author_input else "【约束】不要使用：突然、竟然、似乎、仿佛。"
    chapter_b, quality_b = gen.batch_generate(state, n=1, rag_context=rag_context, outline=outline, style=style,
                                               author_input=constraint_input)
    body_b = chapter_b.content or chapter_b.summary

    # Score deviation: count forbidden words as penalty, count unique sentence starters as bonus
    def deviation_score(text):
        forbidden = ['突然', '竟然', '似乎', '仿佛', '不由得', '只见', '谁知', '缓缓', '微微', '轻轻']
        penalty = sum(text.count(w) for w in forbidden)
        # Count unique sentence starters (first 2 chars of each sentence)
        sentences = re.split(r'[。！？]', text)
        starters = set(s[:3] for s in sentences if len(s) >= 3)
        bonus = len(starters)
        return bonus - penalty * 2

    score_a = deviation_score(body_a)
    score_b = deviation_score(body_b)

    print(f"[CONTRAST] Score A={score_a} Q={quality_a['overall']} | Score B={score_b} Q={quality_b['overall']}")

    # Pick the version with higher deviation score, fallback to quality
    if score_b > score_a + 5:
        return chapter_b, quality_b
    elif quality_b['overall'] > quality_a['overall'] + 0.05:
        return chapter_b, quality_b
    return chapter_a, quality_a


# ═══════════════ Constraint Collapse Engine (§42) ═══════════════

@router.post("/api/novels/{novel_id}/constraint-collapse")
def constraint_collapse(novel_id: str, data: dict) -> dict:
    """
    Given a scene with multiple possible choices, apply 4 rounds of constraints
    to narrow down to the inevitable choice (§42).
    
    Input: {scene_description, choices: ["choice A", "choice B", ...]}
    Output: {survivors: [...], eliminated: [{choice, reason, round}]}
    """
    scene = (data.get("scene_description") or data.get("scene") or "").strip()
    choices = data.get("choices", [])
    if not scene or len(choices) < 2:
        raise HTTPException(400, "Need scene_description and at least 2 choices")

    eliminated = []
    survivors = list(choices)

    # Round 1: Hard constraints (story bible)
    chars = db.get_character_state(novel_id)
    char_names = list(set(c['char_name'] for c in chars[-10:]))
    active_fs = db.get_active_foreshadowing(novel_id)

    for choice in list(survivors):
        # Check if any character is in a state that makes this impossible
        for c in chars[-5:]:
            if c.get('physical_state') == 'injured' and ('战斗' in choice or '打' in choice or '杀' in choice):
                if c['char_name'] in choice:
                    eliminated.append({"choice": choice, "reason": f"{c['char_name']}受伤，无法执行需要体力的选择", "round": 1})
                    survivors.remove(choice)
                    break

    # Round 2: Character constraints (voice)
    if survivors and len(survivors) > 1:
        for choice in list(survivors):
            # If choice contradicts known character traits (simplistic check)
            if '原谅' in choice and any('愤怒' in (c.get('emotion') or '') for c in chars[-3:]):
                eliminated.append({"choice": choice, "reason": "角色当前情绪为愤怒，不宜立即原谅", "round": 2})
                survivors.remove(choice)

    # Round 3: Structure constraints (foreshadowing + pacing)
    if survivors and len(survivors) > 1 and active_fs:
        overdue = [f for f in active_fs if f.get('status') == 'overdue']
        if overdue:
            for choice in list(survivors):
                if not any(f['description'][:10] in choice for f in overdue):
                    eliminated.append({"choice": choice, "reason": f"有{len(overdue)}个过期伏笔未收，该选择未涉及回收", "round": 3})
                    survivors.remove(choice)

    # Round 4: Theme constraint (冰山)
    if survivors and len(survivors) > 1:
        unsaid = db.get_unsaid(novel_id)
        if unsaid:
            # Prefer choices that leave the unsaid truths untouched
            for choice in list(survivors):
                if any(u['entry'][:10] in choice for u in unsaid[-3:]):
                    eliminated.append({"choice": choice, "reason": "该选择可能过早揭示隐藏真相", "round": 4})
                    survivors.remove(choice)

    return {
        "original_choices": len(choices),
        "survivors": survivors,
        "eliminated": eliminated,
        "is_collapsed": len(survivors) == 1,
        "recommendation": survivors[0] if len(survivors) == 1 else (
            "多个选择存活，需要人类判断" if survivors else "所有选择被淘汰，放宽约束或重新定义场景"
        ),
    }


# ═══════════════ Counterpoint Agent (§16) + Memory Decay Agent (§44) ═══════════════

@router.get("/api/novels/{novel_id}/counterpoint")
def get_counterpoint(novel_id: str) -> dict:
    """Track multiple storylines and their relative speed (§16)."""
    if not db.get_novel(novel_id): raise HTTPException(404)
    chars = db.get_character_state(novel_id)
    foreshadowing = db.get_active_foreshadowing(novel_id)
    timeline = db.get_timeline(novel_id)
    costs = db.get_cost_ledger(novel_id)

    # Line A: Plot (chapters with revealed info vs total)
    total_chs = len(timeline)
    plot_progress = min(100, total_chs * 5) if total_chs else 0

    # Line B: Relationships (characters with emotion changes)
    rel_chapters = set(c['chapter_num'] for c in chars if c.get('emotion'))
    rel_speed = len(rel_chapters) / max(1, total_chs) if total_chs else 0

    # Line C: Theme (cost ledger entries = theme manifesting)
    theme_speed = len(costs) / max(1, total_chs) if total_chs else 0

    # Line D: Secrets (active foreshadowing = unrevealed secrets)
    secret_speed = len(foreshadowing) / max(1, total_chs) if total_chs else 0

    lines = [
        {"name": "情节线", "id": "plot", "speed": plot_progress, "status": "正常" if 20 < plot_progress < 80 else ("缓慢" if plot_progress <= 20 else "过速")},
        {"name": "关系线", "id": "rel", "speed": round(rel_speed * 100), "status": "正常" if 0.2 < rel_speed < 0.8 else ("滞后" if rel_speed <= 0.2 else "过密")},
        {"name": "主题线", "id": "theme", "speed": round(theme_speed * 100), "status": "正常" if theme_speed > 0 else "未激活"},
        {"name": "秘密线", "id": "secret", "speed": len(foreshadowing), "status": "正常" if 1 <= len(foreshadowing) <= 5 else ("过载" if len(foreshadowing) > 5 else "枯竭")},
    ]

    # Detect lagging lines
    lagging = [l for l in lines if l['status'] in ('滞后', '缓慢', '未激活', '枯竭')]
    suggestion = ""
    if lagging:
        suggestion = f"{lagging[0]['name']}滞后——建议下章推进此线"
    elif any(l['status'] == '过密' for l in lines):
        suggestion = "关系线过密——建议暂缓感情戏"
    else:
        suggestion = "各线均衡，可自由推进"

    return {"lines": lines, "lagging": [l['name'] for l in lagging], "suggestion": suggestion}


def _memory_decay_check(novel_id: str, chapter_num: int, content: str) -> list[dict]:
    """Check if character memories in this chapter are too accurate (§44)."""
    issues: list[dict[str, str]] = []
    try:
        # Look for recall patterns: "记得" "想起" "那天" "当时"
        import re
        recall_patterns = re.findall(r'(记得|想起|那天|当时|那时候|那晚).{5,50}', content)
        if not recall_patterns:
            return issues

        # Get original events from earlier chapters
        chars = db.get_character_state(novel_id)
        for i, recall in enumerate(recall_patterns[:5]):
            for c in chars:
                if c['char_name'] and c['char_name'] in recall:
                    # Check if recall has exact detail that a character wouldn't remember
                    if len(re.findall(r'[一-鿿]', recall)) > 20:
                        issues.append({
                            "type": "memory_decay",
                            "recall": recall[:80],
                            "character": c['char_name'],
                            "suggestion": "回忆太过精确——真正记忆会歪曲细节。考虑将听觉记忆换为视觉或模糊处理",
                        })
                    break
    except Exception:
        pass
    return issues


# ═══════════════ Agent Pipeline Orchestration (§4) ═══════════════

def _agent_editor_in_chief(novel_id: str, chapter_num: int) -> str:
    """总编 Agent: reads bible → writes chapter brief (§4.1)."""
    try:
        from ..config import Config
        from ..generator import Generator
        provider = _get_provider(novel_id)
        models = provider.get("models", ["deepseek-v4-pro"])
        model = "deepseek-v4-pro" if "deepseek-v4-pro" in str(models) else models[0]
        cfg = Config(openai_api_key=provider.get("api_key",""), openai_base_url=provider.get("base_url",""), model=model)
        gen = Generator(cfg)

        chars = db.get_character_state(novel_id)
        fs = db.get_active_foreshadowing(novel_id)
        unsaid = db.get_unsaid(novel_id)
        costs = db.get_cost_ledger(novel_id)
        reader = db.get_character_state(novel_id, chapter_num - 1) if chapter_num > 1 else []

        char_lines = "\n".join(f"- {c['char_name']}: 情绪={c.get('emotion','?')}, 身体={c.get('physical_state','?')}, 目标={c.get('goal','?')}" for c in chars[-5:]) if chars else "首章"
        fs_lines = "\n".join(f"- #{f['id']}: {f['description'][:60]} (到期Ch{f.get('due_by_chapter','?')})" for f in fs[:5]) if fs else "无活跃伏笔"
        unsaid_lines = "\n".join(f"- 🔒 {e['entry'][:80]}" for e in unsaid[-5:]) if unsaid else "无"
        cost_lines = "\n".join(f"- {e.get('character_name','?')}: +{e.get('gain','')} / -{e.get('loss','')}" for e in costs[-3:]) if costs else "无"

        prompt = f"""你是小说总编。根据以下信息，为第{chapter_num}章写一份简报（不超过300字）。
不要写正文。只写要求。

【当前角色状态】
{char_lines}

【活跃伏笔】
{fs_lines}

【隐藏真相（不能说）】
{unsaid_lines}

【近期代价】
{cost_lines}

【简报要求】
1. 本章需要推进什么情节？（1-2句）
2. 本章必须出现的角色和他们的情感状态
3. 本章必须回收的伏笔（如果有）
4. 本章的主题约束（代价必须被支付）
5. 本章的节奏（快/慢/中）

直接输出简报，不要编号。像在跟作者说话一样写。
"""
        messages = [{"role": "user", "content": prompt}]
        result = gen._call_llm_with_retry(messages, max_tokens=512)
        return result or ""
    except Exception as e:
        print(f"[AGENT-EIC] Failed: {e}")
        return ""


def _agent_architect(novel_id: str, chapter_num: int, brief: str) -> str:
    """结构师 Agent: brief → chapter outline (§4.2)."""
    if not brief:
        return ""

    try:
        from ..config import Config
        from ..generator import Generator
        provider = _get_provider(novel_id)
        models = provider.get("models", ["deepseek-v4-pro"])
        model = "deepseek-v4-pro" if "deepseek-v4-pro" in str(models) else models[0]
        cfg = Config(openai_api_key=provider.get("api_key",""), openai_base_url=provider.get("base_url",""), model=model)
        gen = Generator(cfg)

        prompt = f"""你是小说结构师。根据总编的简报，为第{chapter_num}章设计大纲。

【总编简报】
{brief}

【输出格式】
开场（1-2句，地点+人物+初始状态）
发展（2-3个情节点）
转折（1个关键的转折或揭示）
结尾（钩子，1-2句）

每个情节点包含：类型（开场/冲突/发现/转折/结尾）、涉及角色、地点、要传达的情感。
直接输出大纲，不要编号。简洁即可。
"""
        messages = [{"role": "user", "content": prompt}]
        result = gen._call_llm_with_retry(messages, max_tokens=512)
        return result or ""
    except Exception as e:
        print(f"[AGENT-ARCH] Failed: {e}")
        return ""


def _agent_fact_checker(novel_id: str, chapter_num: int, content: str) -> list[str]:
    """事实核查 Agent: draft + bible → contradiction report (§4.4)."""
    issues = []
    try:
        prev_chars = db.get_character_state(novel_id, chapter_num - 1) if chapter_num > 1 else []
        prev_map = {c['char_name']: c for c in prev_chars}

        for char_name, prev in prev_map.items():
            if prev.get('physical_state') == 'injured' and '双手' in content and char_name in content:
                issues.append(f"🔴 {char_name}上章受伤但本章使用双手——矛盾")
            if prev.get('goal') and prev['goal'] not in content[:1000]:
                issues.append(f"🟡 {char_name}的目标「{prev['goal']}」未在本章体现")

        fs = db.get_active_foreshadowing(novel_id)
        for f in fs:
            if f.get('status') == 'overdue':
                issues.append(f"🔴 伏笔#{f['id']}「{f['description'][:40]}」过期未收")
    except Exception:
        pass
    return issues


# ═══════════════ Agent Pipeline (V12) — 14 Non-blocking Analysis Agents ═══════════════

def _agent_narrative_distance(novel_id: str, chapter_num: int, content: str) -> dict:
    """Compute narrative distance (close/medium/far) and store as memo (§22)."""
    try:
        # Heuristic: count sensory words (close) vs summary words (far)
        close_words = len(re.findall(r'感觉|闻到|听到|触摸|指甲|心跳|呼吸|颤抖|刺痛', content))
        far_words = len(re.findall(r'后来|从此|多年|据说|传说|曾经|据说|那年', content))
        total_avg = close_words + far_words
        if total_avg == 0:
            ratio = 0.5
        else:
            ratio = close_words / total_avg

        if ratio > 0.6:
            distance = "close"
        elif ratio < 0.4:
            distance = "far"
        else:
            distance = "medium"

        result = {
            "distance": distance,
            "close_signals": close_words,
            "far_signals": far_words,
            "ratio": round(ratio, 2),
            "chapter": chapter_num,
        }
        db.log(novel_id, "agent.narrative_distance", result)
        return result
    except Exception as e:
        return {"error": str(e)}


def _agent_pov_shifts(novel_id: str, chapter_num: int, content: str) -> dict:
    """Track POV shifts — count and flag rapid changes (§54)."""
    try:
        # Detect POV marker words
        pov_markers = re.findall(
            r'(?:他|她|我|它)(?:心想|暗想|寻思|感到|觉得|意识到|注意到|发现|看见|听见)',
            content
        )
        # Count POV carriers
        carriers = set()
        for m in pov_markers:
            if m[0] in ('他', '她', '它'):
                carriers.add(m[0])
            elif m[0] == '我':
                carriers.add('我')

        # Heuristic: paragraphs starting with different character names = POV shifts
        paragraphs = [p.strip() for p in content.split('\n') if p.strip()]
        pov_shift_count = 0
        prev_char = None
        for p in paragraphs:
            m = re.match(r'([^，。,.!！?？\s]{1,4})', p)
            if m:
                name = m.group(1)
                if name != prev_char and '说' not in p[:10]:
                    prev_char = name
                    pov_shift_count += 1

        result = {
            "pov_shifts": pov_shift_count,
            "pov_carriers": list(carriers),
            "is_rapid": pov_shift_count > 5,
            "chapter": chapter_num,
        }
        db.log(novel_id, "agent.pov_shifts", result)
        return result
    except Exception as e:
        return {"error": str(e)}


def _agent_narrative_voice(novel_id: str, chapter_num: int, content: str) -> dict:
    """Check narrative voice consistency — sentence length, tone markers (§47)."""
    try:
        sentences = re.split(r'[。!！?？]', content)
        sentences = [s.strip() for s in sentences if s.strip()]
        lengths = [len(s) for s in sentences]

        avg_len = sum(lengths) / len(lengths) if lengths else 0
        short_count = sum(1 for l in lengths if l < 10)
        long_count = sum(1 for l in lengths if l > 50)

        # Tone markers
        exclaim = content.count('！') + content.count('!')
        question = content.count('？') + content.count('?')
        ellipsis = content.count('……') + content.count('...')

        # Previous voice data for comparison
        prev_entries = db.get_character_state(novel_id, chapter_num - 1) if chapter_num > 1 else []

        result = {
            "avg_sentence_len": round(avg_len, 1),
            "short_sentences": short_count,
            "long_sentences": long_count,
            "exclaim": exclaim,
            "question": question,
            "ellipsis": ellipsis,
            "total_sentences": len(sentences),
            "chapter": chapter_num,
        }
        db.log(novel_id, "agent.narrative_voice", result)
        return result
    except Exception as e:
        return {"error": str(e)}


def _agent_pre_understanding(novel_id: str, chapter_num: int, content: str) -> dict:
    """Simulate reader types and what they bring to this chapter (§17)."""
    try:
        # Simulate 3 reader archetypes
        reader_types = {
            "casual": {"pre": "零背景知识进入，只关心爽感", "focus_keywords": ["战斗", "升级", "宝物", "美女", "装逼"]},
            "veteran": {"pre": "记忆前文伏笔的资深读者", "focus_keywords": ["伏笔", "暗线", "因果", "代价", "成长"]},
            "critical": {"pre": "挑剔的编辑/批评者视角", "focus_keywords": ["逻辑", "节奏", "人物弧", "文字", "主题"]},
        }

        results = {}
        for rtype, info in reader_types.items():
            hits = sum(1 for kw in info["focus_keywords"] if kw in content)
            results[rtype] = {
                "pre_state": info["pre"],
                "keyword_hits": hits,
                "satisfaction": "high" if hits >= 3 else "medium" if hits >= 1 else "low",
            }

        result = {
            "reader_types": results,
            "overall_satisfaction": "high" if all(r["satisfaction"] == "high" for r in results.values()) else "mixed",
            "chapter": chapter_num,
        }
        db.log(novel_id, "agent.pre_understanding", result)
        return result
    except Exception as e:
        return {"error": str(e)}


def _agent_midpoint_health(novel_id: str, chapter_num: int, content: str) -> dict:
    """Check midpoint chapter health — stakes, reversals, character stakes (§64)."""
    try:
        novel = db.get_novel(novel_id)
        total_chs = len(novel.get("chapters", []))
        # Only meaningful if this is the midpoint
        is_midpoint = abs(chapter_num - total_chs // 2) <= 2

        # Heuristic midpoint signals
        has_reversal = bool(re.search(r'(?:反转|不料|没想到|却是|竟然|居然)', content))
        has_stakes = bool(re.search(r'(?:代价|失去|风险|危险|生死|命|死)', content))
        has_reveal = bool(re.search(r'(?:真相|秘密|隐瞒|欺骗|真实|原来)', content))

        result = {
            "is_midpoint": is_midpoint,
            "chapter": chapter_num,
            "has_reversal": has_reversal,
            "has_stakes": has_stakes,
            "has_reveal": has_reveal,
            "health_score": (has_reversal + has_stakes + has_reveal) / 3,
        }
        if is_midpoint:
            db.log(novel_id, "agent.midpoint_health", result)
        return result
    except Exception as e:
        return {"error": str(e)}


def _agent_attention_curve(novel_id: str, chapter_num: int, content: str) -> dict:
    """Compute attention curve per chapter — hook density, cliff detection (§67)."""
    try:
        paragraphs = [p.strip() for p in content.split('\n') if len(p.strip()) > 20]
        n = len(paragraphs)

        # Hook density: count tension markers per paragraph segment
        hooks: list[int] = []
        cliff_markers = re.findall(r'(?:突然|忽然|却|但|可|然而|不料|谁知|就在)', content)
        tension_markers = re.findall(r'(?:危险|威胁|杀意|恐惧|死亡|绝望|紧急|来不及)', content)

        segments = max(1, n // 5)
        curve = []
        for i in range(5):
            seg_paras = paragraphs[i * segments:(i + 1) * segments]
            seg_text = ' '.join(seg_paras)
            seg_tension = len(re.findall(r'(?:突然|忽然|却|但|可|然而|不料|谁知|就在|危险|威胁|杀意|恐惧)', seg_text))
            curve.append({"segment": f"{i*20}-{(i+1)*20}%", "tension": seg_tension})

        # Check if chapter ends with a cliff
        last_para = paragraphs[-1] if paragraphs else ""
        is_cliff = bool(re.search(r'(?:未完|待续|突然|忽然|不料|谁知)', last_para[-50:]))

        result = {
            "hook_count": len(cliff_markers),
            "tension_count": len(tension_markers),
            "attention_curve": curve,
            "ends_with_cliff": is_cliff,
            "chapter": chapter_num,
        }
        db.log(novel_id, "agent.attention_curve", result)
        return result
    except Exception as e:
        return {"error": str(e)}


def _agent_expectation_check(novel_id: str, chapter_num: int, content: str) -> dict:
    """Verify genre contract — are we delivering what genre readers expect? (§69)"""
    try:
        novel = db.get_novel(novel_id)
        genre = novel.get("genre", "玄幻")

        # Genre expectations by category
        genre_markers = {
            "玄幻": ["修炼", "突破", "功法", "境界", "灵石", "法宝", "丹药", "飞行", "神识", "机缘"],
            "都市": ["公司", "赚钱", "股票", "总裁", "合同", "谈判", "手机", "都市", "酒吧", "企业"],
            "悬疑": ["线索", "推理", "证据", "嫌疑人", "谋杀", "死亡", "调查", "谜题", "隐藏", "真相"],
            "言情": ["心动", "心跳", "脸红", "牵手", "拥抱", "告白", "甜蜜", "吵架", "吃醋", "思念"],
            "科幻": ["飞船", "星舰", "AI", "虚拟", "基因", "纳米", "量子", "虫洞", "外星", "机器人"],
            "历史": ["皇上", "太后", "宫女", "妃子", "将军", "战争", "朝廷", "进贡", "封号", "赐婚"],
        }

        defaults = genre_markers.get("玄幻", genre_markers["玄幻"])
        expected = genre_markers.get(genre, defaults)

        # Check presence of genre keywords
        hits = [kw for kw in expected if kw in content]
        missing = [kw for kw in expected if kw not in content]

        result = {
            "genre": genre,
            "hits": hits,
            "hit_count": len(hits),
            "missing": missing,
            "contract_score": round(len(hits) / len(expected), 2) if expected else 1.0,
            "is_breach": len(hits) < len(expected) * 0.3,
            "chapter": chapter_num,
        }
        db.log(novel_id, "agent.expectation_check", result)
        return result
    except Exception as e:
        return {"error": str(e)}


def _agent_reverse_reading(novel_id: str, chapter_num: int, content: str) -> dict:
    """Scan old chapters for new meaning revealed by this chapter (§15)."""
    try:
        novel = db.get_novel(novel_id)
        chapters = novel.get("chapters", [])

        # Only scan if we have older chapters
        if chapter_num <= 1:
            return {"retroactive_hints": [], "count": 0, "chapter": chapter_num}

        # Extract key reveals from current chapter (names, objects, events)
        current_keywords = set()
        key_patterns = re.findall(r'(?!但是|然而|因为|所以|如果|虽然)(.{2,4})(?:原来|竟然是|其实是|就是|正是)', content)
        for k in key_patterns:
            if len(k) >= 2:
                current_keywords.add(k.strip())

        # Scan older chapters for these keywords
        retroactive_hints = []
        for ch in chapters[:chapter_num - 1]:
            ch_content = ch.get("content", "")
            if not ch_content:
                continue
            for kw in current_keywords:
                if kw in ch_content and kw not in ('说', '道', '的', '了', '我', '他', '她'):
                    retroactive_hints.append({
                        "chapter": ch.get("number", "?"),
                        "keyword": kw,
                        "snippet": ch_content[max(0, ch_content.index(kw) - 20):ch_content.index(kw) + 30],
                    })

        result = {
            "retroactive_hints": retroactive_hints[:10],  # Cap at 10
            "count": len(retroactive_hints),
            "keywords": list(current_keywords)[:20],
            "chapter": chapter_num,
        }
        db.log(novel_id, "agent.reverse_reading", result)
        return result
    except Exception as e:
        return {"error": str(e)}


def _agent_scream_moments(novel_id: str, chapter_num: int, content: str) -> dict:
    """Find hidden connections — moments that make readers gasp (§24)."""
    try:
        # Scream = unexpected connection between two seemingly unrelated elements
        # Pattern: surprise + revelation + emotional weight
        surprises = re.findall(r'(?:竟然|居然|不料|谁知|原来)(.{5,30}?)(?:[。!！?？])', content)
        reversals = re.findall(r'(?:反转|颠覆|推翻|否定|不是.{2,4}而是)(.{5,30}?)(?:[。!！?？])', content)
        connections = re.findall(r'(?:原来.{2,4}就是|正是.{2,4}|居然是.{2,4})(.{5,30}?)(?:[。!！?？])', content)

        moments = []
        for s in surprises[:3]:
            moments.append({"type": "surprise", "moment": s.strip(), "impact": "reader gasp potential"})
        for r in reversals[:3]:
            moments.append({"type": "reversal", "moment": r.strip(), "impact": "expectation subversion"})
        for c in connections[:3]:
            moments.append({"type": "connection", "moment": c.strip(), "impact": "hidden link revealed"})

        result = {
            "scream_moments": moments,
            "total_potential": len(surprises) + len(reversals) + len(connections),
            "has_major_scream": len(moments) >= 2,
            "chapter": chapter_num,
        }
        db.log(novel_id, "agent.scream_moments", result)
        return result
    except Exception as e:
        return {"error": str(e)}


def _agent_ending_candidates(novel_id: str, chapter_num: int, content: str) -> dict:
    """Track dormant images and their evolution as potential ending material (§35)."""
    try:
        novel = db.get_novel(novel_id)
        chapters = novel.get("chapters", [])

        # Images that often recur and gain meaning: objects, locations, scar/birthmarks, recurring phrases
        image_patterns = re.findall(r'(?:玉佩|戒指|项链|手镯|胎记|疤痕|信物|红绳|铃铛|镜子|日记|钥匙|照片|地图)(.{0,10})', content)

        locations = re.findall(r'(?:老家|故乡|旧址|废墟|旧宅|老宅|庭院|后山|祠堂|密室)(.{0,10})', content)

        phrases = re.findall(r'(.{2,4})总是(?:出现|想起|梦到|浮现|萦绕)', content)

        # Check if any of these appeared in earlier chapters
        recurring = []
        for img in image_patterns[:5]:
            for ch in chapters[:chapter_num - 1]:
                if img in ch.get("content", ""):
                    recurring.append({"image": img, "first_appeared": ch.get("number", "?"), "reappeared": chapter_num})
                    break

        result = {
            "new_images": image_patterns[:10],
            "new_locations": locations[:5],
            "recurring_phrases": phrases[:5],
            "recurring_images": recurring,
            "dormant_potential": len(image_patterns) + len(locations) + len(recurring),
            "chapter": chapter_num,
        }
        db.log(novel_id, "agent.ending_candidates", result)
        return result
    except Exception as e:
        return {"error": str(e)}


def _agent_rituals(novel_id: str, chapter_num: int, content: str) -> dict:
    """Track repeated gestures and behaviors as character rituals (§49)."""
    try:
        novel = db.get_novel(novel_id)
        chapters = novel.get("chapters", [])

        # Repeated gesture patterns
        gestures = re.findall(r'(?:习惯性|总是|每次|照例|一如往常|一如既往|下意识)(.{2,10}?)(?:地|的|了|着)', content)

        # Specific ritual markers
        rituals_found = re.findall(
            r'(?:摩挲|抚摸|把玩|转动|敲击|咬|舔|抿|攥|握|捏|捻|弹)(.{0,5}?)',
            content
        )

        # Check if these gestures appeared in past chapters
        ritual_tracker: dict[str, int] = {}
        for g in gestures[:10]:
            gesture_text = g.strip()
            if len(gesture_text) < 2:
                continue
            ritual_tracker[gesture_text] = ritual_tracker.get(gesture_text, 0) + 1

        for ch in chapters[:chapter_num - 1]:
            ch_content = ch.get("content", "")
            for g in gestures[:10]:
                gesture_text = g.strip()
                if len(gesture_text) >= 2 and gesture_text in ch_content:
                    ritual_tracker[gesture_text] = ritual_tracker.get(gesture_text, 0) + 1

        recurring_rituals = {k: v for k, v in ritual_tracker.items() if v >= 2}

        result = {
            "new_gestures": gestures[:10],
            "ritual_objects": rituals_found[:10],
            "recurring_rituals": recurring_rituals,
            "ritual_count": len(recurring_rituals),
            "chapter": chapter_num,
        }
        db.log(novel_id, "agent.rituals", result)
        return result
    except Exception as e:
        return {"error": str(e)}


def _agent_time_spiral(novel_id: str, chapter_num: int, content: str) -> dict:
    """Compute meaning shifts — how past events change meaning with new information (§76)."""
    try:
        novel = db.get_novel(novel_id)
        chapters = novel.get("chapters", [])

        # Detect flashback or temporal markers
        time_markers = re.findall(
            r'(?:当时|那时|那年|那天|曾经|从前|之前|之后|后来|现在|如今)(.{0,5})',
            content
        )

        # Detect reinterpretation patterns
        reinterpretations = re.findall(
            r'(?:原来.{2,4}不是|其实.{2,4}才是|当初.{2,4}是|现在才知道.{4,10})',
            content
        )

        # Look for past event references in this chapter
        past_events_referenced = []
        for ch in chapters[:chapter_num - 1]:
            ch_content = ch.get("content", "")
            if not ch_content:
                continue
            # Find key terms from old chapter still present
            key_terms = re.findall(r'(.{2,4})(?:事件|事变|之战|之约|的秘密|的真相)', ch_content)
            for term in key_terms:
                if term in content:
                    past_events_referenced.append({
                        "term": term,
                        "orig_chapter": ch.get("number", "?"),
                    })

        result = {
            "time_markers": time_markers[:10],
            "reinterpretations": reinterpretations,
            "past_events_referenced": past_events_referenced[:10],
            "spiral_depth": len(reinterpretations) + len(past_events_referenced),
            "chapter": chapter_num,
        }
        db.log(novel_id, "agent.time_spiral", result)
        return result
    except Exception as e:
        return {"error": str(e)}


def _agent_negative_space_health(novel_id: str, chapter_num: int, content: str) -> dict:
    """Check negative space consumption — what's deliberately omitted and when to reveal (§72)."""
    try:
        novel = db.get_novel(novel_id)
        total_chs = len(novel.get("chapters", [])) or 1
        position_ratio = chapter_num / total_chs

        # What is hinted but not shown?
        hints = re.findall(r'(?:似乎|仿佛|好像|隐隐|暗暗|悄悄|莫名|隐隐约约)(.{3,20}?)(?:[。!！?？,，])', content)

        # What is explicitly unanswered?
        unanswered = re.findall(r'(?:没人知道|谁也不清楚|没有人明白|不得而知|无从得知)(.{3,20}?)(?:[。!！?？,，])', content)

        # What does the reader still not know? (check unsaid table)
        unsaid = db.get_unsaid(novel_id)

        result = {
            "hints_deployed": hints[:10],
            "unanswered": unanswered,
            "unsaid_count": len(unsaid),
            "position_ratio": round(position_ratio, 2),
            "health": "healthy" if (len(unsaid) > 0 or len(hints) > 0) else "starving",
            "recommendation": "揭示快到了，准备伏笔收束" if position_ratio > 0.7 else "保持神秘，继续埋藏",
            "chapter": chapter_num,
        }
        db.log(novel_id, "agent.negative_space_health", result)
        return result
    except Exception as e:
        return {"error": str(e)}


def _agent_boundary_check(novel_id: str, chapter_num: int, content: str) -> dict:
    """Always-active boundary check — are we staying within our rules and canon? (§77)"""
    try:
        novel = db.get_novel(novel_id)
        world_rules = db.get_world_state(novel_id)

        # Check rule violations
        violations = []
        for rule in world_rules:
            if rule.get("is_broken"):
                violations.append({
                    "rule": rule.get("rule_name", "?"),
                    "description": rule.get("rule_description", "")[:60],
                })

        # Check for self-contradiction (simple heuristic)
        contradict_pairs: list[dict[str, str]] = []
        if "白天" in content and "黑夜" in content and content.index("白天") > content.index("黑夜"):
            pass  # OK — natural progression

        # Check for power creep / rule bending
        power_markers = re.findall(r'(?:突破|暴涨|飙升|翻倍|几何|无可匹敌|毁天灭地|灭世)', content)
        has_power_creep = len(power_markers) > 3

        # Check for unexplained changes
        unexplained = re.findall(r'(?:突然|忽然|莫名|不知为何|说不清)(.{3,15}?)(?:[。!！?？,，])', content)

        result = {
            "violations": violations,
            "violation_count": len(violations),
            "power_creep_detected": has_power_creep,
            "unexplained_changes": unexplained[:5],
            "world_rules_count": len(world_rules),
            "boundary_health": "violated" if violations else "clean" if not has_power_creep else "warning",
            "chapter": chapter_num,
        }
        db.log(novel_id, "agent.boundary_check", result)
        return result
    except Exception as e:
        return {"error": str(e)}


# ═══════════════ Agent Pipeline API ═══════════════

@router.post("/api/novels/{novel_id}/agent-pipeline")
def run_agent_pipeline(novel_id: str, background: BackgroundTasks, data: dict = {}) -> dict:
    """Run the complete Agent pipeline for next chapter generation (§4)."""
    if not db.get_novel(novel_id):
        raise HTTPException(404)

    novel = db.get_novel(novel_id)
    next_ch = novel.get("total_chapters", 0) + 1

    # Step 1: Editor-in-Chief → brief
    brief = _agent_editor_in_chief(novel_id, next_ch)

    # Step 2: Architect → outline
    outline = _agent_architect(novel_id, next_ch, brief)

    # Step 3: Trigger generation with brief + outline as direction
    if brief or outline:
        direction = f"【总编简报】\n{brief}\n\n【章节大纲】\n{outline}"
        _gen_directions[novel_id] = direction
        _gen_directions[novel_id + "_qthreshold"] = "0.75"

    # Step 4: Trigger generation
    background.add_task(_run_generation, novel_id)

    return {
        "status": "agent_pipeline_started",
        "novel_id": novel_id,
        "next_chapter": next_ch,
        "brief": brief[:200] if brief else "(skipped)",
        "outline": outline[:200] if outline else "(skipped)",
    }


# ═══════════════ Core: Constraint Builder (文档 §2-3) ═══════════════

def _build_constraints(novel_id: str, next_chapter: int) -> str:
    """
    生成前查故事圣经，输出约束块注入 prompt。
    数据库写小说，AI 只是笔。
    """
    constraints = []

    # ── 角色约束（静态设定 + 动态状态） ──
    novel = db.get_novel(novel_id) or {}
    static_chars = novel.get('characters', [])
    char_map = {c['name']: c for c in static_chars if c.get('name')}

    chars = db.get_character_state(novel_id)
    latest = {}
    for c in chars:
        latest[c['char_name']] = c

    # Static character traits (from characters table)
    for name, info in char_map.items():
        traits = []
        if info.get('personality'):
            traits.append(f"性格：{info['personality'][:30]}")
        if info.get('role') and info['role'] != '配角':
            traits.append(f"角色：{info['role']}")
        if traits:
            constraints.append(f"🎭 {name} — {'；'.join(traits)}")

    # Dynamic character states (from story_bible)
    for name, c in list(latest.items())[-8:]:
        parts = [name]
        if c.get('physical_state') and c['physical_state'] != '健康':
            parts.append(c['physical_state'])
            if '伤' in str(c['physical_state']) or '残' in str(c['physical_state']):
                parts.append('不能使用该部位')
            if c['physical_state'] == '死亡':
                parts.append('不能出场（除非幻觉/回忆）')
        if c.get('emotion'):
            emo = c['emotion']
            if '愤怒' in str(emo):
                parts.append('不会示弱或原谅')
            if '悲伤' in str(emo) or '绝望' in str(emo):
                parts.append('不会主动采取行动')
        if c.get('location'):
            parts.append(f"当前在{c['location']}")
        if len(parts) > 1:
            constraints.append(' - '.join(parts))

    # Dormant characters (not appeared in 5+ chapters)
    if chars and len(chars) > 2:
        all_names = set(c['char_name'] for c in chars)
        recent_names = set(c['char_name'] for c in chars[-5:])
        dormant = all_names - recent_names
        if dormant:
            constraints.append(f"💤 久未出场：{', '.join(list(dormant)[:3])} — 考虑本章让其出现或暗示存在")

    # ── 世界观约束 ──
    if novel.get('power_system'):
        constraints.append(f"🌍 修炼体系：{novel['power_system'][:60]}")
    if novel.get('world_rules'):
        try:
            rules = json.loads(novel['world_rules']) if isinstance(novel['world_rules'], str) else novel['world_rules']
            if isinstance(rules, list) and rules:
                constraints.append(f"🌍 世界规则：{'；'.join(str(r)[:40] for r in rules[:3])}")
        except Exception:
            pass

    # ── 伏笔约束 ──
    fs = db.get_active_foreshadowing(novel_id)
    overdue = [f for f in fs if f.get('status') == 'overdue' or
               (f.get('due_by_chapter') and int(f.get('due_by_chapter', 0)) <= next_chapter)]
    if overdue:
        constraints.append(f"⚠️ {len(overdue)} 个伏笔需在本章回收：")
        for f in overdue[:3]:
            constraints.append(f"  - 必须回收 #{f.get('id','?')}「{f.get('description','')[:60]}」")
    elif fs:
        constraints.append(f"📌 {len(fs)} 个活跃伏笔，本章可暗示但不需回收")

    # ── 代价约束 ──
    costs = db.get_cost_ledger(novel_id)
    gains = len([e for e in costs if e.get('gain')])
    losses = len([e for e in costs if e.get('loss')])
    if gains > losses + 1:
        constraints.append(f"⚖️ 获得 {gains} 次，失去 {losses} 次——本章需要一次失去来平衡代价")
    elif losses > gains + 1:
        constraints.append(f"⚖️ 失去 {losses} 次，获得 {gains} 次——本章需要一次获得来避免过于沉重")

    # ── 冰山约束（不说之书） ──
    unsaid = db.get_unsaid(novel_id)
    if unsaid:
        constraints.append(f"🧊 {len(unsaid)} 条隐藏真相——AI 必须知道但不能在正文写出")
        for u in unsaid[-5:]:
            constraints.append(f"  - 🔒 {u['entry'][:80]}")

    # ── 世界观约束 ──
    world = db.get_world_state(novel_id)
    broken = [w for w in world if w.get('is_broken')]
    if broken:
        for w in broken[-3:]:
            constraints.append(f"🌍 规则「{w.get('rule_name','?')}」曾被破坏——确保本章不重复破坏")

    # ── 对位约束（待激活的线） ──
    tl = db.get_timeline(novel_id)
    if len(tl) > 3:
        relay = len([c for c in chars if c.get('emotion')]) / max(1, len(tl))
        if relay < 0.2:
            constraints.append("📖 关系线长期停滞——本章应推进至少一个角色关系变化")

    return "\n".join(constraints) if constraints else "无特定约束，自由创作"


# ═══════════════ Background Helpers (migrated from old server.py) ═══════════════


def _run_draft(novel_id: str, author_input: str):
    """Background: generate draft directions."""
    try:
        from ..config import Config
        from ..generator import Generator
        provider = _get_provider(novel_id)
        models = provider.get("models", ["deepseek-v4-pro"])
        model = models[0] if isinstance(models, list) and models else "deepseek-v4-pro"
        cfg = Config(
            openai_api_key=provider.get("api_key", ""),
            openai_base_url=provider.get("base_url", ""),
            model=model,
        )
        state = _load_state(novel_id)
        if not state:
            return
        gen = Generator(cfg)
        gen.draft_directions(state, author_input)
        db.log(novel_id, "draft.generated", {"input": author_input[:100]})
    except Exception as e:
        db.log(novel_id, "draft.failed", {"error": str(e)})


def _run_expand(novel_id: str, chosen_id: str, direction: str, preview: str, hook: str, edits: str):
    """Background: expand selected draft to full chapter."""
    try:
        from ..config import Config
        from ..generator import DraftOption, Generator
        provider = _get_provider(novel_id)
        models = provider.get("models", ["deepseek-v4-pro"])
        model = models[0] if isinstance(models, list) and models else "deepseek-v4-pro"
        cfg = Config(
            openai_api_key=provider.get("api_key", ""),
            openai_base_url=provider.get("base_url", ""),
            model=model,
        )
        state = _load_state(novel_id)
        if not state:
            return
        gen = Generator(cfg)
        draft = DraftOption(id=chosen_id, title="", direction=direction, preview=preview, hook=hook)
        title, body = gen.expand(state, draft, edits)

        # De-AI post-processing
        body_de_ai, de_ai_changes = gen.de_ai(body)
        if de_ai_changes > 0:
            print(f"[EXPAND] de-AI: {de_ai_changes} changes")

        # Quality scoring
        try:
            quality = gen.score_quality(body_de_ai or body, state)
        except Exception:
            quality = {"overall": 0, "grade": "?", "issues": []}

        # Save chapter
        final_body = body_de_ai or body
        word_count = len(final_body)
        ch_count = len(db.get_novel(novel_id).get("chapters", []))
        try:
            final_quality = gen.judge_quality(final_body, state)
        except Exception:
            final_quality = {"overall": quality.get("overall", 0)}
        db.add_chapter(
            novel_id=novel_id, number=ch_count + 1, title=title,
            word_count=word_count, summary=final_body[:200],
            content=final_body,
            quality_score=final_quality.get("overall", 0),
            model_used=cfg.model,
        )
        db.log(novel_id, "chapter.expanded", {
            "chapter": ch_count + 1, "title": title,
            "quality": quality.get("overall", 0), "grade": quality.get("grade", "?"),
        })
        de_ai_info = f" de-AI:{de_ai_changes}" if de_ai_changes > 0 else ""
        print(f"[EXPAND] {novel_id} ch{ch_count + 1} — {word_count}w — Q:{quality.get('grade', '?')}({quality.get('overall', 0)}){de_ai_info}")
    except Exception as e:
        db.log(novel_id, "expand.failed", {"error": str(e)})


def _extract_story_bible(novel_id: str, chapter_num: int, content: str, chapter_title: str):
    """Auto-extract structured story data from generated chapter using LLM."""
    try:
        from ..config import Config
        from ..generator import Generator
        provider = _get_provider(novel_id)
        models = provider.get("models", ["deepseek-v4-pro"])
        model = "deepseek-v4-pro" if "deepseek-v4-pro" in str(models) else models[0]
        cfg = Config(
            openai_api_key=provider.get("api_key", ""),
            openai_base_url=provider.get("base_url", ""),
            model=model,
        )
        gen = Generator(cfg)

        prompt = f"""从以下小说章节中提取结构化信息。输出严格JSON格式，不要加任何解释。

{{
  "characters": [
    {{"name": "角色名", "emotion": "当前情绪", "physical_state": "身体状态",
      "knowledge": ["新获得的信息1"],
      "goal": "当前目标", "location": "当前位置",
      "relationships": [{{"target": "关联角色名", "change": "态度变化描述"}}]
    }}
  ],
  "foreshadowing": [
    {{"description": "新埋的伏笔描述", "hint_text": "原文暗示片段(20字以内)", "due_by_chapter": "预计回收章节(数字)"}}
  ],
  "locations": [
    {{"name": "地点名", "event": "发生的事件(10字)", "state_change": "状态变化"}}
  ],
  "timeline": {{"absolute_time": "故事内时间", "relative_time": "距上一章的时间", "event_summary": "本章事件一句话摘要"}},
  "world_rules": [
    {{"rule": "规则名", "description": "规则描述", "is_broken": false}}
  ],
  "costs": [
    {{"character": "角色名", "gain": "获得什么", "loss": "失去什么", "gain_type": "info/power/relationship/position", "loss_type": "freedom/innocence/trust/health", "is_immediate": true}}
  ]
}}

章节标题：{chapter_title}
章节正文（前3000字）：
{content[:3000]}
"""
        messages = [{"role": "user", "content": prompt}]
        result = gen._call_llm_with_retry(messages, max_tokens=2048)
        if not result:
            return

        # Extract JSON — handle truncated/malformed responses
        json_start = result.find("{")
        json_end = result.rfind("}") + 1
        if json_start >= 0 and json_end > json_start:
            raw_json = result[json_start:json_end]
            raw_json = re.sub(r",\s*}", "}", raw_json)
            raw_json = re.sub(r",\s*]", "]", raw_json)
            try:
                data = json.loads(raw_json)
            except json.JSONDecodeError:
                open_braces = raw_json.count("{") - raw_json.count("}")
                raw_json += "}" * max(0, open_braces)
                try:
                    data = json.loads(raw_json)
                except json.JSONDecodeError:
                    return

            # Save character states
            for char in data.get("characters", []):
                if char.get("name"):
                    knowledge = char.get("knowledge", [])
                    if isinstance(knowledge, list):
                        knowledge = json.dumps(knowledge, ensure_ascii=False)
                    relationships = char.get("relationships", [])
                    if isinstance(relationships, list):
                        relationships = json.dumps(relationships, ensure_ascii=False)
                    db.save_character_state(
                        novel_id, chapter_num, char["name"],
                        emotion=char.get("emotion", ""),
                        physical_state=char.get("physical_state", ""),
                        knowledge=knowledge,
                        goal=char.get("goal", ""),
                        location=char.get("location", ""),
                        relationships=relationships,
                    )

            # Save foreshadowing
            for fs in data.get("foreshadowing", []):
                if fs.get("description"):
                    due = fs.get("due_by_chapter")
                    db.save_foreshadowing(
                        novel_id, chapter_num, fs["description"],
                        hint_text=fs.get("hint_text", ""),
                        due_by=int(due) if due and str(due).isdigit() else None,
                    )

            # Save locations
            for loc in data.get("locations", []):
                if loc.get("name"):
                    db.save_location_history(
                        novel_id, chapter_num, loc["name"],
                        event=loc.get("event", ""),
                        state_change=loc.get("state_change", ""),
                    )

            # Save timeline
            tl = data.get("timeline", {})
            if tl:
                db.save_timeline_event(
                    novel_id, chapter_num,
                    absolute_time=tl.get("absolute_time", ""),
                    relative_time=tl.get("relative_time", ""),
                    event_summary=tl.get("event_summary", ""),
                )

            # Save world rules
            for rule in data.get("world_rules", []):
                if rule.get("rule"):
                    db.save_world_state(
                        novel_id, chapter_num, rule["rule"],
                        rule_description=rule.get("description", ""),
                        is_broken=rule.get("is_broken", False),
                    )

            # Save cost ledger entries
            for cost in data.get("costs", []):
                if cost.get("character") and (cost.get("gain") or cost.get("loss")):
                    db.save_cost_entry(
                        novel_id, chapter_num,
                        character_name=cost["character"],
                        gain=cost.get("gain", ""),
                        loss=cost.get("loss", ""),
                        gain_type=cost.get("gain_type", "info"),
                        loss_type=cost.get("loss_type", "none"),
                        is_immediate=cost.get("is_immediate", True),
                    )
    except Exception as e:
        print(f"[BIBLE] Extraction failed: {e}")


def _run_consistency_check(novel_id: str, chapter_num: int):
    """Run all 5 consistency checks against the story bible."""
    try:
        # Check 1: Character consistency
        chars = db.get_character_state(novel_id, chapter_num)
        prev_chars = db.get_character_state(novel_id, chapter_num - 1) if chapter_num > 1 else []
        prev_map = {c["char_name"]: c for c in prev_chars}

        for char in chars:
            name = char["char_name"]
            prev = prev_map.get(name)
            if not prev:
                continue
            if prev.get("physical_state") == "injured" and char.get("physical_state") == "healthy":
                db.log_consistency_issue(novel_id, chapter_num, "character", "error",
                    f"{name} 上一章受伤，本章突然健康——需要说明恢复过程",
                    f"添加一句话说明{name}如何恢复或接受了治疗")
            elif prev.get("physical_state") == "healthy" and char.get("physical_state") == "injured":
                db.log_consistency_issue(novel_id, chapter_num, "character", "info",
                    f"{name} 本章受伤（从健康→受伤），需要明确受伤原因", "")
            prev_know = prev.get("knowledge", "[]")
            curr_know = char.get("knowledge", "[]")
            if prev_know != curr_know and prev_know != "[]":
                db.log_consistency_issue(novel_id, chapter_num, "character", "info",
                    f"{name} 的知识状态发生了变化", "")

        # Check 2: Foreshadowing — mark overdue
        active_fs = db.get_active_foreshadowing(novel_id)
        for fs in active_fs:
            due = fs.get("due_by_chapter")
            if due and int(due) < chapter_num:
                db.log_consistency_issue(novel_id, chapter_num, "foreshadowing", "warning",
                    f"伏笔 #{fs['id']}：「{fs['description'][:50]}」预期在第 {due} 章回收，当前第 {chapter_num} 章——已过期",
                    f"建议在第 {chapter_num + 1} 章回收此伏笔，或标记为放弃")
                with db.conn() as c:
                    c.execute("UPDATE foreshadowing_tracker SET status='overdue' WHERE id=? AND status='active'",
                              (fs["id"],))

        # Check 3: World rules
        world_rules = db.get_world_state(novel_id)
        broken_rules = [r for r in world_rules if r.get("is_broken")]
        for rule in broken_rules[-3:]:
            db.log_consistency_issue(novel_id, chapter_num, "world", "warning",
                f"世界观规则「{rule['rule_name']}」被破坏",
                "确认这是剧情需要还是bug。如需恢复，在后续章节说明规则修正")

        # Check 4: Timeline (placeholder for future extension)
        # Check 5: Location — detect teleportation
        locations = db.get_location_history(novel_id)
        if len(locations) >= 2:
            curr_loc = locations[-1]
            prev_loc = locations[-2]
            if curr_loc.get("location_name") != prev_loc.get("location_name"):
                db.log_consistency_issue(novel_id, chapter_num, "timeline", "info",
                    f"地点从「{prev_loc['location_name']}」切换到「{curr_loc['location_name']}」",
                    "确认切换是否合理，是否需要添加旅行/过渡描写")
    except Exception as e:
        print(f"[CONSISTENCY] Check failed: {e}")
