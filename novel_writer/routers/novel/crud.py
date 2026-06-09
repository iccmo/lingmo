"""Typed v2 API facade for core novel workflows.

This router is mounted by ``server.py`` at ``/api/v2``. Keep paths relative to
that prefix so the public contract stays ``/api/v2/novels/...``.
"""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, HTTPException

from novel_writer.routers.deps import get_db, get_gen_state
from novel_writer.routers.novel.request_validation import bounded_int, text_field
from novel_writer.state import is_active_generation_status

from . import chapters as chapter_routes
from . import core as core_routes
from . import generation as generation_routes

router = APIRouter(tags=["v2"])


CHARACTER_BLUEPRINT_FIELDS = (
    "id",
    "name",
    "role",
    "entrance",
    "signature",
    "speechPattern",
    "coreWound",
    "surfaceTrait",
    "hiddenSelf",
    "arcStart",
    "arcEnd",
    "obsession",
    "contradiction",
    "voiceSample",
    "contrastWith",
    "contrastHow",
)


def _db():
    return get_db()


def _normalize_character_blueprints(data: dict) -> list[dict]:
    raw = data.get("characters", [])
    if not isinstance(raw, list):
        raise HTTPException(400, "characters must be a list")
    if len(raw) > 100:
        raise HTTPException(400, "characters must be at most 100 items")

    normalized: list[dict] = []
    seen_ids: set[str] = set()
    for index, item in enumerate(raw, 1):
        if not isinstance(item, dict):
            raise HTTPException(400, f"characters[{index}] must be an object")
        char_id = text_field(item, "id")
        name = text_field(item, "name")
        if not char_id:
            raise HTTPException(400, f"characters[{index}].id required")
        if not name:
            raise HTTPException(400, f"characters[{index}].name required")
        if char_id in seen_ids:
            raise HTTPException(400, f"duplicate character id: {char_id}")
        seen_ids.add(char_id)
        normalized.append({field: text_field(item, field) for field in CHARACTER_BLUEPRINT_FIELDS})
    return normalized


@router.get("/novels")
def list_novels() -> list:
    return core_routes.list_novels()


@router.post("/novels", status_code=201)
def create_novel(data: dict) -> dict:
    return core_routes.create_novel(data)


@router.get("/novels/{novel_id}")
def get_novel(novel_id: str) -> dict:
    return core_routes.get_novel(novel_id)


@router.put("/novels/{novel_id}")
def update_novel(novel_id: str, data: dict) -> dict:
    db = _db()
    if not db.get_novel(novel_id):
        raise HTTPException(404, "Not found")

    allowed = {
        "title",
        "author",
        "synopsis",
        "genre",
        "world_name",
        "world_era",
        "world_geo",
        "power_system",
        "main_arc",
        "current_arc",
        "arc_chapter_start",
    }
    updates = {key: value for key, value in data.items() if key in allowed}
    if updates:
        db.update_novel(novel_id, **updates)
    return core_routes.get_novel(novel_id)


@router.delete("/novels/{novel_id}")
def delete_novel(novel_id: str) -> dict:
    return core_routes.delete_novel(novel_id)


@router.get("/status")
def system_status() -> dict:
    novels = _db().list_novels()
    active = sum(
        1
        for novel in novels
        if is_active_generation_status(get_gen_state().get_status(novel["id"]).get("status"))
    )
    return {"novels": len(novels), "active_generations": active}


@router.get("/health")
def health_check() -> dict:
    """v2 Health check: DB connectivity + provider status."""
    db = _db()
    providers = db.list_providers()
    return {"ok": True, "db": "ok", "providers": len(providers)}


@router.get("/novels/{novel_id}/chapters/{chapter_num}")
def get_chapter(novel_id: str, chapter_num: int) -> dict:
    return chapter_routes.get_chapter(novel_id, chapter_num)


@router.put("/novels/{novel_id}/chapters/{chapter_num}")
def save_chapter(novel_id: str, chapter_num: int, data: dict) -> dict:
    chapter_routes.save_chapter(novel_id, chapter_num, data)
    return chapter_routes.get_chapter(novel_id, chapter_num)


