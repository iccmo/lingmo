"""Core novel collection and detail endpoints."""

from __future__ import annotations

import json
import re

from fastapi import APIRouter, HTTPException

from novel_writer.routers.deps import get_db
from novel_writer.routers.novel.request_validation import bounded_int, text_field

router = APIRouter(tags=["novel"])


def _db():
    return get_db()


def _random_name(genre: str = "玄幻") -> str:
    from novel_writer.generator import random_protagonist_name

    name, _ = random_protagonist_name(genre)
    return name


def _summary(novel: dict) -> dict:
    return {
        "id": novel["id"],
        "title": novel["title"],
        "author": novel["author"],
        "genre": novel["genre"],
        "synopsis": novel["synopsis"] or "",
        "total_chapters": novel.get("total_chapters", 0),
        "total_words": novel.get("total_words", 0),
        "latest_chapter": novel.get("latest_chapter"),
    }


def _bounded_int(data: dict, key: str, default: int, lower: int, upper: int) -> int:
    return bounded_int(
        data,
        key,
        default,
        lower,
        upper,
        status_code=400,
        invalid_detail=f"{key} must be an integer",
        range_detail=f"{key} must be between {lower} and {upper}",
    )


@router.get("/api/novels")
def list_novels() -> list:
    return [_summary(novel) for novel in _db().list_novels()]


@router.post("/api/novels")
def create_novel(data: dict) -> dict:
    db = _db()
    novel_id = text_field(data, "id")
    if not novel_id:
        raise HTTPException(400, "id required")
    if not re.match(r"^[a-z0-9][a-z0-9-]*$", novel_id):
        raise HTTPException(400, "id must be lowercase alphanumeric with hyphens")
    if len(novel_id) > 50:
        raise HTTPException(400, "id too long (max 50)")
    title = str(data.get("title", novel_id)).strip()
    if not title:
        raise HTTPException(400, "title required")
    total_chapters = _bounded_int(data, "total_chapters", 50, 0, 2000)
    if db.get_novel(novel_id):
        raise HTTPException(409, f"'{novel_id}' already exists")

    novel = db.create_novel(
        id=novel_id,
        title=title,
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
        name=text_field(data, "protagonist_name") or _random_name(data.get("genre", "玄幻")),
        role="主角",
        personality=data.get("protagonist_personality", ""),
        background=data.get("protagonist_background", ""),
        power_level=data.get("protagonist_power", ""),
    )

    try:
        from dataclasses import asdict

        from novel_writer.generator import GENRE_TO_STYLE, STYLE_POOL

        style_key = GENRE_TO_STYLE.get(data.get("genre", "玄幻"), "玄幻")
        base_style = STYLE_POOL.get(style_key)
        if base_style:
            profile = base_style
            profile.novel_id = novel_id
            profile.writer_voice = data.get("writer_voice", "爆款网文")
            profile.knowledge_base = data.get("knowledge_base", "")
            profile.thought_system = data.get("thought_system", "")
            profile.central_question = data.get("central_question", "")
            db.save_style_profile(novel_id, asdict(profile))
    except Exception:
        pass

    for number in range(1, total_chapters + 1):
        db.add_chapter(
            novel_id=novel_id,
            number=number,
            title=f"第{number}章",
            word_count=0,
            content="",
            summary="",
            ending_hook="",
        )

    return _summary(db.get_novel(novel_id) or novel)


@router.get("/api/novels/{novel_id}")
def get_novel(novel_id: str) -> dict:
    novel = _db().get_novel(novel_id)
    if not novel:
        raise HTTPException(404, "Not found")

    result = _summary(novel)
    result["chapters"] = novel.get("chapters", [])
    result["world"] = {
        "name": novel.get("world_name", ""),
        "era": novel.get("world_era", ""),
        "geography": novel.get("world_geo", ""),
        "power_system": novel.get("power_system", ""),
        "rules": novel.get("world_rules", "")
        if isinstance(novel.get("world_rules"), list)
        else (json.loads(novel.get("world_rules", "[]")) if novel.get("world_rules") else []),
        "main_arc": novel.get("main_arc", ""),
        "current_arc": novel.get("current_arc", "开篇"),
        "arc_chapter_start": novel.get("arc_chapter_start", 1),
    }
    result["characters"] = novel.get("characters", [])
    result["factions"] = novel.get("factions", [])
    result["plot_points"] = novel.get("plot_points", [])
    result["character_relations"] = novel.get("character_relations", [])
    return result


@router.delete("/api/novels/{novel_id}")
def delete_novel(novel_id: str) -> dict:
    db = _db()
    if not db.get_novel(novel_id):
        raise HTTPException(404, "Not found")
    db.soft_delete_novel(novel_id)
    return {"ok": True}
