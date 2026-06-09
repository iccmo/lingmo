"""Constraint previewing, compression tests, and choice-collapse endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from novel_writer.routers.deps import get_db
from novel_writer.routers.novel.request_validation import text_field

router = APIRouter(tags=["constraints"])


def _db():
    return get_db()


@router.get("/api/novels/{novel_id}/preview-constraints")
def preview_constraints(novel_id: str, level: str = "L1") -> dict:
    """Preview constraints that will be injected into next chapter generation."""
    db = _db()
    novel = db.get_novel(novel_id)
    if not novel:
        raise HTTPException(404)

    from novel_writer.stations.novel.constraint_builder import ConstraintBuilder
    from novel_writer.stations.novel.constraint_compressor import ConstraintCompressor

    next_chapter = db.get_next_chapter_number(novel_id) if hasattr(db, "get_next_chapter_number") else (
        max([chapter["number"] for chapter in novel.get("chapters", []) if chapter.get("word_count", 0) > 0], default=0) + 1
    )
    result = ConstraintBuilder().run({"novel_id": novel_id, "chapter_num": next_chapter, "db": db})
    all_levels = ConstraintCompressor().generate_all_levels(result)

    return {
        "next_chapter": next_chapter,
        "hard_count": result["hard_count"],
        "soft_count": result["soft_count"],
        "selected_level": level,
        "preview": all_levels[level]["text"][:500],
        "all_levels": {
            level_name: {"chars": item["char_count"], "lines": item["line_count"]}
            for level_name, item in all_levels.items()
        },
    }


@router.get("/api/novels/{novel_id}/test-constraints")
def test_constraint_compression(novel_id: str) -> dict:
    """A/B test: compare all 4 constraint compression levels."""
    db = _db()
    novel = db.get_novel(novel_id)
    if not novel:
        raise HTTPException(404)

    from novel_writer.stations.novel.compression_tester import CompressionTester

    next_chapter = db.get_next_chapter_number(novel_id) if hasattr(db, "get_next_chapter_number") else (
        max([chapter["number"] for chapter in novel.get("chapters", []) if chapter.get("word_count", 0) > 0], default=0) + 1
    )
    return CompressionTester(db).test_novel(novel_id, next_chapter)


@router.get("/api/test-all-constraints")
def test_all_constraints() -> dict:
    """A/B test constraint compression across all novels."""
    from novel_writer.stations.novel.compression_tester import CompressionTester

    return CompressionTester(_db()).test_all_novels()


@router.post("/api/novels/{novel_id}/constraint-collapse")
def constraint_collapse(novel_id: str, data: dict) -> dict:
    """Narrow scene choices through hard, character, structure, and theme constraints."""
    scene = text_field(data, "scene_description") or text_field(data, "scene")
    choices = data.get("choices", [])
    if not scene or len(choices) < 2:
        raise HTTPException(400, "Need scene_description and at least 2 choices")

    db = _db()
    eliminated = []
    survivors = list(choices)

    chars = db.get_character_state(novel_id)
    active_foreshadowing = db.get_active_foreshadowing(novel_id)

    for choice in list(survivors):
        for char in chars[-5:]:
            if char.get("physical_state") == "injured" and (
                "战斗" in choice or "打" in choice or "杀" in choice
            ):
                if char["char_name"] in choice:
                    eliminated.append(
                        {
                            "choice": choice,
                            "reason": f"{char['char_name']}受伤，无法执行需要体力的选择",
                            "round": 1,
                        }
                    )
                    survivors.remove(choice)
                    break

    if survivors and len(survivors) > 1:
        for choice in list(survivors):
            if "原谅" in choice and any("愤怒" in (char.get("emotion") or "") for char in chars[-3:]):
                eliminated.append({"choice": choice, "reason": "角色当前情绪为愤怒，不宜立即原谅", "round": 2})
                survivors.remove(choice)

    if survivors and len(survivors) > 1 and active_foreshadowing:
        overdue = [item for item in active_foreshadowing if item.get("status") == "overdue"]
        if overdue:
            for choice in list(survivors):
                if not any(item["description"][:10] in choice for item in overdue):
                    eliminated.append(
                        {"choice": choice, "reason": f"有{len(overdue)}个过期伏笔未收，该选择未涉及回收", "round": 3}
                    )
                    survivors.remove(choice)

    if survivors and len(survivors) > 1:
        unsaid = db.get_unsaid(novel_id)
        if unsaid:
            for choice in list(survivors):
                if any(item["entry"][:10] in choice for item in unsaid[-3:]):
                    eliminated.append({"choice": choice, "reason": "该选择可能过早揭示隐藏真相", "round": 4})
                    survivors.remove(choice)

    return {
        "original_choices": len(choices),
        "survivors": survivors,
        "eliminated": eliminated,
        "is_collapsed": len(survivors) == 1,
        "recommendation": survivors[0]
        if len(survivors) == 1
        else "多个选择存活，需要人类判断"
        if survivors
        else "所有选择被淘汰，放宽约束或重新定义场景",
    }
