"""灵墨 Web 后端 — 4 模块架构"""

import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from .log_config import get_logger

log = get_logger(__name__)
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .database import Database
from .state import gen_state

# ═══════════════ App Init ═══════════════

app = FastAPI(title="Lingmo", version="0.3.0")
db = Database()


def _get_provider(novel_id: str | None = None):
    """Get configured model provider — default to DeepSeek."""
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
    return provider or {
        "id": "deepseek",
        "base_url": "https://api.deepseek.com",
        "api_key": "",
        "models": ["deepseek-v4-pro"],
    }


# ═══════════════ Dependency Injection ═══════════════

from .routers.deps import init_deps as _init_router_deps

_init_router_deps(db, gen_state)

# ═══════════════ Middleware ═══════════════

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

from .middleware import RequestIDMiddleware, RateLimitMiddleware
app.add_middleware(RequestIDMiddleware)
app.add_middleware(RateLimitMiddleware)


# ── Global exception handler ──
from fastapi import Request
from fastapi.responses import JSONResponse

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    log.error(f"Unhandled: {type(exc).__name__}: {exc}", extra={"path": str(request.url)})
    return JSONResponse(
        status_code=500,
        content={"error": type(exc).__name__, "detail": str(exc)[:500]},
    )


# ═══════════════ AI Suggestion ═══════════════

def _get_pro_model(provider: dict) -> str:
    """选择最强模型用于创意任务。"""
    models = provider.get("models", [])
    return models[0] if models else "gpt-4o"


def _get_flash_model(provider: dict) -> str:
    """选择最便宜的可用模型用于简单任务。"""
    models = provider.get("models", [])
    return models[1] if len(models) > 1 else (models[0] if models else "gpt-4o-mini")


