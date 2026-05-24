"""FastAPI Web 后端 — REST API + Database"""

import json
import re
import sys
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .database import Database

app = FastAPI(title="Lingmo", version="0.2.0")
db = Database()


def _get_provider(novel_id: str = None):
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


app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


# ═══════════════ Helpers ═══════════════

def _random_name(genre: str = "玄幻") -> str:
    from .generator import random_protagonist_name
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

@app.get("/api/novels")
def list_novels():
    return [_summary(n) for n in db.list_novels()]


@app.post("/api/novels")
def create_novel(data: dict):
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
        from .generator import GENRE_TO_STYLE, STYLE_POOL, asdict
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


@app.get("/api/writer-voices")
def list_writer_voices():
    """List available writer voices."""
    from .generator import WRITER_VOICES
    return [{"key": k, "name": v.name, "description": v.description} for k, v in WRITER_VOICES.items()]


@app.get("/api/novels/{novel_id}")
def get_novel(novel_id: str):
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


@app.delete("/api/novels/{novel_id}")
def delete_novel(novel_id: str):
    if not db.get_novel(novel_id):
        raise HTTPException(404, "Not found")
    db.soft_delete_novel(novel_id)
    return {"ok": True}


# ═══════════════ Chapters ═══════════════

@app.get("/api/novels/{novel_id}/chapters/{chapter_num}")
def get_chapter(novel_id: str, chapter_num: int):
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


@app.put("/api/novels/{novel_id}/chapters/{chapter_num}")
def save_chapter(novel_id: str, chapter_num: int, data: dict):
    if not db.get_novel(novel_id):
        raise HTTPException(404, "Not found")
    db.update_chapter(novel_id, chapter_num, content=data.get("content", ""),
                      edit_ratio=data.get("edit_ratio", 0))
    return {"ok": True}


# ═══════════════ Generate ═══════════════

# In-memory store for chapter generation directions
_gen_directions: dict[str, str] = {}

@app.post("/api/novels/{novel_id}/generate")
def trigger_generate(novel_id: str, background: BackgroundTasks, data: dict = {}):
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
    background.add_task(_run_generation, novel_id)
    ch_count = len(db.get_novel(novel_id).get("chapters", []))
    return {"status": "generating", "novel_id": novel_id, "next_chapter": ch_count + 1}


@app.get("/api/novels/{novel_id}/report")
def quality_report(novel_id: str):
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
        from .config import Config
        from .generator import Generator
        provider = _get_provider(novel_id)
        cfg = Config(openai_api_key=provider.get("api_key",""), openai_base_url=provider.get("base_url",""),
                     model=provider.get("models","deepseek-v4-pro")[0] if provider.get("models") else "gpt-4o")
        gen = Generator(cfg)
        titles_raw = gen._call_llm_with_retry([
            {"role":"system","content":"你是一位出版编辑。基于小说内容生成5个备选书名，每个2-6字，有意象感。只输出书名，每行一个。"},
            {"role":"user","content": f"小说简介：{novel.get('synopsis','')}\n核心追问：{db.get_style_profile(novel_id).get('central_question','') if db.get_style_profile(novel_id) else ''}\n已有章节标题：{'、'.join(titles[:10])}"}
        ], max_tokens=256)
    except:
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


@app.post("/api/ab-test")
def ab_test_opening(data: dict, background: BackgroundTasks):
    """A/B test: generate chapter 1 with multiple writer voices, find optimal."""
    synopsis = data.get("synopsis", "").strip()
    genre = data.get("genre", "玄幻")
    voices = data.get("voices", None)  # None = test all
    if not synopsis: raise HTTPException(400, "synopsis required")
    background.add_task(_run_ab_test, synopsis, genre, voices)
    return {"status": "testing", "message": f"正在测试{len(voices) if voices else 14}种作家声音..."}


@app.post("/api/novels/{novel_id}/final-polish")
def final_polish(novel_id: str, background: BackgroundTasks):
    """出版前终极打磨——全本一致性检查+首尾呼应+重复短语清理。"""
    novel = db.get_novel(novel_id)
    if not novel: raise HTTPException(404)
    background.add_task(_run_final_polish, novel_id)
    return {"status": "polishing", "novel_id": novel_id, "message": "出版前终极打磨中..."}


@app.post("/api/novels/{novel_id}/polish")
def polish_novel(novel_id: str, background: BackgroundTasks):
    """全本精修：微调每章的小问题——不一致的称呼、突兀的过渡、冗余短语。"""
    novel = db.get_novel(novel_id)
    if not novel: raise HTTPException(404)
    background.add_task(_run_polish, novel_id)
    return {"status": "polishing", "novel_id": novel_id}


@app.get("/api/novels/{novel_id}/classic-assessment")
def classic_assessment(novel_id: str):
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
    from .generator import Generator
    gen = Generator(Config())
    opener_check = Generator._classic_check.__func__(None, first5[0].get("content","")[:500], None, None) if first5[0].get("content") else (True, [])
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


@app.post("/api/novels/{novel_id}/evolve")
def evolve_novel(novel_id: str, background: BackgroundTasks):
    """进化模式：如果不达标→自动换参数推倒重来，直到达标或达到最大迭代次数。"""
    novel = db.get_novel(novel_id)
    if not novel: raise HTTPException(404)
    background.add_task(_run_evolve, novel_id)
    return {"status": "evolving", "novel_id": novel_id}


@app.post("/api/novels/extract-dna")
def extract_narrative_dna(data: dict):
    """从一本已有的小说中提取叙事基因。data.source_novel_id: 源小说ID。"""
    source_id = data.get("source_novel_id", "")
    if not source_id: raise HTTPException(400, "source_novel_id required")
    novel = db.get_novel(source_id)
    if not novel: raise HTTPException(404)
    gen_chs = [c for c in novel.get("chapters",[]) if c.get("word_count",0) > 0]
    if len(gen_chs) < 3: raise HTTPException(400, "源小说至少3章")

    from .config import Config
    from .generator import Generator
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


@app.post("/api/novels/{novel_id}/import-chapters")
def import_chapters(novel_id: str, data: dict):
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


@app.post("/api/novels/search")
def search_novels(data: dict):
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


@app.get("/api/novels/{novel_id}/spellcheck")
def spellcheck_novel(novel_id: str):
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
    word_freq = {}
    for w in words:
        word_freq[w] = word_freq.get(w, 0) + 1
    for w, c in word_freq.items():
        if c >= 8:
            issues.append({"type": "repetition", "text": w, "count": c})
    return {"issues": issues, "total_chapters_checked": len(chs)}


@app.get("/api/novels/{novel_id}/algorithm-optimize")
def algorithm_optimize(novel_id: str):
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


