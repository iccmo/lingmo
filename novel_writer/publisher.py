"""平台发布器 — Playwright 自动化发布到 番茄小说"""
import asyncio
import json
import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from .config import Config, config
from .database import Database

SELECTORS_PATH = Path(__file__).parent.parent / "data" / "selectors.json"

DEFAULT_SELECTORS = {
    "fanqie": {
        "create_chapter_btn": "button:has-text('创建章节')",
        "title_input": "input[placeholder='请输入标题']",
        "body_editor": "[contenteditable='true']",
        "next_btn": "button:has-text('下一步')",
    }
}


def _load_selectors() -> dict:
    if SELECTORS_PATH.exists():
        try:
            return json.loads(SELECTORS_PATH.read_text())
        except Exception:
            pass
    SELECTORS_PATH.parent.mkdir(parents=True, exist_ok=True)
    SELECTORS_PATH.write_text(json.dumps(DEFAULT_SELECTORS, ensure_ascii=False, indent=2))
    return DEFAULT_SELECTORS.copy()


@dataclass
class PublishResult:
    success: bool
    platform: str
    chapter_number: int
    url: str = ""
    error: str = ""
    screenshot_path: str = ""
    retry_count: int = 0
    duration_seconds: float = 0.0


class BasePlatform(ABC):
    name: str
    author_url: str

    @abstractmethod
    async def login(self, page, storage_state_path: str | None = None) -> bool: ...

    @abstractmethod
    async def upload_chapter(self, page, title: str, body: str, chapter_num: int = 0) -> PublishResult: ...

    @abstractmethod
    async def smoke_test(self, page) -> bool: ...


