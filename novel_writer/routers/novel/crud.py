"""小说 CRUD + 章节 + 生成 — FastAPI Depends + Pydantic + Service。
挂载于 /api/v2，路径不含 /api 前缀。"""
import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ...schemas import (
    NovelCreate, NovelUpdate, NovelSummary, NovelDetail,
    ChapterUpdate, ChapterResponse, SystemStatus,
    GenerateRequest, GenerateBatchRequest, GenerateResponse, QueueStatus, GenStatus,
)
from ...services.novel_service import NovelService, get_session
from ...services.generation_service import GenerationService
from ...routers.deps import get_db as _get_legacy_db

router = APIRouter(tags=["v2"])


def get_service(session: Session = Depends(get_session)) -> NovelService:
    return NovelService(session)


def get_gen_service() -> GenerationService:
    return GenerationService(_get_legacy_db())


# ═══ Novel CRUD ═══

@router.get("/novels", response_model=list[NovelSummary])
def list_novels(svc: NovelService = Depends(get_service)):
    return svc.list_novels()


@router.post("/novels", response_model=NovelDetail, status_code=201)
def create_novel(data: NovelCreate, svc: NovelService = Depends(get_service)):
    if svc.get_novel(data.id):
        raise HTTPException(409, f"'{data.id}' already exists")
    return svc.create_novel(data)


@router.get("/novels/{novel_id}", response_model=NovelDetail)
def get_novel(novel_id: str, svc: NovelService = Depends(get_service)):
    novel = svc.get_novel(novel_id)
    if not novel:
        raise HTTPException(404)
    return novel


@router.put("/novels/{novel_id}", response_model=NovelDetail)
def update_novel(novel_id: str, data: NovelUpdate, svc: NovelService = Depends(get_service)):
    novel = svc.update_novel(novel_id, data)
    if not novel:
        raise HTTPException(404)
    return novel


@router.delete("/novels/{novel_id}", response_model=dict)
def delete_novel(novel_id: str, svc: NovelService = Depends(get_service)):
    if not svc.delete_novel(novel_id):
        raise HTTPException(404)
    return {"ok": True}


@router.get("/status", response_model=SystemStatus)
def system_status(svc: NovelService = Depends(get_service)):
    return svc.get_stats()


@router.get("/health")
def health_check(svc: NovelService = Depends(get_service)):
    """v2 Health check — DB connectivity + provider status."""
    import time
    start = time.time()

    # Check DB
    db_ok = False
    try:
        stats = svc.get_stats()
        db_ok = stats.get("novels_count", -1) >= 0
    except Exception:
        pass

    # Check providers
    providers = []
    try:
        db = _get_legacy_db()
        for p in db.list_providers():
            providers.append({
                "id": p["id"],
                "enabled": bool(p.get("is_enabled")),
                "has_key": bool(p.get("api_key")),
            })
    except Exception:
        pass

    return {
        "status": "ok" if db_ok else "degraded",
        "db": db_ok,
        "providers": providers,
        "latency_ms": round((time.time() - start) * 1000),
    }


# ═══ Chapter CRUD ═══

@router.get("/novels/{novel_id}/chapters/{chapter_num}", response_model=ChapterResponse)
def get_chapter(novel_id: str, chapter_num: int, svc: NovelService = Depends(get_service)):
    ch = svc.get_chapter(novel_id, chapter_num)
    if not ch:
        raise HTTPException(404)
    return ch


@router.put("/novels/{novel_id}/chapters/{chapter_num}", response_model=ChapterResponse)
def save_chapter(novel_id: str, chapter_num: int, data: ChapterUpdate, svc: NovelService = Depends(get_service)):
    ch = svc.save_chapter(novel_id, chapter_num, data.content)
    if not ch:
        raise HTTPException(404)
    return ch


# ═══ Generation ═══

@router.post("/novels/{novel_id}/generate", response_model=GenerateResponse)
def trigger_generate(
    novel_id: str,
    req: GenerateRequest = GenerateRequest(),
    svc: GenerationService = Depends(get_gen_service),
):
    try:
        return svc.trigger_generate(novel_id, req)
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.post("/novels/{novel_id}/generate-batch", response_model=GenerateResponse)
def trigger_generate_batch(
    novel_id: str,
    req: GenerateBatchRequest,
    svc: GenerationService = Depends(get_gen_service),
):
    try:
        return svc.trigger_batch(novel_id, req)
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.get("/novels/{novel_id}/generate/queue-status", response_model=QueueStatus)
def queue_status(novel_id: str, svc: GenerationService = Depends(get_gen_service)):
    return svc.get_queue_status(novel_id)