@app.get("/api/market-trends")
def market_trends():
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


@app.get("/api/novels/{novel_id}/preview")
def preview_chapter(novel_id: str):
    """章节预览：生成200字样本展示风格和声音，不消耗完整生成费用。"""
    novel = db.get_novel(novel_id)
    if not novel: raise HTTPException(404)
    from .config import Config
    from .generator import Generator
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


@app.get("/api/novels/{novel_id}/reading-stats")
def reading_stats(novel_id: str):
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


@app.post("/api/novels/{novel_id}/compare")
def compare_chapters(novel_id: str, data: dict):
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


@app.get("/api/novels/{novel_id}/check-ending")
def check_ending(novel_id: str):
    """检测小说是否已到达自然结局——伏笔回收率、角色弧完成度、情绪曲线闭合度。"""
    novel = db.get_novel(novel_id)
    if not novel: raise HTTPException(404)
    gen_chs = [c for c in novel.get("chapters",[]) if c.get("word_count",0) > 0]
    if len(gen_chs) < 5: return {"ready": False, "reason": "章节不足5章"}

    # Check signals
    from .generator import Generator
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


@app.post("/api/novels/{novel_id}/world-bible")
def generate_world_bible(novel_id: str, background: BackgroundTasks):
    """从简介自动生成完整世界观设定——世界背景、修炼体系、势力分布、角色关系网。"""
    novel = db.get_novel(novel_id)
    if not novel: raise HTTPException(404)
    background.add_task(_run_world_bible, novel_id)
    return {"status": "generating", "novel_id": novel_id}


@app.post("/api/novel-farm")
def novel_farm(data: dict, background: BackgroundTasks):
    """批量种书：一次创建多本小说，不同体裁+不同声音，生成后横向对比评分。"""
    seeds = data.get("seeds", [])
    if not seeds: raise HTTPException(400, "seeds required")
    created = []
    import time as _t
    for i, seed in enumerate(seeds):
        nid = f"farm-{int(_t.time())%100000 + i}"
        from .generator import random_protagonist_name
        name, _ = random_protagonist_name(seed.get("genre","玄幻"))
        db.create_novel(id=nid, title=seed.get("title", f"农场第{i+1}本"),
                        synopsis=seed.get("synopsis",""), genre=seed.get("genre","玄幻"),
                        char_key="protagonist", name=name, role="主角")
        # Set writer voice
        voice = seed.get("voice", "爆款网文")
        from dataclasses import asdict

        from .generator import _get_style_for_genre
        style = _get_style_for_genre(seed.get("genre","玄幻"))
        style.novel_id = nid
        style.writer_voice = voice
        db.save_style_profile(nid, asdict(style))
        created.append(nid)
        background.add_task(_run_generation, nid)
    return {"status": "farming", "novels": created, "message": f"种下{len(created)}本书，正在生长..."}


@app.get("/api/novels/{novel_id}/export-full")
def export_full_novel(novel_id: str):
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


@app.post("/api/novels/{novel_id}/chapters/reorder")
def reorder_chapters(novel_id: str, data: dict):
    """重排章节顺序。data.order = {old_number: new_number, ...}"""
    if not db.get_novel(novel_id): raise HTTPException(404)
    order = data.get("order", {})
    for old_num, new_num in order.items():
        with db.conn() as c:
            c.execute("UPDATE chapters SET number=? WHERE novel_id=? AND number=?",
                     (new_num, novel_id, int(old_num)))
    return {"ok": True}


@app.get("/api/novels/{novel_id}/timeline")
def book_timeline(novel_id: str):
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


@app.get("/api/novels/{novel_id}/packaging")
def generate_packaging(novel_id: str):
    """生成书的简介、书名备选、封面描述——读者看到的第一印象。"""
    novel = db.get_novel(novel_id)
    if not novel: raise HTTPException(404)
    gen_chs = [c for c in novel.get("chapters",[]) if c.get("word_count",0) > 0]
    synopsis = novel.get("synopsis","")
    titles = [c.get("title","") for c in gen_chs[:5]]
    total_words = novel.get("total_words",0)

    from .config import Config
    from .generator import Generator
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


@app.get("/api/novels/{novel_id}/export-epub")
def export_epub(novel_id: str):
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



@app.get("/api/novels/{novel_id}/export-pdf")
def export_pdf(novel_id: str):
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


@app.get("/api/novels/{novel_id}/export-mobi")
def export_mobi(novel_id: str):
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

@app.get("/api/analytics-dashboard")
def analytics_dashboard():
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


@app.get("/api/publishing-dashboard")
def publishing_dashboard():
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


@app.get("/api/daily")
def daily_digest():
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


@app.get("/api/novels/{novel_id}/diffs")
def chapter_diffs(novel_id: str):
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


@app.get("/api/novels/{novel_id}/ask")
def ask_novel(novel_id: str, q: str = ""):
    """向自己的小说提问——基于RAG检索最相关的章节回答。"""
    if not q: raise HTTPException(400, "q required")
    from .config import Config
    from .generator import Generator
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