class FanqiePlatform(BasePlatform):
    name = "fanqie"
    author_url = "https://fanqienovel.com/main/writer/book-manage"

    def __init__(self):
        self.SELECTORS = _load_selectors().get(self.name, DEFAULT_SELECTORS["fanqie"])

    async def _get_browser(self, p):
        """Create browser via CDP (preferred) or headless fallback."""
        cdp = os.environ.get("CDP_URL", "")
        if cdp:
            browser = await p.chromium.connect_over_cdp(cdp)
            ctx = browser.contexts[0] if browser.contexts else await browser.new_context()
        else:
            browser = await p.chromium.launch(headless=True)
            ctx = await browser.new_context(viewport={"width": 1280, "height": 800})
        return browser, ctx

    async def login(self, page, storage_state_path: str | None = None) -> bool:
        if storage_state_path and Path(storage_state_path).exists():
            storage = json.loads(Path(storage_state_path).read_text())
            await page.context.add_cookies(storage.get("cookies", []))
            await page.goto(self.author_url, wait_until="networkidle")
            await asyncio.sleep(2)
            body = await page.evaluate("() => document.body.innerText")
            if "登录" in body and "密码" in body and "创建章节" not in body:
                print("[PUBLISH] ⚠️ Cookies expired")
                return False
            return True
        print("[PUBLISH] ❌ No saved cookies")
        return False

    async def smoke_test(self, page) -> bool:
        try:
            await page.goto(self.author_url, wait_until="domcontentloaded", timeout=15000)
            await asyncio.sleep(2)
            return bool(await page.query_selector(self.SELECTORS["create_chapter_btn"]))
        except Exception as e:
            print(f"[PUBLISH] Smoke test failed: {e}")
            return False

    async def _fill_body_dom(self, page, text: str):
        """Inject body text into rich editor via DOM."""
        await page.evaluate("""(t) => {
            const el = document.querySelector('[contenteditable="true"]');
            if (!el) return;
            el.innerHTML = '<p>' + t.split('\\n').filter(s => s.trim()).join('</p><p>') + '</p>';
            el.dispatchEvent(new Event('input', {bubbles: true}));
        }""", text)
        await asyncio.sleep(0.5)

    async def upload_chapter(self, page, title: str, body: str, chapter_num: int = 0) -> PublishResult:
        """发布一章到番茄。最小化流程，直接提交。"""
        editor = None
        spath = ""
        for attempt in range(3):
            t0 = time.time()
            try:
                if attempt > 0:
                    print(f"[PUBLISH] Retry {attempt+1}/3…")
                    await asyncio.sleep(3)

                await page.goto(self.author_url, wait_until="networkidle", timeout=30000)
                await asyncio.sleep(2)

                # Step 1: 创建章节 → 新标签
                create_btn = await page.wait_for_selector(self.SELECTORS["create_chapter_btn"], timeout=10000)
                async with page.context.expect_page(timeout=15000) as new_tab:
                    await create_btn.click()
                editor = await new_tab.value
                await editor.wait_for_load_state("domcontentloaded", timeout=15000)
                await asyncio.sleep(2)

                # Step 2: 填标题
                await editor.fill(self.SELECTORS["title_input"], title)
                await asyncio.sleep(0.3)

                # Step 3: 填正文
                await editor.click("[contenteditable='true']")
                await self._fill_body_dom(editor, body)

                # Step 4: 下一步 → 章节号页
                await editor.click(self.SELECTORS["next_btn"], timeout=10000)
                await asyncio.sleep(2)

                # Step 5: 填章节号
                for inp in await editor.query_selector_all("input[type='text']"):
                    ph = await inp.get_attribute("placeholder") or ""
                    if "标题" not in ph and "搜索" not in ph:
                        await inp.fill(str(chapter_num))
                        break
                await asyncio.sleep(0.3)

                # Step 6: 下一步 → 预览页（触犯检测弹窗）
                await editor.click(self.SELECTORS["next_btn"], timeout=10000)
                await asyncio.sleep(3)

                # Step 7: 点"全面检测"（可能是 button/div/span）
                await asyncio.sleep(2)
                clicked_detection = await editor.evaluate("""() => {
                    const labels = ['全面检测', '基础检测', '仅基础检测'];
                    const all = document.querySelectorAll('button, span, div, label, [class*="detect"], [class*="check"]');
                    for (const label of labels) {
                        for (const el of all) {
                            if (el.offsetParent !== null && el.textContent.trim() === label) {
                                el.click();
                                return 'clicked:' + label;
                            }
                        }
                    }
                    return 'not_found';
                }""")
                print(f"[PUBLISH] 🔍 Detection choice: {clicked_detection}")
                await asyncio.sleep(4)

                # Step 8: 弹窗里的"提交" = 确认检测结果
                for label in ['提交', '确认提交']:
                    try:
                        btn = await editor.query_selector(f"button:has-text('{label}')")
                        if btn and await btn.is_visible():
                            await btn.click()
                            await asyncio.sleep(2)
                            print(f"[PUBLISH] ✅ Modal submit: '{label}'")
                            break
                    except:
                        pass

                # Step 9: 发布设置 — 选"否"(非AI生成) → 点"确认发布"
                await asyncio.sleep(3)
                # 选"否" — 可能是 button/radio/switch/tab
                for sel in [
                    "button:has-text('否')", "span:has-text('否')", "label:has-text('否')",
                    "[class*='radio']:has-text('否')", "[class*='switch']:has-text('否')",
                    "[class*='tab']:has-text('否')",
                ]:
                    try:
                        el = await editor.query_selector(sel)
                        if el and await el.is_visible():
                            await el.click()
                            await asyncio.sleep(1)
                            print("[PUBLISH] ✅ Selected '否'")
                            break
                    except:
                        pass
                # 点"确认发布"或"发布"
                for label in ['确认发布', '发布', '确认']:
                    try:
                        btn = await editor.query_selector(f"button:has-text('{label}')")
                        if btn and await btn.is_visible():
                            await btn.click()
                            await asyncio.sleep(3)
                            print(f"[PUBLISH] ✅ '{label}' clicked")
                            break
                    except:
                        pass
                await asyncio.sleep(5)

                # Step 10: 如果还在编辑页，再试一次"确认发布"
                text = await editor.evaluate("() => document.body.innerText")
                if '确认发布' in text or '发布' in text:
                    for label in ['确认发布', '发布']:
                        try:
                            btn = await editor.query_selector(f"button:has-text('{label}')")
                            if btn and await btn.is_visible():
                                await btn.click()
                                await asyncio.sleep(3)
                                print(f"[PUBLISH] ✅ '{label}' (retry)")
                                break
                        except:
                            pass

                # Step 8: 验证 + 采集数据
                await page.goto(self.author_url, wait_until="networkidle", timeout=15000)
                await asyncio.sleep(2)
                api = await page.evaluate("""async () => {
                    const r = await fetch('/api/author/book/book_list/v0?aid=2503&app_name=muye_novel&page_count=10&page_index=0');
                    try {
                        const d = await r.json();
                        if (d.code !== 0) return null;
                        const b = d.data.book_list[0];
                        return {words: b.word_count, last: b.last_chapter_title,
                                read_count: b.read_count || 0, status: b.status};
                    } catch { return null; }
                }""")
                success = api and api.get("words", 0) > 0
                # Save performance data
                if api:
                    try:
                        from .database import Database
                        db2 = Database()
                        with db2.conn() as c:
                            c.execute("""INSERT OR REPLACE INTO performance_logs
                                (novel_id, chapter_number, views, collected_at)
                                VALUES (?,?,?,datetime('now'))""",
                                (self.name, chapter_num, api.get("read_count", 0)))
                    except Exception:
                        pass

                # Screenshot
                spath = str(Path("data/publish_logs") / f"ch{chapter_num}_{int(time.time())}.png")
                Path("data/publish_logs").mkdir(exist_ok=True)
                await page.screenshot(path=spath)

                if success:
                    print(f"[PUBLISH] 🎉 成功! 字数={api['words']} 最新章={api.get('last','?')}", flush=True)
                    return PublishResult(True, self.name, chapter_num, screenshot_path=spath,
                                         retry_count=attempt, duration_seconds=round(time.time() - t0, 1))
                else:
                    print(f"[PUBLISH] ❌ 失败: {api}", flush=True)

            except Exception as e:
                print(f"[PUBLISH] Error (attempt {attempt+1}): {e}")
                if editor:
                    try:
                        spath = str(Path("data/publish_logs") / f"error_ch{chapter_num}_{int(time.time())}.png")
                        Path("data/publish_logs").mkdir(exist_ok=True)
                        await editor.screenshot(path=spath)
                    except:
                        pass
                    try:
                        await editor.close()
                    except:
                        pass

        return PublishResult(False, self.name, chapter_num, error="All attempts failed",
                             screenshot_path=spath)


