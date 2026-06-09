"""Import, clone, search, and external-analysis novel endpoints."""

from __future__ import annotations

import io
import json
import random
import re
import time
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from novel_writer.routers.deps import get_db
from novel_writer.routers.novel.chapter_metadata import metadata_for_content
from novel_writer.routers.novel.request_validation import text_field

router = APIRouter(tags=["imports"])


def _db():
    return get_db()


def _get_provider(novel_id: str | None = None):
    db = _db()
    provider_id = "deepseek"
    if novel_id:
        novel = db.get_novel(novel_id)
        if novel:
            provider_id = novel.get("provider_id", "deepseek")
    provider = db.get_provider(provider_id)
    if not provider or not provider.get("api_key"):
        for candidate in db.list_providers():
            if candidate.get("api_key"):
                provider = db.get_provider(candidate["id"])
                break
    return provider or {
        "id": "deepseek",
        "base_url": "https://api.deepseek.com",
        "api_key": "",
        "models": ["deepseek-v4-pro"],
    }


def _generator_for(novel_id: str):
    from novel_writer.config import Config
    from novel_writer.generator import Generator

    provider = _get_provider(novel_id)
    models = provider.get("models", ["deepseek-v4-pro"])
    cfg = Config(
        openai_api_key=provider.get("api_key", ""),
        openai_base_url=provider.get("base_url", ""),
        model=models[0] if isinstance(models, list) and models else "gpt-4o",
    )
    return Generator(cfg)


def _random_name(genre: str = "玄幻") -> str:
    from novel_writer.generator import random_protagonist_name

    name, _ = random_protagonist_name(genre)
    return name


@router.post("/api/novels/extract-dna")
def extract_narrative_dna(data: dict) -> dict:
    """Extract reusable narrative DNA from an existing novel."""
    db = _db()
    source_id = data.get("source_novel_id", "")
    if not source_id:
        raise HTTPException(400, "source_novel_id required")
    novel = db.get_novel(source_id)
    if not novel:
        raise HTTPException(404)

    generated_chapters = [
        chapter for chapter in novel.get("chapters", []) if chapter.get("word_count", 0) > 0
    ]
    if len(generated_chapters) < 3:
        raise HTTPException(400, "源小说至少3章")

    samples = [
        {
            "title": chapter["title"],
            "word_count": chapter["word_count"],
            "content": chapter.get("content", "")[:800],
        }
        for chapter in generated_chapters[:5]
    ]
    dna = _generator_for(source_id).extract_narrative_dna(samples, data.get("target_genre", ""))

    dna_dir = Path("data") / "narrative_dna"
    dna_dir.mkdir(exist_ok=True)
    dna_path = dna_dir / f"{source_id}.json"
    dna_path.write_text(json.dumps(dna, ensure_ascii=False, indent=2))

    target_id = data.get("target_novel_id", "")
    if target_id and dna and "error" not in dna:
        style_data = db.get_style_profile(target_id)
        if style_data:
            rules = style_data.get("special_rules", [])
            if "structure_type" in dna:
                rules.append(f"叙事结构类型：{dna.get('structure_type', '')}")
            if "hook_pattern" in dna:
                rules.append(f"钩子模式：{dna.get('hook_pattern', '')}")
            style_data["special_rules"] = rules
            db.save_style_profile(target_id, style_data)

    return {
        "dna": dna,
        "saved_to": f"data/narrative_dna/{source_id}.json",
        "applied_to": target_id if target_id else None,
    }


@router.post("/api/novels/{novel_id}/import-chapters")
def import_chapters(novel_id: str, data: dict) -> dict:
    """Import chapters from plain text separated by --- blocks."""
    db = _db()
    if not db.get_novel(novel_id):
        raise HTTPException(404)
    text = text_field(data, "text")
    if not text:
        raise HTTPException(400, "text required")

    imported = 0
    for index, block in enumerate(text.split("\n---\n"), 1):
        lines = block.strip().split("\n")
        title = lines[0].strip() if lines else f"第{index}章"
        content = "\n".join(lines[1:]).strip() if len(lines) > 1 else ""
        if content:
            metadata = metadata_for_content(
                {"number": index, "title": title, "content": "", "summary": ""},
                content,
            )
            db.add_chapter(
                novel_id=novel_id,
                number=index,
                title=title,
                word_count=metadata["word_count"],
                summary=metadata["summary"],
                content=metadata["content"],
                narrative_facts=metadata["narrative_facts"],
            )
            imported += 1
    return {"imported": imported, "novel_id": novel_id}