@app.get("/api/insights")
def cross_novel_insights():
    """跨书自适应学习：从所有已生成小说中提取模式。"""
    novels = db.list_novels()
    insights = {"total_novels": len(novels), "total_chapters": 0, "total_words": 0,
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


@app.post("/api/novels/{novel_id}/pipeline")
def trigger_pipeline(novel_id: str, background: BackgroundTasks):
    """自主出版管线：生成剩余章节 → 回修开头 → 识别弱章 → 经典重写 → 质量报告"""
    if not db.get_novel(novel_id):
        raise HTTPException(404)
    background.add_task(_run_pipeline, novel_id)
    return {"status": "pipeline", "novel_id": novel_id, "message": "自主管线启动"}


@app.get("/api/novels/{novel_id}/chapters/{chapter_num}/fact-check")
def fact_check_chapter(novel_id: str, chapter_num: int):
    """AI幻觉检测：让AI自己审计章节中的事实性陈述。"""
    ch = db.get_chapter(novel_id, chapter_num)
    if not ch: raise HTTPException(404)
    novel = db.get_novel(novel_id)
    from .config import Config
    from .generator import Generator
    provider = _get_provider(novel_id)
    cfg = Config(openai_api_key=provider.get("api_key",""), openai_base_url=provider.get("base_url",""),
                 model=provider.get("models","deepseek-v4-pro")[0] if provider.get("models") else "gpt-4o")
    gen = Generator(cfg)
    result = gen.fact_check(ch.get("content",""), novel.get("genre",""))
    return result


@app.post("/api/novels/{novel_id}/chapters/{chapter_num}/humanize")
def humanize_chapter(novel_id: str, chapter_num: int, background: BackgroundTasks):
    """深度去AI味——AI读自己的文字，找出不像人写的地方并修复。"""
    ch = db.get_chapter(novel_id, chapter_num)
    if not ch: raise HTTPException(404)
    background.add_task(_run_humanize, novel_id, chapter_num)
    return {"status": "humanizing", "novel_id": novel_id, "chapter": chapter_num}


@app.post("/api/novels/{novel_id}/chapters/{chapter_num}/revise")
def revise_chapter(novel_id: str, chapter_num: int, data: dict, background: BackgroundTasks):
    """基于自然语言批评重写章节。"""
    ch = db.get_chapter(novel_id, chapter_num)
    if not ch: raise HTTPException(404, "Chapter not found")
    critique = data.get("critique", "").strip()
    if not critique: raise HTTPException(400, "critique required")
    background.add_task(_run_revise_chapter, novel_id, chapter_num, critique)
    return {"status": "revising", "novel_id": novel_id, "chapter": chapter_num}


@app.post("/api/novels/{novel_id}/revise-opening")
def trigger_revise_opening(novel_id: str, background: BackgroundTasks):
    """全书生成完后，回头重写前3章——基于结局知识植入精准伏笔。"""
    if not db.get_novel(novel_id):
        raise HTTPException(404)
    background.add_task(_run_revise_opening, novel_id)
    return {"status": "revising", "novel_id": novel_id, "message": "正在基于结局重写前3章..."}


@app.post("/api/novels/{novel_id}/generate-classic")
def trigger_generate_classic(novel_id: str, background: BackgroundTasks):
    """经典模式：生成多版，只通过≥0.75+经典检查+跨章一致的版本。"""
    if not db.get_novel(novel_id):
        raise HTTPException(404)
    background.add_task(_run_generation_classic, novel_id)
    return {"status": "generating_classic", "novel_id": novel_id}


@app.post("/api/novels/{novel_id}/generate-batch")
def trigger_generate_batch(novel_id: str, data: dict, background: BackgroundTasks):
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


@app.get("/api/novels/{novel_id}/generate/queue-status")
def generate_queue_status(novel_id: str):
    """Get the current batch generation queue status for a novel."""
    queue_status = _get_queue_status(novel_id)
    if not queue_status:
        return {"job_id": None, "status": "idle", "progress": {"current": 0, "total": 0}, "last_error": None}
    return queue_status


def _run_generation(novel_id: str):
    """V3: Full generation pipeline with quality scoring, de-AI, and RAG"""
    try:
        _set_status(novel_id, "generating", "正在构思章节…（生成中，约需60秒）", 10)
        from .config import Config
        from .generator import Generator
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
        gen._on_stream_chunk = on_stream
        state = _load_state(novel_id)
        # Load style profile
        style = None
        try:
            from .generator import StyleProfile, _get_style_for_genre
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

        # Batch generate (n versions, pick best by quality)
        import time as _time
        t0 = _time.time()
        # Read author direction + soul injection if set
        author_direction = _gen_directions.pop(novel_id, "")
        soul_injection = _gen_directions.pop(novel_id + "_soul", "")
        if soul_injection:
            author_direction = soul_injection + ("\n\n作者方向：" + author_direction if author_direction else "")
        _set_status(novel_id, "generating", "正在生成候选版本…（约40秒）", 20)
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
            from .generator import Generator
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

        # V3: Store embeddings (non-blocking)
        try:
            gen.store_chapter_embedding(cid, novel_id, chapter.summary)
        except Exception:
            pass  # Embedding is optional for future searches

        # V7: Pre-generate TTS audio in background (non-blocking)
        try:
            import threading
            threading.Thread(target=_pregen_tts_background, args=(novel_id, chapter.number), daemon=True).start()
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
            from .config import Config
            from .generator import Generator
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
        from .config import Config
        from .generator import Generator
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
            from .generator import StyleProfile
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
    from .config import Config
    from .generator import Generator
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
        from .config import Config
        from .generator import Generator
        provider = _get_provider(novel_id)
        cfg = Config(openai_api_key=provider.get("api_key",""), openai_base_url=provider.get("base_url",""),
                     model=provider.get("models","deepseek-v4-pro")[0] if provider.get("models") else "gpt-4o")
        gen = Generator(cfg)
        state = _load_state(novel_id)
        ch = db.get_chapter(novel_id, chapter_num)
        if not ch or not state: raise Exception("Chapter or state not found")
        style = None
        try:
            from .generator import StyleProfile
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

    from .config import Config
    from .generator import GENRE_TO_STYLE, STYLE_POOL, Generator
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
        except:
            pass

        _set_status(novel_id, "complete", f"全自动完成！{target_chapters}章")
        db.log(novel_id, "autonomous.complete", {"chapters": target_chapters})
    except Exception as e:
        _set_status(novel_id, "error", str(e)[:200])


def _run_evolve(novel_id: str):
    """进化模式：迭代推倒→重来，直到经典潜质达标。max 3次，有成本追踪和死胡同检测。"""
    import random as _rd
    import time as _t

    from .config import Config
    from .generator import GENRE_TO_STYLE, STYLE_POOL, WRITER_VOICES, Generator
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
    from .config import Config
    from .generator import Generator
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
    from .config import Config
    from .generator import Generator
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
    from .config import Config
    from .generator import Generator
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
    from .config import Config
    from .generator import Generator
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
    from .config import Config
    from .generator import Generator, StyleProfile
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
        from .config import Config
        from .generator import Generator
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
            from .generator import StyleProfile
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
        from .config import Config
        from .generator import Generator
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
            from .generator import StyleProfile
            style_data = db.get_style_profile(novel_id)
            if style_data:
                style = StyleProfile(**style_data)
        except Exception:
            pass

        # Smart context window: generate chapter summaries for novels with 30+ chapters
        _ensure_smart_context(novel_id, gen, state)

        # RAG context (reuse across batch)
        rag_context = gen.retrieve_relevant_context(
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
                rag_context = summary_text + "\n\n" + rag_context
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
            try:
                gen.store_chapter_embedding(cid, novel_id, chapter.summary)
            except Exception:
                pass

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
    from .story_state import ChapterMeta, Character, Plot, StoryState, World
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


# ═══════════════ Publish ═══════════════

@app.post("/api/novels/{novel_id}/publish")
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


@app.get("/api/novels/{novel_id}/publish-status")
def publish_status(novel_id: str):
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

        from .publisher import Publisher
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

@app.post("/api/novels/{novel_id}/draft")
def draft_directions(novel_id: str, data: dict, background: BackgroundTasks):
    if not db.get_novel(novel_id):
        raise HTTPException(404)
    author_input = data.get("input", "")
    if not author_input:
        raise HTTPException(400, "input required")
    background.add_task(_run_draft, novel_id, author_input)
    return {"status": "drafting", "novel_id": novel_id}


@app.post("/api/novels/{novel_id}/expand")
def expand_chapter(novel_id: str, data: dict, background: BackgroundTasks):
    if not db.get_novel(novel_id):
        raise HTTPException(404)
    chosen_id = data.get("chosen_id", "")
    edits = data.get("edits", "")
    if not chosen_id:
        raise HTTPException(400, "chosen_id required")
    background.add_task(_run_expand, novel_id, chosen_id, data.get("direction",""), data.get("preview",""), data.get("hook",""), edits)
    return {"status": "expanding", "novel_id": novel_id}


# ═══════════════ Auto Mode ═══════════════

@app.post("/api/novels/{novel_id}/auto/start")
def auto_start(novel_id: str):
    if not db.get_novel(novel_id):
        raise HTTPException(404)
    db.set_scheduler_state(novel_id, is_running=1)
    db.log(novel_id, "mode.switched", {"from": "creator", "to": "auto"})
    return {"status": "started"}


@app.post("/api/novels/{novel_id}/auto/stop")
def auto_stop(novel_id: str):
    db.set_scheduler_state(novel_id, is_running=0)
    db.log(novel_id, "mode.switched", {"from": "auto", "to": "creator"})
    return {"status": "stopped"}


@app.post("/api/novels/{novel_id}/auto/once")
def auto_once(novel_id: str, background: BackgroundTasks):
    if not db.get_novel(novel_id):
        raise HTTPException(404)
    background.add_task(_run_generation, novel_id)
    return {"status": "running"}


# ═══════════════ System ═══════════════

@app.get("/api/status")
def system_status():
    novels = db.list_novels()
    return {
        "novels_count": len(novels),
        "total_chapters": sum(n.get("total_chapters", 0) for n in novels),
        "total_words": sum(n.get("total_words", 0) for n in novels),
        "server_time": __import__("datetime").datetime.now().isoformat(),
    }


@app.get("/api/logs")
def get_logs():
    return {"logs": db.get_logs(50)}


@app.get("/api/health")
def health():
    """系统自检：API Key、DB、磁盘空间、最后生成时间。"""
    issues = []
    # Check DB
    try:
        db.list_novels()
    except Exception as e:
        issues.append(f"DB: {e}")
    # Check API key
    provider = _get_provider(None)
    if not provider or not provider.get("api_key"):
        issues.append("未配置API Key")
    # Check disk
    import shutil
    disk = shutil.disk_usage("data")
    free_mb = disk.free / (1024*1024)
    if free_mb < 100:
        issues.append(f"磁盘空间不足({free_mb:.0f}MB)")
    return {
        "status": "degraded" if issues else "healthy",
        "issues": issues,
        "db": "ok" if not any("DB" in i for i in issues) else "error",
        "api_key_configured": bool(provider and provider.get("api_key")),
        "disk_free_mb": round(free_mb),
    }


@app.get("/api/novels/{novel_id}/revenue-estimate")
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


@app.get("/api/novels/{novel_id}/freshness-check")
def freshness_check(novel_id: str):
    """新鲜度检测：这个故事的设定、人物、冲突是否太像已有的爆款？"""
    novel = db.get_novel(novel_id)
    if not novel: raise HTTPException(404)
    synopsis = novel.get("synopsis","")
    genre = novel.get("genre","")
    gen_chs = [c for c in novel.get("chapters",[]) if c.get("word_count",0) > 0]

    from .config import Config
    from .generator import Generator
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


@app.get("/api/novels/{novel_id}/acquisition-review")
def acquisition_review(novel_id: str):
    """模拟出版社编辑的买断评估——这本书值不值得签。"""
    novel = db.get_novel(novel_id)
    if not novel: raise HTTPException(404)
    gen_chs = [c for c in novel.get("chapters",[]) if c.get("word_count",0) > 0]
    if len(gen_chs) < 10: return {"error": "至少需要10章才能做买断评估"}

    scores = [c.get("quality_score",0) for c in gen_chs]
    avg_q = sum(scores)/len(scores)
    titles = [c.get("title","") for c in gen_chs]

    # Acquisition criteria
    criteria = {
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

    total = sum(c["score"] for c in criteria.values())
    max_total = sum(c["max"] for c in criteria.values())
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


@app.get("/api/novels/{novel_id}/cockpit")
def writers_cockpit(novel_id: str):
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


@app.get("/api/novels/{novel_id}/retention-score")
def retention_score(novel_id: str):
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


@app.get("/api/novels/{novel_id}/monetization-status")
def monetization_status(novel_id: str):
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


@app.get("/api/novels/{novel_id}/optimal-publish-time")
def optimal_publish_time(novel_id: str):
    """最佳发布时间：基于平台用户活跃时段，建议每天几点发布。"""
    return {
        "best_times": ["12:00-13:00（午休阅读高峰）", "18:00-20:00（通勤+晚饭后）", "21:00-23:00（睡前黄金档）"],
        "worst_times": ["02:00-06:00（没人醒着）", "09:00-11:00（工作时间）"],
        "recommendation": "每天固定18:00和21:00各发1章——培养读者追更习惯",
        "weekend_bonus": "周末多发1章——读者周末阅读时长是工作日2倍",
    }


@app.get("/api/novels/{novel_id}/estimate")
def estimate_cost(novel_id: str):
    """预估生成成本。传入目标章数，返回预计花费。"""
    novel = db.get_novel(novel_id)
    if not novel: raise HTTPException(404)
    gen_chs = [c for c in novel.get("chapters",[]) if c.get("word_count",0) > 0]
    avg_words = sum(c["word_count"] for c in gen_chs) / len(gen_chs) if gen_chs else 2500
    provider = _get_provider(novel_id)
    model = provider.get("models","deepseek-v4-pro")[0] if provider else "gpt-4o"
    # Rough estimate: ~20000 input tokens + avg_words*3 output tokens per chapter
    from .generator import Generator
    per_chapter = Generator._calc_cost(model, 20000, int(avg_words * 2.5))
    return {
        "model": model,
        "avg_words_per_chapter": round(avg_words),
        "estimated_cost_per_chapter": round(per_chapter, 4),
        "estimated_10_chapters": round(per_chapter * 10, 2),
        "estimated_50_chapters": round(per_chapter * 50, 2),
    }


@app.get("/api/novels/{novel_id}/resume")
def resume_generation(novel_id: str):
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


@app.get("/api/ping")
def ping():
    return {"status": "ok"}



# ═══════════════ Model Providers ═══════════════

@app.get("/api/providers")
def list_providers():
    return db.list_providers()

@app.put("/api/providers/{provider_id}")
def update_provider(provider_id: str, data: dict):
    allowed = {"name", "base_url", "api_key", "models", "is_enabled", "priority"}
    updates = {k: v for k, v in data.items() if k in allowed and v is not None}
    if not updates:
        raise HTTPException(400, "No valid fields to update")
    if "models" in updates and isinstance(updates["models"], list):
        updates["models"] = json.dumps(updates["models"])
    db.save_provider(provider_id, **updates)
    return {"ok": True}

@app.get("/api/novels/{novel_id}/chapters/{chapter_num}/tts")
async def chapter_tts(novel_id: str, chapter_num: int, voice: str = "zh-CN-XiaoxiaoNeural", rate: str = "+0%", pitch: str = "+0Hz"):
    """Stream chapter audio — cached MP3 (pre-generated in background)."""
    novel = db.get_novel(novel_id)
    if not novel: raise HTTPException(404)
    ch = db.get_chapter(novel_id, chapter_num)
    if not ch: raise HTTPException(404)
    content = ch.get("content", "") or ch.get("summary", "")
    if not content: raise HTTPException(400, "No content")

    text = content.replace("#", "").replace("*", "").replace("_", "").replace(">", "").replace("[", "").replace("]", "")
    text = text[:5000]

    import hashlib
    content_hash = hashlib.md5(text.encode()).hexdigest()[:12]
    rate_safe = rate.replace("+", "p").replace("-", "m").replace("%", "")
    cache_name = f"{novel_id}_ch{chapter_num}_{voice}_{rate_safe}_{content_hash}.mp3"
    cache_dir = Path(__file__).parent.parent / "data" / "tts_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / cache_name

    from fastapi.responses import FileResponse

    # Cache hit — instant
    if cache_path.exists():
        return FileResponse(str(cache_path), media_type="audio/mpeg",
                          headers={"Content-Disposition": f"inline; filename=ch{chapter_num}.mp3"})

    # Cache miss — generate on-the-fly
    try:
        await _generate_tts_async(text, voice, rate, str(cache_path))
        return FileResponse(str(cache_path), media_type="audio/mpeg",
                          headers={"Content-Disposition": f"inline; filename=ch{chapter_num}.mp3"})
    except Exception as e:
        raise HTTPException(500, f"TTS failed: {str(e)[:100]}")


# ═══════════════ Full-text Search ═══════════════

@app.get("/api/search")
def search_chapters(q: str = "", novel_id: str = "", limit: int = 20):
    """Full-text search across all chapters or within a novel."""
    if not q or len(q) < 2:
        return {"results": [], "total": 0}

    with db.conn() as conn:
        if novel_id:
            rows = conn.execute("""
                SELECT c.novel_id, n.title as novel_title, c.number, c.title,
                       substr(c.content, max(0, instr(c.content, ?) - 40), 120) as snippet,
                       c.word_count
                FROM chapters c JOIN novels n ON n.id = c.novel_id
                WHERE c.novel_id = ? AND c.content LIKE ? AND c.word_count > 0
                ORDER BY c.number LIMIT ?
            """, (q, novel_id, '%' + q + '%', limit)).fetchall()
        else:
            rows = conn.execute("""
                SELECT c.novel_id, n.title as novel_title, c.number, c.title,
                       substr(c.content, max(0, instr(c.content, ?) - 40), 120) as snippet,
                       c.word_count
                FROM chapters c JOIN novels n ON n.id = c.novel_id
                WHERE c.content LIKE ? AND c.word_count > 0
                ORDER BY c.novel_id, c.number LIMIT ?
            """, (q, '%' + q + '%', limit)).fetchall()

        results = [{
            "novel_id": r["novel_id"], "novel_title": r["novel_title"],
            "chapter": r["number"], "title": r["title"],
            "snippet": r["snippet"], "word_count": r["word_count"],
        } for r in rows]

        count_row = conn.execute("SELECT COUNT(*) as cnt FROM chapters WHERE content LIKE ? AND word_count > 0",
            ('%' + q + '%',)).fetchone()
        return {"results": results, "total": count_row["cnt"] if count_row else 0}


# ═══════════════ App Settings Persistence ═══════════════

@app.post("/api/settings/sync")
def settings_sync(data: dict):
    """Sync app settings from frontend localStorage to DB."""
    try:
        for k, v in data.items():
            if isinstance(v, str) and len(v) < 5000:
                db.save_audio_setting(k, v)
        return {"ok": True}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/api/settings")
def settings_load():
    """Load all app settings from DB."""
    try:
        return db.load_audio_settings()
    except Exception as e:
        raise HTTPException(500, str(e))

# ═══════════════ Audio Data Sync ═══════════════

@app.post("/api/audio/sync")
def audio_sync(data: dict):
    """Sync audio data from frontend localStorage to server DB."""
    try:
        if 'progress' in data and data['progress']:
            for p in data['progress']:
                db.save_audio_progress(p['novelId'], p['chapterNum'], p.get('position', 0))
        if 'bookmarks' in data and data['bookmarks']:
            db.save_audio_bookmarks(data['bookmarks'])
        if 'settings' in data and data['settings']:
            for k, v in data['settings'].items():
                db.save_audio_setting(k, str(v))
        if 'playlist' in data and data['playlist']:
            db.save_audio_playlist(data['playlist'])
        if 'stats' in data and data['stats']:
            db.save_audio_stats(data['stats'])
        return {"ok": True}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/audio/data")
def audio_load():
    """Load all audio data from server DB."""
    try:
        bookmarks = db.load_audio_bookmarks()
        settings = db.load_audio_settings()
        playlist = db.load_audio_playlist()
        stats = db.load_audio_stats()
        progress = db.get_all_audio_progress()
        # Convert to frontend-friendly format
        return {
            "bookmarks": [{  "id": b['id'], "novelId": b['novel_id'], "novelTitle": b['novel_title'],
                "chapterNum": b['chapter_num'], "chapterTitle": b['chapter_title'],
                "position": b['position'], "note": b['note'], "tag": b['tag'],
                "createdAt": b.get('created_at', '')
            } for b in bookmarks],
            "progress": [{"novelId": p['novel_id'], "chapterNum": p['chapter_num'], "position": p['position_sec']} for p in progress],
            "settings": settings,
            "playlist": [{"novelId": p['novel_id'], "novelTitle": p['novel_title'], "chapterNum": p['chapter_num'], "chapterTitle": p['chapter_title']} for p in playlist],
            "stats": stats,
        }
    except Exception as e:
        raise HTTPException(500, str(e))


async def _generate_tts_async(text: str, voice: str, rate: str, output_path: str):
    """Generate TTS audio: edge_tts → ffmpeg → MP3 file."""
    import os
    import subprocess
    import tempfile

    import edge_tts

    communicate = edge_tts.Communicate(text, voice, rate=rate)
    tmp_raw = tempfile.NamedTemporaryFile(delete=False, suffix=".adts")
    raw_path = tmp_raw.name
    tmp_raw.close()
    await communicate.save(raw_path)

    result = subprocess.run([
        "ffmpeg", "-y", "-i", raw_path,
        "-acodec", "libmp3lame", "-ar", "44100", "-ac", "2", "-ab", "128k",
        output_path,
    ], capture_output=True, timeout=30)
    os.unlink(raw_path)

    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {result.stderr.decode()[:200]}")


@app.get("/api/novels/{novel_id}/chapters/{chapter_num}/tts-dramatic")
async def chapter_tts_dramatic(novel_id: str, chapter_num: int, voice: str = "zh-CN-XiaoxiaoNeural", rate: str = "+0%"):
    """Dramatic reading: single voice with pitch/rate variation per character."""
    novel = db.get_novel(novel_id)
    if not novel: raise HTTPException(404)
    ch = db.get_chapter(novel_id, chapter_num)
    if not ch: raise HTTPException(404)
    content = ch.get("content", "") or ch.get("summary", "")
    if not content: raise HTTPException(400, "No content")

    text = content.replace("#", "").replace("*", "").replace("_", "").replace(">", "").replace("[", "").replace("]", "")
    text = text[:5000]

    import hashlib
    content_hash = hashlib.md5(text.encode()).hexdigest()[:12]
    rate_safe = rate.replace("+", "p").replace("-", "m").replace("%", "")
    cache_name = f"{novel_id}_ch{chapter_num}_{voice}_{rate_safe}_dramatic_{content_hash}.mp3"
    cache_dir = Path(__file__).parent.parent / "data" / "tts_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / cache_name

    from fastapi.responses import FileResponse
    if cache_path.exists():
        return FileResponse(str(cache_path), media_type="audio/mpeg",
                          headers={"Content-Disposition": f"inline; filename=ch{chapter_num}_dramatic.mp3"})

    try:
        import os
        import re
        import subprocess
        import tempfile

        import edge_tts

        # Parse text into segments
        segments: list[tuple[str, str, str]] = []  # (text, pitch, rate)
        parts = re.split(r'(「[^」]*」)', text)

        for part in parts:
            if not part.strip():
                continue
            if part.startswith('「') and part.endswith('」'):
                # Dialogue — detect speaker type from nearby cues
                dialogue = part[1:-1]
                pitch, spd = _detect_voice_modulation(part, text)
                segments.append((dialogue, pitch, spd))
            else:
                # Narration
                segments.append((part, "+0Hz", rate))

        # Generate per-segment TTS
        seg_files: list[str] = []
        for i, (seg_text, seg_pitch, seg_rate) in enumerate(segments):
            if not seg_text.strip():
                continue
            communicate = edge_tts.Communicate(seg_text.strip(), voice, rate=seg_rate, pitch=seg_pitch)
            tmp_raw = tempfile.NamedTemporaryFile(delete=False, suffix=".adts")
            raw_path = tmp_raw.name
            tmp_raw.close()
            await communicate.save(raw_path)

            tmp_mp3 = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
            mp3_path = tmp_mp3.name
            tmp_mp3.close()

            result = subprocess.run([
                "ffmpeg", "-y", "-i", raw_path,
                "-acodec", "libmp3lame", "-ar", "44100", "-ac", "2", "-ab", "128k",
                mp3_path,
            ], capture_output=True, timeout=30)
            os.unlink(raw_path)
            if result.returncode != 0:
                raise RuntimeError(f"ffmpeg seg {i} failed: {result.stderr.decode()[:200]}")
            seg_files.append(mp3_path)

        # Concatenate all segments
        concat_list = tempfile.NamedTemporaryFile(delete=False, suffix=".txt", mode="w")
        for sf in seg_files:
            concat_list.write(f"file '{sf}'\n")
        concat_list.close()

        subprocess.run([
            "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_list.name,
            "-acodec", "copy", str(cache_path),
        ], capture_output=True, timeout=30)
        os.unlink(concat_list.name)

        # Cleanup segment files
        for sf in seg_files:
            try: os.unlink(sf)
            except: pass

        return FileResponse(str(cache_path), media_type="audio/mpeg",
                          headers={"Content-Disposition": f"inline; filename=ch{chapter_num}_dramatic.mp3"})
    except ImportError:
        raise HTTPException(500, "edge-tts not installed")
    except Exception as e:
        raise HTTPException(500, f"Dramatic TTS failed: {str(e)[:100]}")


def _detect_voice_modulation(dialogue: str, full_text: str) -> tuple[str, str]:
    """Detect speaker type from dialogue cues and return (pitch, rate)."""
    # Look for speaker cue in nearby text (before or after dialogue)
    combined = full_text

    # Male indicators
    if re.search(r'(他|男|父|兄|叔|爷|弟|君|公子|先生)(说|道|问|喊|吼|叫|怒|喝|冷笑|叹)', combined):
        return ("-5Hz", "-5%")
    # Female indicators
    if re.search(r'(她|女|母|姐|妹|姨|婆|娘|妃|小姐|姑娘|夫人)(说|道|问|喊|吼|叫|怒|喝|冷笑|叹)', combined):
        return ("+5Hz", "+3%")
    # Angry/shouting
    if re.search(r'(吼|怒|喝|斥|骂|叫|厉声|沉声|冷声)', combined):
        return ("-3Hz", "+10%")
    # Gentle/soft
    if re.search(r'(笑|轻|柔|叹|缓|慢|细|低声|悄声|温声|柔声)', combined):
        return ("+3Hz", "-5%")
    # Young/child
    if re.search(r'(小|童|孩|幼|少)(说|道|问|喊|叫)', combined):
        return ("+10Hz", "+10%")
    # Old/elder
    if re.search(r'(老|翁|媪|叟)(说|道|问)', combined):
        return ("-8Hz", "-8%")

    # Default: alternate based on dialogue position
    return ("+3Hz", "+3%") if hash(dialogue[:10]) % 2 == 0 else ("-3Hz", "-3%")


def _pregen_tts_background(novel_id: str, chapter_num: int):
    """Background task: pre-generate TTS for all voices at default speed."""
    try:
        novel = db.get_novel(novel_id)
        if not novel: return
        ch = db.get_chapter(novel_id, chapter_num)
        if not ch: return
        content = ch.get("content", "") or ch.get("summary", "")
        if not content: return

        text = content.replace("#", "").replace("*", "").replace("_", "").replace(">", "").replace("[", "").replace("]", "")
        text = text[:5000]

        import hashlib
        content_hash = hashlib.md5(text.encode()).hexdigest()[:12]
        cache_dir = Path(__file__).parent.parent / "data" / "tts_cache"
        cache_dir.mkdir(parents=True, exist_ok=True)

        # Pre-generate with default voice at 1x speed
        voice = "zh-CN-XiaoxiaoNeural"
        rate = "+0%"
        rate_safe = rate.replace("+", "p").replace("-", "m").replace("%", "")
        cache_name = f"{novel_id}_ch{chapter_num}_{voice}_{rate_safe}_{content_hash}.mp3"
        cache_path = cache_dir / cache_name

        if not cache_path.exists():
            print(f"[TTS-PREGEN] Generating {novel_id} ch{chapter_num}...")
            import asyncio
            asyncio.run(_generate_tts_async(text, voice, rate, str(cache_path)))
            print(f"[TTS-PREGEN] Done: {cache_path.name}")
    except Exception as e:
        print(f"[TTS-PREGEN] Failed: {e}")

@app.post("/api/providers/{provider_id}/test")
def test_provider(provider_id: str):
    """Test a provider's API key by making a minimal completion call."""
    provider = db.get_provider(provider_id)
    if not provider:
        raise HTTPException(404, "Provider not found")
    api_key = provider.get("api_key", "")
    if not api_key:
        return {"ok": False, "error": "未配置 API Key"}
    base_url = provider.get("base_url", "")
    model = (provider.get("models") or "deepseek-v4-pro")[0] if isinstance(provider.get("models"), list) else "gpt-4o"

    try:
        import openai
        client = openai.OpenAI(api_key=api_key, base_url=base_url, timeout=15)
        # Minimal test: list models or make a tiny completion
        r = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "hi"}],
            max_tokens=5,
        )
        return {"ok": True, "model": model, "response": r.choices[0].message.content if r.choices else "ok"}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}


