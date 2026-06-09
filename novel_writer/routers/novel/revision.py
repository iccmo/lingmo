"""Revision, polish, and generation-variant endpoints."""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, HTTPException

from novel_writer.routers.deps import get_db, get_gen_state

from .generation import _ensure_generation_idle
from .generation_service import run_generation_classic, run_longrun_batch_generation
from .request_validation import bounded_float, bounded_int, text_field
from .revision_service import (
    run_ab_test,
    run_evolve,
    run_final_polish,
    run_humanize,
    run_polish,
    run_revise_chapter,
    run_revise_opening,
)

router = APIRouter(tags=["revision"])


def _bounded_int(data: dict, key: str, default: int, lower: int, upper: int) -> int:
    return bounded_int(
        data,
        key,
        default,
        lower,
        upper,
        status_code=400,
        invalid_detail=f"{key} must be an integer",
        range_detail=f"{key} must be {lower}-{upper}",
    )


def _bounded_float(data: dict, key: str, default: float, lower: float, upper: float) -> float:
    return bounded_float(
        data,
        key,
        default,
        lower,
        upper,
        status_code=400,
        invalid_detail=f"{key} must be a number",
        range_detail=f"{key} must be {lower}-{upper}",
    )


def _db():
    return get_db()


@router.post("/api/ab-test")
def ab_test_opening(data: dict, background: BackgroundTasks) -> dict:
    """A/B test: generate chapter 1 with multiple writer voices, find optimal."""
    synopsis = text_field(data, "synopsis")
    genre = data.get("genre", "玄幻")
    voices = data.get("voices", None)
    if not synopsis:
        raise HTTPException(400, "synopsis required")
    background.add_task(run_ab_test, synopsis, genre, voices)
    return {"status": "testing", "message": f"正在测试{len(voices) if voices else 14}种作家声音..."}


@router.post("/api/novels/{novel_id}/final-polish")
def final_polish(novel_id: str, background: BackgroundTasks) -> dict:
    """Run final full-book polish before publication."""
    if not _db().get_novel(novel_id):
        raise HTTPException(404)
    _ensure_generation_idle(novel_id)
    background.add_task(run_final_polish, novel_id)
    return {"status": "polishing", "novel_id": novel_id, "message": "出版前终极打磨中..."}


@router.post("/api/novels/{novel_id}/polish")
def polish_novel(novel_id: str, background: BackgroundTasks) -> dict:
    """Polish all generated chapters."""
    if not _db().get_novel(novel_id):
        raise HTTPException(404)
    _ensure_generation_idle(novel_id)
    background.add_task(run_polish, novel_id)
    return {"status": "polishing", "novel_id": novel_id}


@router.post("/api/novels/{novel_id}/evolve")
def evolve_novel(novel_id: str, background: BackgroundTasks) -> dict:
    """Run iterative evolution until quality improves or limits are reached."""
    if not _db().get_novel(novel_id):
        raise HTTPException(404)
    _ensure_generation_idle(novel_id)
    background.add_task(run_evolve, novel_id)
    return {"status": "evolving", "novel_id": novel_id}


@router.post("/api/novels/{novel_id}/chapters/{chapter_num}/humanize")
def humanize_chapter(novel_id: str, chapter_num: int, background: BackgroundTasks) -> dict:
    """Deep-humanize one chapter."""
    if not _db().get_chapter(novel_id, chapter_num):
        raise HTTPException(404)
    _ensure_generation_idle(novel_id)
    background.add_task(run_humanize, novel_id, chapter_num)
    return {"status": "humanizing", "novel_id": novel_id, "chapter": chapter_num}


@router.post("/api/novels/{novel_id}/chapters/{chapter_num}/revise")
def revise_chapter(novel_id: str, chapter_num: int, data: dict, background: BackgroundTasks) -> dict:
    """Revise a chapter from natural-language critique."""
    if not _db().get_chapter(novel_id, chapter_num):
        raise HTTPException(404, "Chapter not found")
    _ensure_generation_idle(novel_id)
    critique = text_field(data, "critique")
    if not critique:
        raise HTTPException(400, "critique required")
    get_gen_state().set_status(novel_id, "revising", f"正在根据批评重写第{chapter_num}章…")
    background.add_task(run_revise_chapter, novel_id, chapter_num, critique)
    return {"status": "revising", "novel_id": novel_id, "chapter": chapter_num}


@router.post("/api/novels/{novel_id}/revise-opening")
def trigger_revise_opening(novel_id: str, background: BackgroundTasks) -> dict:
    """Revise the opening chapters using ending knowledge."""
    if not _db().get_novel(novel_id):
        raise HTTPException(404)
    _ensure_generation_idle(novel_id)
    background.add_task(run_revise_opening, novel_id)
    return {"status": "revising", "novel_id": novel_id, "message": "正在基于结局重写前3章..."}


@router.post("/api/novels/{novel_id}/generate-classic")
def trigger_generate_classic(novel_id: str, background: BackgroundTasks) -> dict:
    """Generate in classic multi-candidate mode."""
    if not _db().get_novel(novel_id):
        raise HTTPException(404)
    _ensure_generation_idle(novel_id)
    background.add_task(run_generation_classic, novel_id)
    return {"status": "generating_classic", "novel_id": novel_id}


@router.get("/api/novels/{novel_id}/consistency-score")
def get_consistency_score(novel_id: str) -> dict:
    """Get cross-chapter consistency score."""
    from novel_writer.stations.novel.consistency_scorer import ConsistencyScorer

    scorer = ConsistencyScorer()
    return scorer.run({"novel_id": novel_id, "db": _db()})


@router.post("/api/novels/{novel_id}/batch-generate")
def trigger_batch_generate(novel_id: str, background: BackgroundTasks, data: dict = {}) -> dict:
    """Generate N chapters sequentially with fixed constraint level for long-run testing."""
    if not _db().get_novel(novel_id):
        raise HTTPException(404)
    _ensure_generation_idle(novel_id)
    data = data or {}
    chapters = _bounded_int(data, "chapters", 10, 1, 20)
    compression = text_field(data, "compression", "L1").upper()
    quality_threshold = _bounded_float(data, "quality_threshold", 0.75, 0.5, 1.0)
    if compression not in ("L0", "L1", "L2", "L3", "NONE"):
        compression = "L1"
    background.add_task(run_longrun_batch_generation, novel_id, chapters, compression, quality_threshold)
    return {
        "status": "batch_started",
        "novel_id": novel_id,
        "chapters": chapters,
        "compression": compression,
    }