@router.post("/api/novels/search")
def search_novels(data: dict) -> dict:
    """Full-text search across title, synopsis, chapter titles, and chapter content."""
    query = text_field(data, "q")
    if not query:
        return {"results": []}

    results = []
    for novel in _db().list_novels():
        score = 0
        if query in novel["title"]:
            score += 100
        if query in novel.get("synopsis", ""):
            score += 50
        for chapter in novel.get("chapters", []):
            if query in chapter.get("title", ""):
                score += 20
            if query in (chapter.get("content", "") or "")[:5000]:
                score += 5
        if score > 0:
            results.append({
                "id": novel["id"],
                "title": novel["title"],
                "score": score,
                "genre": novel.get("genre", ""),
            })

    results.sort(key=lambda item: item["score"], reverse=True)
    return {"results": results[:20]}


@router.get("/api/market-trends")
def market_trends() -> dict:
    """Return static market trend suggestions used by the product UI."""
    return {
        "hot_genres": [
            {"genre": "AI科幻", "reason": "AI话题全民关注，番茄搜索量月增300%", "competition": "低（同质化少）"},
            {"genre": "官场反腐", "reason": "现实题材政策扶持+读者偏好深度内容", "competition": "中"},
            {"genre": "悬疑推理", "reason": "短剧改编需求旺盛，悬疑类转化率最高", "competition": "高"},
            {"genre": "女性职场", "reason": "她经济持续升温，轻治愈+成长线", "competition": "低"},
            {"genre": "末世生存", "reason": "全球不确定性推高生存类阅读，硬核末世缺口大", "competition": "中"},
        ],
        "recommended_combos": [
            {"genre": "AI科幻", "voice": "刘慈欣", "question": "当AI比人类更懂爱，人类还剩下什么"},
            {"genre": "官场反腐", "voice": "东野圭吾", "question": "一个好人能在坏制度里坚持多久"},
            {"genre": "悬疑推理", "voice": "余华", "question": "如果真相会让你恨自己，你还想知道吗"},
        ],
        "updated": datetime.now().isoformat(),
    }