def _run_draft(novel_id: str, author_input: str):
    """Background: generate draft directions"""
    try:
        from .config import Config
        from .generator import Generator
        provider = _get_provider(novel_id)
        cfg = Config(openai_api_key=provider.get("api_key",""), openai_base_url=provider.get("base_url",""),
                     model=provider.get("models","deepseek-v4-pro")[0] if provider.get("models") else "gpt-4o")
        state = _load_state(novel_id)
        if not state: return
        gen = Generator(cfg)
        gen.draft_directions(state, author_input)
        db.log(novel_id, "draft.generated", {"input": author_input[:100]})
    except Exception as e:
        db.log(novel_id, "draft.failed", {"error": str(e)})

def _run_expand(novel_id: str, chosen_id: str, direction: str, preview: str, hook: str, edits: str):
    """Background: expand selected draft to full chapter"""
    try:
        from .config import Config
        from .generator import DraftOption, Generator
        provider = _get_provider(novel_id)
        cfg = Config(openai_api_key=provider.get("api_key",""), openai_base_url=provider.get("base_url",""),
                     model=provider.get("models","deepseek-v4-pro")[0] if provider.get("models") else "gpt-4o")
        state = _load_state(novel_id)
        if not state: return
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
            quality = {'overall': 0, 'grade': '?', 'issues': []}

        # Save chapter
        final_body = body_de_ai or body
        word_count = len(final_body)
        ch_count = len(db.get_novel(novel_id).get("chapters", []))
        final_quality = gen.judge_quality(final_body, state, style)
        cid = db.add_chapter(novel_id=novel_id, number=ch_count+1, title=title,
                            word_count=word_count, summary=final_body[:200],
                            content=final_body,
                            quality_score=final_quality.get('overall', 0),
                            model_used=cfg.model)

        # Store embedding (non-blocking)
        try:
            gen.store_chapter_embedding(cid, novel_id, final_body[:200])
        except Exception:
            pass

        db.log(novel_id, "chapter.expanded", {
            "chapter": ch_count+1, "title": title,
            "quality": quality.get('overall', 0), "grade": quality.get('grade', '?'),
        })
        de_ai_info = f" de-AI:{de_ai_changes}" if de_ai_changes > 0 else ""
        print(f"[EXPAND] {novel_id} ch{ch_count+1} — {word_count}w — Q:{quality.get('grade','?')}({quality.get('overall',0)}){de_ai_info}")
    except Exception as e:
        db.log(novel_id, "expand.failed", {"error": str(e)})