@app.post("/api/suggest-novel")
def suggest_novel(data: dict) -> dict:
    """AI 根据题材+风格生成书名和简介。支持风格切换避免重复。"""
    genre = data.get("genre", "玄幻")
    seed = data.get("seed", "").strip()
    style = data.get("style", "orthodox")  # orthodox | subversive | humorous
    retry = data.get("retry", 0)  # >0 时增加随机性避免重复

    from .generator import Generator
    from .config import Config
    provider = _get_provider()
    temp = 0.85 + retry * 0.05  # 每次重试略微增加随机性
    cfg = Config(
        openai_api_key=provider.get("api_key", ""),
        openai_base_url=provider.get("base_url", ""),
        model=_get_pro_model(provider),
        temperature=min(temp, 1.1),
    )
    gen = Generator(cfg)

    seed_hint = f'\n核心创意方向：「{seed}」' if seed else ''

    # ── 题材专属指导 ──
    genre_guides = {
        "玄幻": "仙侠/异界/修炼体系，金手指要有独创性。好书名如《诡秘之主》《大奉打更人》《道诡异仙》",
        "都市": "现代背景+身份反差。好书名如《都挺好》《漫长的季节》，网文版需更挑逗",
        "悬疑": "悬念驱动，短而有力。好书名如《隐秘的角落》《沉默的真相》《心理罪》",
        "科幻": "未来感+科学美感。好书名如《三体》《深海余烬》《我们生活在南京》",
        "历史": "古风+穿越优势。好书名如《覆汉》《秦吏》《新宋》《唐砖》",
        "官场": "低调有力，体制内博弈。好书名如《二号首长》《人民的名义》《狂飙》",
        "仙侠": "古典仙气，逆天改命。好书名如《遮天》《仙逆》《剑来》《凡人修仙传》",
        "女频": "情感细腻，身份互动。好书名如《知否》《甄嬛传》《步步惊心》《东宫》",
        "系统流": "系统+数据化，爽感驱动。好书名如《全职高手》《惊悚乐园》《学霸的黑科技系统》",
        "游戏": "游戏设定+现实交错。好书名如《超神机械师》《这不是游戏》《亏成首富从游戏开始》",
        "灵异": "恐怖+悬疑，民俗文化。好书名如《我有一座恐怖屋》《神秘复苏》《青囊尸衣》",
        "轻小说": "日式轻快+二次元。好书名如《关于我转生变成史莱姆这档事》《Re:从零开始的异世界生活》",
        "种田": "生活流+经营养成。好书名如《农家小福女》《北宋小地主》《我在末世种个田》",
        "运动": "竞技+热血成长。好书名如《围棋少年》《排球少年》《灌篮高手》",
        "武侠": "古典江湖，侠义恩仇。好书名如《天龙八部》《雪中悍刀行》《剑来》",
        "末世": "生存危机+人道困境。好书名如《全球进化》《废土》《我在末世捡空投》",
        "无限流": "多世界穿梭+规则博弈。好书名如《无限恐怖》《惊悚乐园》《王牌进化》",
        "奇幻": "西方奇幻+魔法体系。好书名如《盘龙》《哈利波特》《冰与火之歌》",
        "二次元": "动漫风格+萌系设定。好书名如《我的妹妹不可能这么可爱》《刀剑神域》",
        "军事": "战争+策略+热血。好书名如《亮剑》《佣兵的战争》《弹痕》",
        "古代言情": "古风+情感+权谋。好书名如《知否》《甄嬛传》《东宫》《长相思》",
        "现代言情": "都市情感+职场。好书名如《何以笙箫默》《微微一笑很倾城》",
        "纯爱": "男性向耽美，情感细腻。好书名如《魔道祖师》《天官赐福》《杀破狼》",
    }
    genre_guide = genre_guides.get(genre, "4-7字书名，有辨识度。好书名参考榜单TOP50")

    # ── 风格指导 ──
    style_guides = {
        "orthodox": "正统网文风格：爽感+成长+逆袭。金手指清晰有力，设定严谨。",
        "subversive": "反套路/脑洞风格：反转经典设定，突破读者预期。如修仙者发现世界是假的、反派觉醒自我意识。",
        "humorous": "轻松搞笑风格：无厘头设定+反差萌+吐槽流。如魔王转生异世界结果异世界没有魔力、修仙界第一天才其实是个社恐。",
        "dark": "黑暗虐心风格：残酷世界观+道德困境+悲剧美学。主角在黑暗中挣扎，没有绝对的好人。如末世废土唯有绝望、修仙界天道已死仙人圈养凡人。",
        "hotblooded": "热血燃向风格：高燃打斗+突破极限+集体荣誉。如废材少年觉醒最强血脉、被人嘲笑的梦想终将实现。",
    }
    style_guide = style_guides.get(style, style_guides["orthodox"])
    avoid_hint = "避免重复之前生成的设定。" if retry > 0 else ""

    prompt = f"""你是起点中文网资深签约编辑。为「{genre}」题材创意3个高质量小说设定。

## 题材要求
{genre_guide}

## 风格要求
{style_guide}
{avoid_hint}

## 书名要求
- 4-7字，有辨识度和记忆点，避免俗套
- 不用「XX传」「XX录」「重生之XX」「超级XX系统」等模板

## 简介公式
「主角身份」+「独特金手指/困境」+「核心冲突」+「钩子」
30-60字，精炼有力，让人想继续读
{seed_hint}

## 输出格式
1. 《书名》
简介：（一句话简介）

2. 《书名》
简介：（一句话简介）

3. 《书名》
简介：（一句话简介）"""

    try:
        result = gen._call_llm_with_retry([
            {"role": "system", "content": "你是资深网文编辑。返回纯文本，严格按格式输出。"},
            {"role": "user", "content": prompt},
        ], max_tokens=1024)

        suggestions = []
        for line in result.split("\n"):
            line = line.strip()
            if line.startswith("《") or (line and line[0].isdigit() and ". " in line[:4]):
                title = line.split("《")[-1].split("》")[0] if "《" in line else ""
                if title:
                    suggestions.append({"title": title, "synopsis": ""})
            elif "简介" in line and suggestions:
                syn = line.split("：", 1)[-1].split(":", 1)[-1].strip().rstrip("。")
                if syn:
                    suggestions[-1]["synopsis"] = syn

        if not suggestions or all(not s["synopsis"] for s in suggestions):
            suggestions = [{"title": s, "synopsis": ""} for s in
                [l.strip().strip("123. ").strip("《").strip("》").strip()
                 for l in result.split("\n") if l.strip() and ("《" in l or "简介" in l)]]

        return {"suggestions": suggestions[:3]}
    except Exception as e:
        return {"suggestions": [], "error": str(e)[:200]}