@router.post("/api/novels/{novel_id}/clone")
def clone_novel(novel_id: str, data: dict | None = None) -> dict:
    """Clone a novel world, characters, factions, outline, and style profile."""
    db = _db()
    original = db.get_novel(novel_id)
    if not original:
        raise HTTPException(404, "Original novel not found")

    data = data or {}
    new_genre = data.get("genre", original.get("genre", "玄幻"))
    new_title = data.get("title", original.get("title", "") + "（副本）")
    new_name = text_field(data, "protagonist_name") or (
        _random_name(new_genre) if new_genre != original.get("genre") else ""
    )

    for _ in range(10):
        suffix = str(random.randint(10, 99))
        new_id = f"{novel_id}-copy-{suffix}"
        if not db.get_novel(new_id):
            break
    else:
        new_id = f"{novel_id}-copy-{int(time.time())}"

    db.create_novel(
        id=new_id,
        title=new_title,
        author=original.get("author", "AI"),
        synopsis=original.get("synopsis", ""),
        genre=new_genre,
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

    for character in original.get("characters", []):
        if character.get("char_key") == "protagonist":
            continue
        try:
            with db.conn() as conn:
                conn.execute(
                    """INSERT INTO characters (novel_id,char_key,name,role,personality,background,power_level,status)
                    VALUES (?,?,?,?,?,?,?,?)""",
                    (
                        new_id,
                        character.get("char_key", ""),
                        character.get("name", ""),
                        character.get("role", "配角"),
                        character.get("personality", ""),
                        character.get("background", ""),
                        character.get("power_level", ""),
                        character.get("status", "alive"),
                    ),
                )
        except Exception:
            pass

    for faction in original.get("factions", []):
        try:
            with db.conn() as conn:
                conn.execute(
                    "INSERT INTO factions (novel_id,name,description,leader,sort_order) VALUES (?,?,?,?,?)",
                    (
                        new_id,
                        faction.get("name", ""),
                        faction.get("description", ""),
                        faction.get("leader", ""),
                        faction.get("sort_order", 0),
                    ),
                )
        except Exception:
            pass

    for chapter in original.get("chapters", []):
        if chapter.get("word_count", 0) == 0:
            try:
                with db.conn() as conn:
                    conn.execute(
                        "INSERT INTO chapters (novel_id,number,title,summary,word_count) VALUES (?,?,?,?,0)",
                        (new_id, chapter.get("number", 0), chapter.get("title", ""), chapter.get("summary", "")),
                    )
            except Exception:
                pass

    for plot_point in original.get("plot_points", []):
        try:
            with db.conn() as conn:
                conn.execute(
                    "INSERT INTO plot_points (novel_id,type,content,is_resolved,sort_order) VALUES (?,?,?,?,?)",
                    (
                        new_id,
                        plot_point.get("type", "plot"),
                        plot_point.get("content", ""),
                        plot_point.get("is_resolved", 0),
                        plot_point.get("sort_order", 0),
                    ),
                )
        except Exception:
            pass

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


@router.post("/api/novels/import")
async def import_novel(
    title: str = Form(...),
    genre: str = Form("玄幻"),
    file: UploadFile = File(...),
):
    """Import a novel from an external TXT or EPUB file."""
    db = _db()
    if not title.strip():
        raise HTTPException(400, "title required")

    raw_bytes = await file.read()
    filename = (file.filename or "").lower()

    if filename.endswith(".epub"):
        try:
            import ebooklib
            from ebooklib import epub
        except ImportError:
            raise HTTPException(500, "ebooklib not installed. Run: pip install ebooklib")

        book = epub.read_epub(io.BytesIO(raw_bytes))
        chapters_data: list[tuple[str, str]] = []
        toc_items: list = []
        for item in book.toc:
            if isinstance(item, tuple):
                _extract_toc_items(item, toc_items)
            elif hasattr(item, "get_name"):
                toc_items.append(item)

        if not toc_items:
            toc_items = [doc for doc in book.get_items_of_type(ebooklib.ITEM_DOCUMENT)]

        for item in toc_items:
            try:
                item_content = item.get_content()
                html_content = item_content.decode("utf-8", errors="ignore") if isinstance(item_content, bytes) else item_content
                text = re.sub(r"<[^>]+>", "", html_content)
                text = re.sub(r"\n{3,}", "\n\n", text).strip()
                if text and len(text) > 50:
                    title_line = ""
                    for line in text.split("\n"):
                        stripped = line.strip()
                        if stripped and len(stripped) < 50:
                            title_line = stripped
                            break
                    chapters_data.append((title_line or f"第{len(chapters_data) + 1}章", text))
            except Exception:
                continue
    elif filename.endswith(".txt"):
        chapters_data = _detect_chapters_from_text(raw_bytes.decode("utf-8", errors="ignore"))
    else:
        raise HTTPException(400, "Unsupported file format. Please upload .txt or .epub")

    if not chapters_data:
        raise HTTPException(400, "No chapter content found in the uploaded file")

    imported_id = re.sub(r"[^a-z0-9-]", "", title.lower().replace(" ", "-")[:40])
    if not imported_id:
        from uuid import uuid4

        imported_id = uuid4().hex[:12]

    base_id = imported_id
    counter = 1
    while db.get_novel(imported_id):
        imported_id = f"{base_id}-{counter}"
        counter += 1

    db.create_novel(id=imported_id, title=title.strip(), genre=genre, synopsis="")

    for index, (chapter_title, chapter_content) in enumerate(chapters_data, 1):
        clean_title = chapter_title or f"第{index}章"
        metadata = metadata_for_content(
            {"number": index, "title": clean_title, "content": "", "summary": ""},
            chapter_content,
        )
        db.add_chapter(
            novel_id=imported_id,
            number=index,
            title=clean_title,
            word_count=metadata["word_count"],
            summary=metadata["summary"].replace("\n", " "),
            content=metadata["content"],
            narrative_facts=metadata["narrative_facts"],
            ending_hook="",
        )

    return {
        "novel_id": imported_id,
        "title": title.strip(),
        "chapters_imported": len(chapters_data),
        "total_words": sum(len(chapter[1]) for chapter in chapters_data),
    }


def _extract_toc_items(item, result: list):
    """Recursively extract items from EPUB TOC tuples."""
    if isinstance(item, tuple) and len(item) >= 2:
        if isinstance(item[1], list):
            for sub_item in item[1]:
                _extract_toc_items(sub_item, result)
        elif hasattr(item[1], "get_name"):
            result.append(item[1])
    elif hasattr(item, "get_name"):
        result.append(item)


def _detect_chapters_from_text(text: str) -> list[tuple[str, str]]:
    """Detect chapter breaks from plain text and return [(title, content), ...]."""
    patterns = [
        r"(第[一二三四五六七八九十百千\d]+[章节回卷部集幕])",
        r"(Chapter\s+\d+)",
        r"(CHAPTER\s+\d+)",
        r"(第\d+[章节回卷部集幕])",
    ]

    lines = text.split("\n")
    chapter_indices = []
    for index, line in enumerate(lines):
        stripped = line.strip()
        for pattern in patterns:
            if re.match(pattern, stripped):
                chapter_indices.append(index)
                break

    if len(chapter_indices) < 2:
        return [("", text.strip())]

    chapters = []
    for index, line_index in enumerate(chapter_indices):
        title = lines[line_index].strip()
        start = line_index + 1
        end = chapter_indices[index + 1] if index + 1 < len(chapter_indices) else len(lines)
        content = "\n".join(lines[start:end]).strip()
        if content:
            chapters.append((title, content))

    return chapters