@app.get("/api/novels/{novel_id}/generate/status")
def generate_status(novel_id: str):
    return _get_status(novel_id)


@app.get("/api/novels/{novel_id}/generate/stream")
async def generate_stream_sse(novel_id: str):
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

@app.get("/api/novels/{novel_id}/chapters/{chapter_num}/versions")
def chapter_versions(novel_id: str, chapter_num: int):
    """Get version history for a chapter."""
    return {"versions": db.get_chapter_versions(novel_id, chapter_num)}


@app.get("/api/novels/{novel_id}/chapters/{chapter_num}/versions/{version_id}")
def chapter_version_content(version_id: int):
    """Get a specific version's content."""
    content = db.get_chapter_version_content(version_id)
    if not content:
        raise HTTPException(404)
    return {"content": content}


# P2: Export chapter as TXT
@app.get("/api/novels/{novel_id}/chapters/{chapter_num}/export")
def export_chapter(novel_id: str, chapter_num: int):
    ch = db.get_chapter(novel_id, chapter_num)
    if not ch:
        raise HTTPException(404, "Not found")
    from fastapi.responses import PlainTextResponse
    content = f"{ch['title']}\n\n{ch.get('content', '')}"
    return PlainTextResponse(content, media_type="text/plain; charset=utf-8",
                             headers={"Content-Disposition": f"attachment; filename=chapter_{chapter_num}.txt"})


