"""灵墨 Web 后端 — 4 模块架构

模块：
  - novel    : 小说 CRUD、写作生成、质量分析、导出发布
  - audiobook: TTS 语音合成、音频播放
  - script   : 视觉圣经、AI 导演分镜、Prompt 生成
  - drama    : 画面生成、配音配乐、视频合成
"""

import json
import threading
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .database import Database

# ═══════════════ App Init ═══════════════

app = FastAPI(title="Lingmo", version="0.3.0")
db = Database()

# ═══════════════ Shared State ═══════════════

_gen_status: dict[str, dict] = {}
_gen_lock = threading.Lock()


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


def _set_status(novel_id: str, status: str, message: str = "", progress: int = 0, overall: float = 0):
    with _gen_lock:
        _gen_status[novel_id] = {"status": status, "message": message, "progress": progress}
        if overall > 0:
            _gen_status[novel_id]["overall"] = round(overall, 2)


def _get_status(novel_id: str) -> dict:
    return _gen_status.get(novel_id, {"status": "idle", "message": "", "progress": 0})


# ═══════════════ Dependency Injection ═══════════════

from .routers.deps import init_deps as _init_router_deps

_init_router_deps(db, _set_status, _get_status)

# ═══════════════ Middleware ═══════════════

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ═══════════════ Register 4 Module Routers ═══════════════
# Order matters: drama/script/audiobook have specific routes (/film-settings etc.)
# that must match BEFORE novel's catch-all /{novel_id} parameter route.

from .routers.audiobook import router as audiobook_router
from .routers.drama import router as drama_router
from .routers.novel import router as novel_router
from .routers.script import router as script_router

app.include_router(drama_router)    # /api/novels/film-settings etc.
app.include_router(script_router)   # /api/novels/{id}/visual-bible etc.
app.include_router(audiobook_router)  # /api/search, /api/audio/* etc.
app.include_router(novel_router)    # /api/novels/{novel_id} — must be LAST


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
