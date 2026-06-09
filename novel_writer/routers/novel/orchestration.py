"""Creative orchestration endpoints for multi-step novel workflows."""

from __future__ import annotations

import copy
import time
from dataclasses import asdict

from fastapi import APIRouter, BackgroundTasks, HTTPException

from novel_writer.routers.deps import get_db

from . import _legacy
from .generation import _ensure_generation_idle
from .orchestration_service import run_pipeline
from .request_validation import text_field
from .world_bible_service import run_world_bible

router = APIRouter(tags=["orchestration"])


def _db():
    return get_db()


@router.get("/api/novels/{novel_id}/check-ending")
def check_ending(novel_id: str) -> dict:
    """Check whether the novel has reached a natural ending point."""
    db = _db()
    novel = db.get_novel(novel_id)
    if not novel:
        raise HTTPException(404)

    generated_chapters = [
        chapter for chapter in novel.get("chapters", []) if chapter.get("word_count", 0) > 0
    ]
    if len(generated_chapters) < 5:
        return {"ready": False, "reason": "章节不足5章"}

    from novel_writer.config import Config
    from novel_writer.generator import Generator

    state = _legacy._load_state(novel_id)
    if not state:
        return {"ready": False, "reason": "无法加载状态"}

    audit = Generator(Config()).audit_foreshadowing(state)
    open_count = audit.get("total_open", 99)
    stale = audit.get("stale", [])
    last_chapters = generated_chapters[-3:]
    avg_quality = sum(chapter.get("quality_score", 0) for chapter in last_chapters) / len(last_chapters)
    ready = open_count <= 3 and avg_quality >= 0.7
    return {
        "ready": ready,
        "open_foreshadowing": open_count,
        "stale_foreshadowing": len(stale),
        "recent_avg_quality": round(avg_quality, 2),
        "recommendation": "可以收尾" if ready else f"还有{open_count}条伏笔未回收，建议继续生成",
    }


@router.post("/api/novels/{novel_id}/world-bible")
def generate_world_bible(novel_id: str, background: BackgroundTasks) -> dict:
    """Generate a full world bible from the novel synopsis."""
    if not _db().get_novel(novel_id):
        raise HTTPException(404)
    _ensure_generation_idle(novel_id)
    background.add_task(run_world_bible, novel_id)
    return {"status": "generating", "novel_id": novel_id}


@router.post("/api/novel-farm")
def novel_farm(data: dict, background: BackgroundTasks) -> dict:
    """Create several seed novels and start generation for each one."""
    db = _db()
    seeds = data.get("seeds", [])
    if not seeds:
        raise HTTPException(400, "seeds required")

    from novel_writer.generator import _get_style_for_genre, random_protagonist_name

    created = []
    for index, seed in enumerate(seeds):
        novel_id = f"farm-{int(time.time()) % 100000 + index}"
        name, _ = random_protagonist_name(seed.get("genre", "玄幻"))
        db.create_novel(
            id=novel_id,
            title=seed.get("title", f"农场第{index + 1}本"),
            synopsis=seed.get("synopsis", ""),
            genre=seed.get("genre", "玄幻"),
            char_key="protagonist",
            name=name,
            role="主角",
        )

        style = copy.copy(_get_style_for_genre(seed.get("genre", "玄幻")))
        style.novel_id = novel_id
        style.writer_voice = seed.get("voice", "爆款网文")
        db.save_style_profile(novel_id, asdict(style))
        created.append(novel_id)
        background.add_task(_legacy._run_generation, novel_id)

    return {"status": "farming", "novels": created, "message": f"种下{len(created)}本书，正在生长..."}


@router.post("/api/novels/{novel_id}/pipeline")
def trigger_pipeline(novel_id: str, background: BackgroundTasks) -> dict:
    """Start the autonomous publication pipeline."""
    if not _db().get_novel(novel_id):
        raise HTTPException(404)
    _ensure_generation_idle(novel_id)
    background.add_task(run_pipeline, novel_id)
    return {"status": "pipeline", "novel_id": novel_id, "message": "自主管线启动"}


@router.post("/api/autonomous-novel")
def autonomous_novel(data: dict, background: BackgroundTasks) -> dict:
    """Create a novel and start the fully autonomous book workflow."""
    db = _db()
    synopsis = text_field(data, "synopsis")
    genre = data.get("genre", "玄幻")
    title = data.get("title", "")
    chapters_count = data.get("chapters", 30)
    if not synopsis:
        raise HTTPException(400, "synopsis required")

    novel_id = data.get("id", f"auto-{int(time.time()) % 100000}")
    if not db.get_novel(novel_id):
        from novel_writer.generator import random_protagonist_name

        name, _ = random_protagonist_name(genre)
        db.create_novel(
            id=novel_id,
            title=title or synopsis[:20],
            author="AI",
            synopsis=synopsis,
            genre=genre,
            char_key="protagonist",
            name=name,
            role="主角",
        )
    _ensure_generation_idle(novel_id)
    background.add_task(_legacy._run_autonomous, novel_id, chapters_count)
    return {"status": "autonomous", "novel_id": novel_id, "message": f"全自动生成{chapters_count}章中..."}


@router.post("/api/demo")
def create_demo(background: BackgroundTasks) -> dict:
    """Create a demo novel and generate the first chapter."""
    db = _db()
    with db.conn() as conn:
        conn.execute("DELETE FROM chapters WHERE novel_id='demo'")
        conn.execute("DELETE FROM characters WHERE novel_id='demo'")
        conn.execute("DELETE FROM factions WHERE novel_id='demo'")
        conn.execute("DELETE FROM novel_tags WHERE novel_id='demo'")
        conn.execute("DELETE FROM novels WHERE id='demo'")

    db.create_novel(
        id="demo",
        title="修仙从炼丹开始",
        author="AI",
        genre="玄幻",
        synopsis="一个普通药师，意外获得上古丹方，从此踏上修仙之路",
        world_name="九天大陆",
        world_era="上古",
        power_system="练气→筑基→金丹→元婴→化神",
        main_arc="从普通药师到丹帝的逆袭之路",
        current_arc="开篇",
        char_key="protagonist",
        name=_legacy._random_name("玄幻"),
        role="主角",
        personality="坚韧不拔，心思缜密",
        background="普通药师，自幼父母双亡",
        tags=["炼丹", "系统流", "逆袭"],
    )
    background.add_task(_legacy._run_generation, "demo")
    return {"status": "ok", "novel_id": "demo", "message": "Demo novel created, generating first chapter..."}