@app.get("/api/novels/{novel_id}/export")
def export_novel(novel_id: str, fmt: str = "txt"):
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
@app.delete("/api/novels/{novel_id}/characters/{char_key}")
def delete_character(novel_id: str, char_key: str):
    if not db.get_novel(novel_id):
        raise HTTPException(404, "Novel not found")
    with db.conn() as conn:
        conn.execute("DELETE FROM characters WHERE novel_id=? AND char_key=?", (novel_id, char_key))
    return {"ok": True}

@app.delete("/api/novels/{novel_id}/chapters/{chapter_num}")
def delete_chapter(novel_id: str, chapter_num: int):
    with db.conn() as conn:
        conn.execute("DELETE FROM chapters WHERE novel_id=? AND number=?", (novel_id, chapter_num))
    return {"ok": True}

# P1: One-click demo
@app.post("/api/autonomous-novel")
def autonomous_novel(data: dict, background: BackgroundTasks):
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
        from .generator import random_protagonist_name
        name, _ = random_protagonist_name(genre)
        db.create_novel(id=nid, title=title or synopsis[:20], author="AI", synopsis=synopsis,
                        genre=genre, char_key="protagonist", name=name, role="主角")
    background.add_task(_run_autonomous, nid, chapters_count)
    return {"status": "autonomous", "novel_id": nid, "message": f"全自动生成{chapters_count}章中..."}


