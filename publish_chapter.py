#!/usr/bin/env python3
"""番茄小说自动发布器 — 独立命令行脚本

用法:
    # 发布单章
    .venv/bin/python publish_chapter.py 1

    # 发布多章
    .venv/bin/python publish_chapter.py 1 2 3

    # 发布全部待发章节
    .venv/bin/python publish_chapter.py --all

    # 干跑(不实际发布, 只打印流程)
    .venv/bin/python publish_chapter.py --dry-run 1

    # 列出发布状态
    .venv/bin/python publish_chapter.py --status

依赖:
    pip install playwright
    playwright install chromium
"""
import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from novel_writer.database import Database
from novel_writer.publisher import FanqiePlatform, PublishResult

# ── Config ──────────────────────────────────────────────────────

BOOK_ID = "7641988849018620952"
BOOK_TITLE = "江临棋局"
AUTH_PATH = "data/auth/fanqie.json"
STATUS_PATH = "data/publish_status.json"

# Default novel_id — can be overridden via --novel-id
_NOVEL_ID = "qingyun-road"


def _get_novel_id() -> str:
    """Allow CLI override via env var during testing."""
    return os.environ.get("PUBLISH_NOVEL_ID", _NOVEL_ID)


def load_status() -> dict:
    """Load publish status from JSON."""
    path = Path(STATUS_PATH)
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return {}