@router.delete("/novels/{novel_id}/chapters/{chapter_num}")
def delete_chapter(novel_id: str, chapter_num: int) -> dict:
    return chapter_routes.delete_chapter(novel_id, chapter_num)


@router.post("/novels/{novel_id}/generate")
def trigger_generate(novel_id: str, background: BackgroundTasks, data: dict = {}) -> dict:
    return generation_routes.trigger_generate(novel_id, background, data)


@router.post("/novels/{novel_id}/generate-batch")
def trigger_generate_batch(novel_id: str, data: dict, background: BackgroundTasks) -> dict:
    return generation_routes.trigger_generate_batch(novel_id, data, background)


@router.get("/novels/{novel_id}/generate/queue-status")
def queue_status(novel_id: str) -> dict:
    return generation_routes.generate_queue_status(novel_id)


@router.get("/novels/{novel_id}/generate/stream")
async def generate_stream_sse(novel_id: str):
    """v2 SSE streaming: event-based push."""
    return await generation_routes.generate_stream_sse(novel_id)


@router.get("/novels/{novel_id}/generate/status")
def gen_status(novel_id: str) -> dict:
    return get_gen_state().get_status(novel_id)


@router.get("/novels/{novel_id}/traces")
def get_traces(novel_id: str) -> list[dict]:
    """获取所有章的生成追踪数据。"""
    if not _db().get_novel(novel_id):
        raise HTTPException(404, "Not found")
    return _db().get_chapter_traces(novel_id)


@router.get("/novels/{novel_id}/traces/latest")
def get_latest_trace(novel_id: str) -> dict:
    """获取最新一章的生成追踪。"""
    traces = get_traces(novel_id)
    return traces[0] if traces else {}


@router.get("/novels/{novel_id}/soul-fingerprint")
def get_soul(novel_id: str):
    if not _db().get_novel(novel_id):
        raise HTTPException(404, "Not found")
    return _db().get_soul_fingerprint(novel_id) or {}


@router.post("/novels/{novel_id}/soul-fingerprint")
def save_soul(novel_id: str, data: dict):
    if not _db().get_novel(novel_id):
        raise HTTPException(404, "Not found")
    polarity = text_field(data, "polarity") or text_field(data, "primaryPolarity")
    if not polarity:
        raise HTTPException(400, "polarity required")
    position = bounded_int(
        data,
        "position",
        5,
        1,
        10,
        status_code=400,
        invalid_detail="position must be an integer",
        range_detail="position must be 1-10",
    )
    answer = text_field(data, "answer")
    if not answer:
        raise HTTPException(400, "answer required")
    _db().save_soul_fingerprint(novel_id, polarity, position, answer)
    return {"ok": True}


@router.delete("/novels/{novel_id}/soul-fingerprint")
def delete_soul(novel_id: str):
    if not _db().get_novel(novel_id):
        raise HTTPException(404, "Not found")
    _db().delete_soul_fingerprint(novel_id)
    return {"ok": True}


@router.get("/novels/{novel_id}/character-blueprints")
def get_character_blueprints(novel_id: str):
    """获取小说所有角色蓝图。"""
    if not _db().get_novel(novel_id):
        raise HTTPException(404, "Not found")
    return {"characters": _db().get_character_blueprints(novel_id)}


@router.post("/novels/{novel_id}/character-blueprints")
def save_character_blueprints(novel_id: str, data: dict):
    """批量保存角色蓝图（全量替换）。"""
    if not _db().get_novel(novel_id):
        raise HTTPException(404, "Not found")
    characters = _normalize_character_blueprints(data)
    _db().save_character_blueprints(novel_id, characters)
    return {"ok": True, "characters": characters}


@router.delete("/novels/{novel_id}/character-blueprints/{char_id}")
def delete_character_blueprint(novel_id: str, char_id: str):
    """删除单个角色蓝图。"""
    if not _db().get_novel(novel_id):
        raise HTTPException(404, "Not found")
    if not _db().delete_character_blueprint(novel_id, char_id):
        raise HTTPException(404, "Character blueprint not found")
    return {"ok": True}