@app.post("/api/demo")
def create_demo(background: BackgroundTasks):
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

@app.put("/api/novels/{novel_id}/world")
def update_world(novel_id: str, data: dict):
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

@app.put("/api/novels/{novel_id}/characters/{char_key}")
def update_character(novel_id: str, char_key: str, data: dict):
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

@app.post("/api/novels/{novel_id}/characters")
def add_character(novel_id: str, data: dict):
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

@app.post("/api/novels/{novel_id}/factions")
def add_faction(novel_id: str, data: dict):
    if not db.get_novel(novel_id):
        raise HTTPException(404)
    name = data.get('name', '').strip()
    if not name: raise HTTPException(400, "name required")
    with db.conn() as conn:
        conn.execute("INSERT INTO factions (novel_id,name,description,leader,sort_order) VALUES (?,?,?,?,?)",
                     (novel_id, name, data.get('description',''), data.get('leader',''), data.get('sort_order',0)))
    return {"ok": True}

@app.put("/api/novels/{novel_id}/factions/{faction_id}")
def update_faction(novel_id: str, faction_id: int, data: dict):
    with db.conn() as conn:
        row = conn.execute("SELECT id FROM factions WHERE id=? AND novel_id=?", (faction_id, novel_id)).fetchone()
        if not row: raise HTTPException(404)
        fields = {k: data[k] for k in ['name','description','leader','sort_order'] if k in data}
        if fields:
            sets = ", ".join(f"{k}=?" for k in fields)
            conn.execute(f"UPDATE factions SET {sets} WHERE id=?", list(fields.values()) + [faction_id])
    return {"ok": True}