def save_status(status: dict):
    """Save publish status to JSON."""
    path = Path(STATUS_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(status, f, ensure_ascii=False, indent=2)


def show_status():
    """Print current publish status."""
    status = load_status()
    novel = status.get(BOOK_TITLE, {})
    published = novel.get("published", [])
    pending = novel.get("pending", [])
    chapters = novel.get("chapters", {})

    print(f"\n📖 {BOOK_TITLE} (ID: {novel.get('book_id', BOOK_ID)})")
    print(f"   已发布: {sorted(published) if published else '无'}")
    print(f"   待发布: {sorted(pending) if pending else '无'}")
    print()

    if chapters:
        for num in sorted(chapters.keys(), key=int):
            ch = chapters[num]
            mark = "✅" if ch.get("published") else "⏳"
            print(f"   {mark} 第{num}章: {ch.get('title', '?')}")
    print()


async def publish_chapter(chapter_num: int, dry_run: bool = False, novel_id: str = "") -> PublishResult:
    """Publish a single chapter to 番茄小说."""
    if not novel_id:
        novel_id = _get_novel_id()

    db = Database()
    chapter = db.get_chapter(novel_id, chapter_num)
    if not chapter:
        return PublishResult(False, "fanqie", chapter_num,
                             error=f"Chapter {chapter_num} not found in DB")

    # Clean title
    clean_title = chapter["title"]
    for prefix in ["# ", "## ", "### ", "#### "]:
        if clean_title.startswith(prefix):
            clean_title = clean_title[len(prefix):]
    clean_title = clean_title.strip().replace("\n", "")
    body = chapter.get("content", "")
    # 去掉正文中的标题行（已单独填在标题输入框）
    import re
    body = re.sub(r'^#\s*第\d+[章節]\s*[：:\s]*.*\n', '', body).strip()
    body = re.sub(r'^#\s*[^#\n]+\n', '', body).strip()

    print(f"\n{'='*60}")
    print(f"📝 第{chapter_num}章: {clean_title}")
    print(f"   字数: {chapter.get('word_count', '?')}")
    print(f"   正文前100字: {body[:100].replace(chr(10), ' ')}...")
    print(f"{'='*60}")

    if dry_run:
        print("🔍 [DRY RUN] 不会实际发布，仅验证流程。")
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            return PublishResult(True, "fanqie", chapter_num,
                                 error="DRY RUN — Playwright not installed")
        async with async_playwright() as p:
            cdp_url = os.environ.get("CDP_URL", "")
            if cdp_url:
                browser = await p.chromium.connect_over_cdp(cdp_url)
                context = browser.contexts[0] if browser.contexts else await browser.new_context()
            else:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(viewport={"width": 1280, "height": 800})
            page = await context.new_page()
            platform = FanqiePlatform()
            smoke = await platform.smoke_test(page)
            print(f"   Smoke test: {'✅' if smoke else '❌'}")
            auth_ok = await platform.login(page, AUTH_PATH)
            print(f"   Auth check: {'✅' if auth_ok else '❌'}")
            await browser.close()
        # Dry run: report actual result, not always True
        if not smoke:
            return PublishResult(False, "fanqie", chapter_num,
                                error="DRY RUN — smoke test failed (page did not load)")
        return PublishResult(True, "fanqie", chapter_num,
                             error="DRY RUN — no actual publish")

    # Real publish
    t0 = time.time()
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return PublishResult(False, "fanqie", chapter_num,
                             error="Playwright not installed")

    async with async_playwright() as p:
        cdp_url = os.environ.get("CDP_URL", "")
        if cdp_url:
            browser = await p.chromium.connect_over_cdp(cdp_url)
            context = browser.contexts[0] if browser.contexts else await browser.new_context()
        else:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(viewport={"width": 1280, "height": 800})
        page = await context.new_page()
        platform = FanqiePlatform()

        try:
            logged_in = await platform.login(page, AUTH_PATH)
            if not logged_in:
                await browser.close()
                return PublishResult(False, "fanqie", chapter_num, error="Login failed")

            result = await platform.upload_chapter(page, clean_title, body, chapter_num)
            result.duration_seconds = round(time.time() - t0, 1)

            if result.success:
                db.record_publish(chapter["id"], "fanqie", True,
                                  result.url, "", result.screenshot_path)
                db.log(novel_id, "publish.success", {"chapter": chapter_num})

            # Update status JSON
            status = load_status()
            novel = status.setdefault(BOOK_TITLE, {"book_id": BOOK_ID, "published": [], "pending": [], "chapters": {}})
            if result.success:
                pending_list = novel.get("pending", [])
                if chapter_num in pending_list:
                    pending_list.remove(chapter_num)
                published_list = novel.setdefault("published", [])
                if chapter_num not in published_list:
                    published_list.append(chapter_num)
                novel.setdefault("chapters", {})[str(chapter_num)] = {
                    "title": clean_title,
                    "published": True,
                    "published_at": time.strftime("%Y-%m-%d %H:%M:%S")
                }
            save_status(status)

            return result

        finally:
            await browser.close()


async def main():
    parser = argparse.ArgumentParser(
        description="番茄小说自动发布器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s 1              发布第1章
  %(prog)s 1 2 3          连续发布第1-3章
  %(prog)s --all           发布全部待发章节
  %(prog)s --dry-run 1     干跑验证(不实际发布)
  %(prog)s --status        查看发布状态
        """
    )
    parser.add_argument("chapters", nargs="*", type=int, help="要发布的章节号")
    parser.add_argument("--all", action="store_true", help="发布全部待发章节")
    parser.add_argument("--dry-run", action="store_true", help="干跑模式, 不实际发布")
    parser.add_argument("--status", action="store_true", help="查看发布状态")
    parser.add_argument("--watch", action="store_true", help="监控发布状态(配合--status)")
    parser.add_argument("--delay", type=int, default=30,
                        help="章节间延迟秒数 (默认30, 避免触发风控)")
    parser.add_argument("--novel-id", default=_NOVEL_ID,
                        help=f"小说数据库ID (默认: {_NOVEL_ID})")

    args = parser.parse_args()

    # ── Status mode ──
    if args.status:
        if args.watch:
            print("📡 监控发布状态 (Ctrl+C 退出)...")
            try:
                while True:
                    show_status()
                    await asyncio.sleep(30)
            except KeyboardInterrupt:
                print("\n👋 退出监控")
        else:
            show_status()
        return

    # ── Determine chapters to publish ──
    chapters_to_publish = []
    if args.all:
        status = load_status()
        novel = status.get(BOOK_TITLE, {})
        chapters_to_publish = sorted(novel.get("pending", []))
        if not chapters_to_publish:
            print("✅ 没有待发布章节!")
            return
        print(f"📋 待发布 {len(chapters_to_publish)} 章: {chapters_to_publish}")
    elif args.chapters:
        chapters_to_publish = args.chapters
    else:
        parser.print_help()
        return

    # ── Publish loop ──
    results = []
    novel_id = args.novel_id
    for i, ch_num in enumerate(chapters_to_publish):
        if i > 0:
            print(f"\n⏳ 等待 {args.delay}s (避免触发风控)...")
            await asyncio.sleep(args.delay)

        result = await publish_chapter(ch_num, dry_run=args.dry_run, novel_id=novel_id)
        results.append(result)

        if result.success:
            print(f"✅ 第{ch_num}章 发布成功! ({result.duration_seconds:.0f}s)")
        else:
            print(f"❌ 第{ch_num}章 发布失败: {result.error[:200]}")

    # ── Summary ──
    print(f"\n{'='*60}")
    print("📊 发布总结")
    print(f"   成功: {sum(1 for r in results if r.success)}/{len(results)}")
    if not args.dry_run:
        show_status()


if __name__ == "__main__":
    asyncio.run(main())
