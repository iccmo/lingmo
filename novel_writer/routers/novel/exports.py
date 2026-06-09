"""Novel export endpoints."""

from __future__ import annotations

import html as _html
import json
import os
import re
import subprocess
import tempfile
from urllib.parse import quote

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, PlainTextResponse, Response

from novel_writer.exporter import export_enhanced_epub, export_enhanced_pdf
from novel_writer.routers.deps import get_db

router = APIRouter(tags=["exports"])


def _db():
    return get_db()


def _generated_chapters_with_content(novel_id: str, novel: dict) -> list[dict]:
    chapters = [dict(c) for c in novel.get("chapters", []) if c.get("word_count", 0) > 0]
    with _db().conn() as conn:
        for chapter in chapters:
            row = conn.execute(
                "SELECT content FROM chapters WHERE novel_id=? AND number=?",
                (novel_id, chapter["number"]),
            ).fetchone()
            chapter["content"] = row["content"] if row else ""
    return chapters


def _chapter_body(content: str) -> str:
    return re.sub(r"^#+\s*.*$", "", content, flags=re.MULTILINE).strip()


def _book_html(novel: dict, chapters: list[dict], *, print_css: bool = False) -> str:
    if print_css:
        style = """
  @page { size: A4; margin: 2cm; }
  body { font-family: "Noto Serif CJK SC", "Songti SC", "SimSun", serif; line-height: 2; font-size: 12pt; color: #333; }
  h1 { text-align: center; font-size: 18pt; margin-bottom: 0.5em; page-break-before: avoid; }
  h2 { margin-top: 2em; font-size: 14pt; page-break-before: always; page-break-after: avoid; }
  .synopsis { font-style: italic; color: #666; text-align: center; margin-bottom: 2em; }
  p { text-indent: 2em; margin: 0.5em 0; }
  @media print { body { font-size: 11pt; } }
"""
    else:
        style = "body{font-family:serif;line-height:1.8;margin:2em}h1{text-align:center}h2{margin-top:2em}.synopsis{font-style:italic;color:#666}"

    parts = [
        f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>{_html.escape(novel["title"])}</title>
<style>{style}</style></head>
<body>
<h1>{_html.escape(novel["title"])}</h1>
<p class="synopsis">{_html.escape(novel.get("synopsis", ""))}</p>"""
    ]
    for chapter in chapters:
        parts.append(f"<h2>第{chapter['number']}章 {_html.escape(chapter['title'])}</h2>")
        for para in _chapter_body(chapter.get("content", "")).split("\n"):
            if para.strip():
                parts.append(f"<p>{_html.escape(para.strip())}</p>")
    parts.append("</body></html>")
    return "\n".join(parts)


@router.get("/api/novels/{novel_id}/export-full")
def export_full_novel(novel_id: str):
    """Export complete novel data for migration between instances."""
    db = _db()
    novel = db.get_novel(novel_id)
    if not novel:
        raise HTTPException(404)
    chapters = _generated_chapters_with_content(novel_id, novel)
    data = {
        "novel": {k: v for k, v in novel.items() if k != "chapters"},
        "chapters": [
            {
                "number": c["number"],
                "title": c["title"],
                "content": c.get("content", ""),
                "word_count": c["word_count"],
                "quality_score": c.get("quality_score"),
                "generated_at": c.get("generated_at"),
            }
            for c in chapters
        ],
        "style_profile": db.get_style_profile(novel_id),
        "characters": novel.get("characters", []),
        "factions": novel.get("factions", []),
        "versions": {str(c["number"]): db.get_chapter_versions(novel_id, c["number"]) for c in chapters},
    }
    return PlainTextResponse(
        json.dumps(data, ensure_ascii=False, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename={novel_id}_full.json"},
    )


@router.get("/api/novels/{novel_id}/export-epub")
def export_epub(novel_id: str):
    """Export HTML content suitable for EPUB workflows."""
    novel = _db().get_novel(novel_id)
    if not novel:
        raise HTTPException(404)
    chapters = _generated_chapters_with_content(novel_id, novel)
    if not chapters:
        raise HTTPException(400, "No chapters")
    safe_fn = quote(f"{novel['title']}_{len(chapters)}chapters.html")
    return PlainTextResponse(
        _book_html(novel, chapters),
        media_type="text/html; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{safe_fn}"},
    )


@router.get("/api/novels/{novel_id}/export-pdf")
def export_pdf(novel_id: str):
    """Export PDF when a renderer is installed, otherwise return print-ready HTML."""
    novel = _db().get_novel(novel_id)
    if not novel:
        raise HTTPException(404)
    chapters = _generated_chapters_with_content(novel_id, novel)
    if not chapters:
        raise HTTPException(400, "No chapters")

    html = _book_html(novel, chapters, print_css=True)
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
        fn = quote(f"{novel['title']}_{len(chapters)}chapters.pdf")
        return Response(
            pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename*=UTF-8''{fn}"},
        )

    fn = quote(f"{novel['title']}_{len(chapters)}chapters_pdf.html")
    return PlainTextResponse(
        html,
        media_type="text/html; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{fn}"},
    )


@router.get("/api/novels/{novel_id}/export-mobi")
def export_mobi(novel_id: str):
    """Export MOBI through Calibre ebook-convert."""
    novel = _db().get_novel(novel_id)
    if not novel:
        raise HTTPException(404)
    chapters = _generated_chapters_with_content(novel_id, novel)
    if not chapters:
        raise HTTPException(400, "No chapters")

    html = _book_html(novel, chapters)
    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False, encoding="utf-8") as file:
            file.write(html)
            html_path = file.name

        mobi_path = html_path.replace(".html", ".mobi")
        result = subprocess.run(
            ["ebook-convert", html_path, mobi_path],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )

        if result.returncode == 0 and os.path.exists(mobi_path):
            with open(mobi_path, "rb") as mobi_file:
                mobi_bytes = mobi_file.read()
            fn = quote(f"{novel['title']}_{len(chapters)}chapters.mobi")
            return Response(
                mobi_bytes,
                media_type="application/x-mobipocket-ebook",
                headers={"Content-Disposition": f"attachment; filename*=UTF-8''{fn}"},
            )
    except FileNotFoundError:
        pass
    finally:
        for path in (locals().get("html_path"), locals().get("mobi_path")):
            if path and os.path.exists(path):
                os.unlink(path)

    raise HTTPException(501, "Install Calibre (https://calibre-ebook.com) for MOBI export. Run: brew install calibre")


@router.get("/api/novels/{novel_id}/export-enhanced-epub")
def export_enhanced_epub_endpoint(novel_id: str):
    """Export enhanced EPUB HTML with table of contents, cover, and metadata."""
    db = _db()
    html = export_enhanced_epub(db, novel_id)
    if html is None:
        raise HTTPException(404, "Novel not found or no chapters")
    novel = db.get_novel(novel_id)
    fn = quote(f"{novel['title']}_enhanced.epub")
    return HTMLResponse(html, headers={"Content-Disposition": f"attachment; filename*=UTF-8''{fn}"})


@router.get("/api/novels/{novel_id}/export-enhanced-pdf")
def export_enhanced_pdf_endpoint(novel_id: str):
    """Export enhanced PDF HTML with table of contents, page numbers, and cover."""
    db = _db()
    html = export_enhanced_pdf(db, novel_id)
    if html is None:
        raise HTTPException(404, "Novel not found or no chapters")
    novel = db.get_novel(novel_id)
    fn = quote(f"{novel['title']}_enhanced.pdf")
    return HTMLResponse(
        html,
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{fn}",
            "Content-Type": "application/pdf",
        },
    )


@router.get("/api/novels/{novel_id}/chapters/{chapter_num}/export")
def export_chapter(novel_id: str, chapter_num: int):
    chapter = _db().get_chapter(novel_id, chapter_num)
    if not chapter:
        raise HTTPException(404, "Not found")
    content = f"{chapter['title']}\n\n{chapter.get('content', '')}"
    return PlainTextResponse(
        content,
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename=chapter_{chapter_num}.txt"},
    )


@router.get("/api/novels/{novel_id}/export")
def export_novel(novel_id: str, fmt: str = "txt"):
    """Export entire novel as TXT or Markdown."""
    novel = _db().get_novel(novel_id)
    if not novel:
        raise HTTPException(404, "Novel not found")
    chapters = _generated_chapters_with_content(novel_id, novel)
    if not chapters:
        raise HTTPException(400, "No generated chapters")

    if fmt == "md":
        lines = [f"# {novel['title']}", f"\n_{novel.get('synopsis', '')}_\n"]
        for chapter in chapters:
            lines.append(f"## 第{chapter['number']}章 {chapter['title']}\n")
            lines.append(chapter.get("content", ""))
            lines.append("")
        content = "\n\n".join(lines)
        media = "text/markdown; charset=utf-8"
    else:
        lines = [novel["title"], novel.get("synopsis", ""), ""]
        for chapter in chapters:
            lines.append(f"\n{'-' * 40}")
            lines.append(f"第{chapter['number']}章 {chapter['title']}")
            lines.append(f"{'-' * 40}\n")
            lines.append(_chapter_body(chapter.get("content", "")))
        content = "\n".join(lines)
        media = "text/plain; charset=utf-8"

    fn = quote(f"{novel['title']}_{len(chapters)}chapters.{fmt}")
    return PlainTextResponse(
        content,
        media_type=media,
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{fn}"},
    )