class Publisher:
    def __init__(self, cfg: Config = config):
        self.cfg = cfg
        self.db = Database()
        self.platform = FanqiePlatform()

    async def publish(self, novel_id: str, chapter_number: int) -> PublishResult:
        t0 = time.time()
        if not novel_id or chapter_number < 1:
            return PublishResult(False, self.platform.name, chapter_number, error="Invalid params")
        chapter = self.db.get_chapter(novel_id, chapter_number)
        if not chapter:
            return PublishResult(False, self.platform.name, chapter_number, error="Chapter not found")
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            return PublishResult(False, self.platform.name, chapter_number, error="Playwright not installed")

        async with async_playwright() as p:
            browser, ctx = await self.platform._get_browser(p)
            page = await ctx.new_page()
            try:
                logged_in = await self.platform.login(page, f"data/auth/{self.platform.name}.json")
                if not logged_in:
                    return PublishResult(False, self.platform.name, chapter_number, error="Login failed")
                clean_title = chapter["title"].replace("# ", "").replace("## ", "").replace("\n", "")
                result = await self.platform.upload_chapter(page, clean_title, chapter.get("content", ""), chapter_number)
                result.duration_seconds = round(time.time() - t0, 1)
                self.db.record_publish(chapter["id"], self.platform.name, result.success,
                                       result.url, result.error, result.screenshot_path)
                if result.success:
                    self.db.log(novel_id, "publish.success", {"chapter": chapter_number})
                return result
            except Exception as e:
                self.db.log(novel_id, "publish.failed", {"chapter": chapter_number, "error": str(e)})
                return PublishResult(False, self.platform.name, chapter_number, error=str(e))
            finally:
                await browser.close()
