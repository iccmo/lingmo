"""Enhanced EPUB + PDF export with TOC, cover, and metadata.

Published as separate endpoints to avoid breaking existing exports.
"""

import html as _html
import json
import re
from datetime import datetime, UTC
from pathlib import Path
from typing import Any


def _get_novel_with_chapters(db, novel_id: str) -> dict | None:
    """Fetch novel with generated chapters."""
    novel = db.get_novel(novel_id)
    if not novel:
        return None
    chapters = [c for c in novel.get("chapters", []) if c.get("word_count", 0) > 0]
    chapters.sort(key=lambda c: c.get("number", 0))
    return {"novel": novel, "chapters": chapters}


def _clean_content(content: str) -> str:
    """Strip markdown headers and normalize content for export."""
    content = re.sub(r'^#+\s*.*$', '', content, flags=re.MULTILINE).strip()
    return content


def _chapter_html(ch: dict, chapter_num_display: int = 0) -> str:
    """Render a single chapter as HTML."""
    num = ch.get("number", chapter_num_display)
    title = _html.escape(ch.get("title", f"第{num}章"))
    content = _clean_content(ch.get("content", ""))
    paragraphs = content.split('\n')
    body = '\n'.join(
        f'<p>{_html.escape(p.strip())}</p>' if p.strip() else '<br/>'
        for p in paragraphs
    )
    return f"""<section class="chapter" id="ch{num}">
<h2>第{num}章 {title}</h2>
{body}
</section>"""


def _cover_page(novel: dict) -> str:
    """Generate a cover/title page."""
    title = _html.escape(novel.get("title", "未命名"))
    author = _html.escape(novel.get("author", "灵墨AI"))
    genre = _html.escape(novel.get("genre", ""))
    synopsis = _html.escape(novel.get("synopsis", ""))
    date_str = datetime.now(UTC).strftime("%Y-%m-%d")
    return f"""<div class="cover">
<h1 class="cover-title">{title}</h1>
<p class="cover-author">{author}</p>
<p class="cover-genre">{genre}</p>
<p class="cover-date">{date_str}</p>
<div class="cover-synopsis">{synopsis}</div>
</div>"""


def _toc_html(chapters: list[dict]) -> str:
    """Generate table of contents."""
    items = '\n'.join(
        f'<li><a href="#ch{ch["number"]}">第{ch["number"]}章 {_html.escape(ch.get("title", ""))}</a></li>'
        for ch in chapters
    )
    return f"""<nav class="toc" epub:type="toc">
<h2>目录</h2>
<ol>{items}</ol>
</nav>"""


def _build_enhanced_epub(novel: dict, chapters: list[dict]) -> str:
    """Build enhanced EPUB with TOC and cover."""
    cover = _cover_page(novel)
    toc = _toc_html(chapters)
    body = '\n'.join(_chapter_html(ch, i + 1) for i, ch in enumerate(chapters))

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">
<head>
<meta charset="UTF-8"/>
<title>{_html.escape(novel.get('title', ''))}</title>
<meta name="author" content="{_html.escape(novel.get('author', '灵墨AI'))}"/>
<meta name="generator" content="灵墨·AI创作伴侣"/>
<style>
body {{ font-family: "Songti SC", "SimSun", serif; line-height: 1.8; margin: 2em; }}
.cover {{ text-align: center; padding: 4em 0; page-break-after: always; }}
.cover-title {{ font-size: 2em; font-weight: bold; margin-bottom: 0.5em; }}
.cover-author {{ font-size: 1.2em; color: #666; }}
.cover-genre {{ font-size: 0.9em; color: #999; margin-bottom: 2em; }}
.cover-date {{ font-size: 0.8em; color: #aaa; }}
.cover-synopsis {{ margin-top: 3em; font-style: italic; color: #666; max-width: 24em; margin-left: auto; margin-right: auto; }}
.toc {{ page-break-after: always; }}
.toc h2 {{ text-align: center; }}
.toc ol {{ list-style: none; padding: 0; }}
.toc li {{ margin: 0.5em 0; }}
.toc a {{ text-decoration: none; color: #333; }}
.chapter {{ page-break-before: always; margin-top: 2em; }}
.chapter h2 {{ text-align: center; font-size: 1.3em; margin-bottom: 1.5em; }}
p {{ text-indent: 2em; margin: 0.5em 0; }}
</style>
</head>
<body>
{cover}
{toc}
{body}
</body>
</html>"""


def _build_enhanced_pdf(novel: dict, chapters: list[dict]) -> str:
    """Build enhanced PDF with TOC and cover."""
    cover = _cover_page(novel)
    toc = _toc_html(chapters)
    body = '\n'.join(_chapter_html(ch, i + 1) for i, ch in enumerate(chapters))

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8"/>
<title>{_html.escape(novel.get('title', ''))}</title>
<style>
@page {{ size: A5; margin: 2cm; @bottom-center {{ content: counter(page); font-size: 9pt; }} }}
@page :first {{ @bottom-center {{ content: none; }} }}
body {{ font-family: "Songti SC", "SimSun", serif; line-height: 1.8; }}
.cover {{ text-align: center; padding: 4em 0; page-break-after: always; }}
.cover-title {{ font-size: 2em; font-weight: bold; margin-bottom: 0.5em; }}
.cover-author {{ font-size: 1.2em; color: #666; }}
.cover-genre {{ font-size: 0.9em; color: #999; margin-bottom: 2em; }}
.cover-date {{ font-size: 0.8em; color: #aaa; }}
.cover-synopsis {{ margin-top: 3em; font-style: italic; color: #666; max-width: 24em; margin-left: auto; margin-right: auto; }}
.toc {{ page-break-after: always; }}
.toc h2 {{ text-align: center; }}
.toc ol {{ list-style: none; padding: 0; }}
.toc li {{ margin: 0.5em 0; }}
.toc a {{ text-decoration: none; color: #333; }}
.chapter {{ page-break-before: always; margin-top: 2em; }}
.chapter h2 {{ text-align: center; font-size: 1.3em; margin-bottom: 1.5em; string-set: chapter-title content(); }}
@page chapter {{ @top-center {{ content: string(chapter-title); font-size: 9pt; color: #999; }} }}
p {{ text-indent: 2em; margin: 0.5em 0; }}
</style>
</head>
<body>
{cover}
{toc}
{body}
</body>
</html>"""


def export_enhanced_epub(db: Any, novel_id: str) -> str | None:
    """Generate enhanced EPUB HTML string."""
    data = _get_novel_with_chapters(db, novel_id)
    if not data:
        return None
    return _build_enhanced_epub(data["novel"], data["chapters"])


def export_enhanced_pdf(db: Any, novel_id: str) -> str | None:
    """Generate enhanced PDF HTML string."""
    data = _get_novel_with_chapters(db, novel_id)
    if not data:
        return None
    return _build_enhanced_pdf(data["novel"], data["chapters"])