@router.get("/novels/{novel_id}/generate/stream")
async def generate_stream_sse(novel_id: str):
    """v2 SSE streaming — Event-based push (no polling)."""
    from ...state import gen_state

    async def event_stream():
        event = gen_state.get_event(novel_id)
        last = ""
        deadline = asyncio.get_event_loop().time() + 600  # 10 min timeout

        while True:
            try:
                event.clear()  # Clear BEFORE wait — prevents lost updates
                await asyncio.wait_for(event.wait(), timeout=30)
            except asyncio.TimeoutError:
                event.clear()  # Clear after timeout too
                pass  # Send heartbeat even if no change

            status = gen_state.get_status(novel_id)
            current = json.dumps(status, ensure_ascii=False)

            if current != last:
                last = current
                yield f"data: {current}\n\n"

            if status["status"] in ("complete", "error"):
                yield f"data: {current}\n\n"
                break

            if asyncio.get_event_loop().time() > deadline:
                yield f"data: {json.dumps({'status': 'idle', 'message': 'stream timeout'})}\n\n"
                break

        gen_state.clear_event(novel_id)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/novels/{novel_id}/generate/status", response_model=GenStatus)
def gen_status(novel_id: str, svc: GenerationService = Depends(get_gen_service)):
    return svc.get_gen_status(novel_id)


# ═══ Generation Traces ═══

@router.get("/novels/{novel_id}/traces", response_model=list[dict])
def get_traces(novel_id: str):
    """获取所有章的生成追踪数据。"""
    db = _get_legacy_db()
    return db.get_chapter_traces(novel_id)


@router.get("/novels/{novel_id}/traces/latest", response_model=dict)
def get_latest_trace(novel_id: str):
    """获取最新一章的生成追踪。"""
    db = _get_legacy_db()
    traces = db.get_chapter_traces(novel_id)
    if not traces:
        from fastapi import HTTPException
        raise HTTPException(404, "No traces found")
    return traces[0]  # Already sorted DESC


@router.delete("/novels/{novel_id}/chapters/{chapter_num}", response_model=dict)
def delete_chapter(novel_id: str, chapter_num: int, svc: NovelService = Depends(get_service)):
    svc.delete_chapter(novel_id, chapter_num)
    return {"ok": True}


# ═══ Soul Fingerprint ═══

@router.get("/novels/{novel_id}/soul-fingerprint")
def get_soul(novel_id: str):
    db = _get_legacy_db()
    fp = db.get_soul_fingerprint(novel_id)
    return fp or {"polarity": "", "position": 5, "answer": ""}


@router.post("/novels/{novel_id}/soul-fingerprint")
def save_soul(novel_id: str, data: dict):
    db = _get_legacy_db()
    db.save_soul_fingerprint(
        novel_id=novel_id,
        polarity=data.get("primaryPolarity", data.get("polarity", "")),
        position=int(data.get("position", 5)),
        answer=data.get("answer", "").strip(),
    )
    return {"ok": True}


@router.delete("/novels/{novel_id}/soul-fingerprint")
def delete_soul(novel_id: str):
    db = _get_legacy_db()
    db.delete_soul_fingerprint(novel_id)
    return {"ok": True}


# ═══ Character Blueprints ═══

@router.get("/novels/{novel_id}/character-blueprints")
def get_character_blueprints(novel_id: str):
    """获取小说所有角色蓝图。"""
    db = _get_legacy_db()
    return db.get_character_blueprints(novel_id)


@router.post("/novels/{novel_id}/character-blueprints")
def save_character_blueprints(novel_id: str, data: dict):
    """批量保存角色蓝图（全量替换）。"""
    db = _get_legacy_db()
    characters = data.get("characters", data if isinstance(data, list) else [])
    if isinstance(characters, dict):
        characters = [characters]
    db.save_character_blueprints(novel_id, characters)
    return {"ok": True, "count": len(characters)}


@router.delete("/novels/{novel_id}/character-blueprints/{char_id}")
def delete_character_blueprint(novel_id: str, char_id: str):
    """删除单个角色蓝图。"""
    db = _get_legacy_db()
    if not db.delete_character_blueprint(novel_id, char_id):
        raise HTTPException(404, "Character not found")
    return {"ok": True}