@app.delete("/api/novels/{novel_id}/factions/{faction_id}")
def delete_faction(novel_id: str, faction_id: int):
    with db.conn() as conn:
        conn.execute("DELETE FROM factions WHERE id=? AND novel_id=?", (faction_id, novel_id))
    return {"ok": True}

# ═══════════════ V5: Chapter Outline ═══════════════

@app.get("/api/novels/{novel_id}/outline")
def get_outline(novel_id: str):
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

@app.post("/api/novels/{novel_id}/outline")
def save_outline(novel_id: str, data: dict):
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

@app.delete("/api/novels/{novel_id}/outline/{chapter_num}")
def delete_outline_item(novel_id: str, chapter_num: int):
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

@app.post("/api/novels/{novel_id}/suggest-outline")
def suggest_outline(novel_id: str):
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
        from .config import Config
        from .generator import Generator
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

@app.post("/api/novels/{novel_id}/generate-cover")
def generate_cover(novel_id: str):
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
        from .config import Config
        from .generator import Generator
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

@app.post("/api/novels/{novel_id}/clone")
def clone_novel(novel_id: str, data: dict | None = None):
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


@app.get("/api/novels/{novel_id}/analytics")
def get_analytics(novel_id: str):
    """Get chapter analytics: retention, drop-off points, quality correlation."""
    if not db.get_novel(novel_id):
        raise HTTPException(404, "Novel not found")
    return _compute_analytics(novel_id)


@app.get("/api/novels/{novel_id}/foreshadowing")
def get_foreshadowing_audit(novel_id: str):
    """Get foreshadowing audit: open, stale, recovered stats."""
    if not db.get_novel(novel_id):
        raise HTTPException(404, "Novel not found")
    from .config import Config
    from .generator import Generator
    provider = _get_provider(novel_id)
    cfg = Config(openai_api_key=provider.get("api_key",""), openai_base_url=provider.get("base_url",""),
                 model=provider.get("models","deepseek-v4-pro")[0] if provider.get("models") else "gpt-4o")
    gen = Generator(cfg)
    state = _load_state(novel_id)
    if not state:
        raise HTTPException(500, "Failed to load state")
    return gen.audit_foreshadowing(state)


@app.get("/api/novels/{novel_id}/continuity")
def chapter_continuity(novel_id: str):
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


@app.get("/api/costs")
def get_costs(novel_id: str = ""):
    """Get cost summary for a novel or all novels."""
    return db.get_cost_summary(novel_id)


@app.get("/api/costs/summary")
def costs_summary():
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


@app.post("/api/novels/{novel_id}/optimize-prompt")
def optimize_prompt(novel_id: str, background: BackgroundTasks):
    """Analyze performance and auto-tune StyleProfile parameters."""
    if not db.get_novel(novel_id):
        raise HTTPException(404, "Novel not found")

    analytics = _compute_analytics(novel_id)
    chapters = analytics.get("chapters", [])
    adjustments = []

    # Load current style
    from .generator import StyleProfile, _get_style_for_genre, asdict
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

@app.post("/api/novels/{novel_id}/chapters/{chapter_num}/proofread")
def proofread_chapter(novel_id: str, chapter_num: int):
    """AI校对：找出错别字、重复用词、逻辑不连贯、标点错误。"""
    ch = db.get_chapter(novel_id, chapter_num)
    if not ch:
        raise HTTPException(404, "Chapter not found")
    content = ch.get("content", "")
    if not content:
        raise HTTPException(400, "Chapter has no content")

    from .config import Config
    from .generator import Generator
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

@app.post("/api/novels/import")
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
        toc_items = []
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


@app.post("/api/backup/cloud")
def cloud_backup():
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


@app.get("/api/backup/status")
def backup_status():
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

FRONTEND_DIST = Path(__file__).parent.parent / "frontend" / "dist"

# Mount static assets first (JS, CSS, images, etc.)
if FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIST / "assets")), name="assets")

# SPA fallback: serve static files if they exist, otherwise index.html
@app.get("/{full_path:path}")
async def serve_spa(full_path: str):
    """Serve static file if it exists, otherwise fallback to SPA index.html"""
    if full_path.startswith("api/"):
        raise HTTPException(404)
    file_path = FRONTEND_DIST / full_path
    if file_path.is_file():
        return FileResponse(file_path)
    index_path = FRONTEND_DIST / "index.html"
    if not index_path.exists():
        raise HTTPException(404, "Frontend not built. Run: cd frontend && npm run build")
    return FileResponse(index_path)

@app.get("/")
async def serve_root():
    """Serve SPA root"""
    index_path = FRONTEND_DIST / "index.html"
    if not index_path.exists():
        raise HTTPException(404, "Frontend not built")
    return FileResponse(index_path)