@app.post("/api/polish-novel-idea")
def polish_novel_idea(data: dict) -> dict:
    """AI 优化用户现有的书名和简介，让它们更有吸引力。"""
    title = data.get("title", "").strip()
    synopsis = data.get("synopsis", "").strip()
    genre = data.get("genre", "玄幻")
    if not title and not synopsis:
        return {"title": "", "synopsis": "", "error": "请至少填写书名或简介"}

    from .generator import Generator
    from .config import Config
    provider = _get_provider()
    cfg = Config(
        openai_api_key=provider.get("api_key", ""),
        openai_base_url=provider.get("base_url", ""),
        model=_get_pro_model(provider),
        temperature=0.7,
    )
    gen = Generator(cfg)

    prompt = f"""你是起点资深编辑。优化以下{genre}题材小说的书名和简介。

## 优化原则
- 书名越短越好（4-7字），去掉冗余修饰词
- 简介用「主角+金手指+冲突+钩子」四段式，30-60字
- 不要加"且看""究竟""最终"等废话
- 保留原意的核心设定，只优化表达力

现有书名：{title or '（无）'}
现有简介：{synopsis or '（无）'}

返回JSON格式：
{{"title": "优化后的书名", "synopsis": "优化后的一句话简介"}}"""

    try:
        result = gen._call_llm_with_retry([
            {"role": "system", "content": "你是资深网文编辑。返回纯JSON，不要markdown包裹。"},
            {"role": "user", "content": prompt},
        ], max_tokens=512)

        import json as _json
        result = result.strip()
        if result.startswith("```"):
            result = result.split("\n", 1)[1].rsplit("\n", 1)[0]
        data = _json.loads(result)
        return {"title": data.get("title", title), "synopsis": data.get("synopsis", synopsis)}
    except Exception as e:
        return {"title": title, "synopsis": synopsis, "error": str(e)[:200]}


# ═══════════════ Register 4 Module Routers ═══════════════
# Order matters: drama/script/audiobook have specific routes (/film-settings etc.)
# that must match BEFORE novel's catch-all /{novel_id} parameter route.

from .routers.audiobook import router as audiobook_router
from .routers.drama import router as drama_router
from .routers.novel import router as novel_router
from .routers.novel.crud import router as novel_crud_router  # NEW: typed CRUD on /api/v2
from .routers.script import router as script_router

app.include_router(drama_router)
app.include_router(script_router)
app.include_router(audiobook_router)
app.include_router(novel_crud_router, prefix="/api/v2")  # NEW: typed CRUD on v2 prefix
app.include_router(novel_router)       # must be LAST (catch-all routes)


# ═══════════════ Global Endpoints ═══════════════


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
    """系统自检：API Key、DB、磁盘空间。"""
    issues = []
    try:
        db.list_novels()
    except Exception as e:
        issues.append(f"DB: {e}")
    provider = _get_provider()
    if not provider or not provider.get("api_key"):
        issues.append("未配置API Key")
    import shutil

    disk = shutil.disk_usage("data")
    free_mb = disk.free / (1024 * 1024)
    if free_mb < 100:
        issues.append(f"磁盘空间不足({free_mb:.0f}MB)")
    return {
        "status": "degraded" if issues else "healthy",
        "issues": issues,
        "db": "ok" if not any("DB" in i for i in issues) else "error",
        "api_key_configured": bool(provider and provider.get("api_key")),
        "disk_free_mb": round(free_mb),
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
    model = (
        (provider.get("models") or "deepseek-v4-pro")[0]
        if isinstance(provider.get("models"), list)
        else "gpt-4o"
    )
    try:
        import openai

        client = openai.OpenAI(api_key=api_key, base_url=base_url, timeout=15)
        r = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "hi"}],
            max_tokens=5,
        )
        return {
            "ok": True,
            "model": model,
            "response": r.choices[0].message.content if r.choices else "ok",
        }
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}


# ═══════════════ App Settings ═══════════════


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


# ═══════════════ Static File Serving (SPA) ═══════════════

FRONTEND_DIST = Path(__file__).parent.parent / "frontend" / "dist"

if FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIST / "assets")), name="assets")


@app.get("/{full_path:path}")
async def serve_spa(full_path: str):
    """Serve static file if it exists, otherwise fallback to SPA index.html."""
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
    """Serve SPA root."""
    index_path = FRONTEND_DIST / "index.html"
    if not index_path.exists():
        raise HTTPException(404, "Frontend not built")
    return FileResponse(index_path)
