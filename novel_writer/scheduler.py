"""调度器 — 模式 A 全自动定时执行"""
import json
import signal
import time
from datetime import datetime, timedelta

from .config import Config, config
from .database import Database
from .routers.novel.chapter_metadata import chapter_content_rejection
from .routers.novel.generation_service import (
    _sync_new_foreshadowing,
    _sync_next_plot_points,
    _sync_resolved_foreshadowing,
)


def _safe_json_list(value):
    if not value:
        return []
    try:
        parsed = json.loads(value) if isinstance(value, str) else value
        if isinstance(parsed, list):
            return parsed
    except (json.JSONDecodeError, TypeError):
        pass
    if isinstance(value, str):
        return [item.strip() for item in value.replace("；", "\n").replace(";", "\n").splitlines() if item.strip()]
    return []


class Scheduler:
    def __init__(self, cfg: Config = config):
        self.cfg = cfg
        self.db = Database()
        self._running = False

    def start_auto(self, novel_id: str):
        """Start auto mode for a novel"""
        self.db.update_novel(novel_id, mode="auto")
        next_run = self._calc_next_run()
        self.db.set_scheduler_state(novel_id, is_running=1, next_run_at=next_run)
        self.db.log(novel_id, "auto.started", {"next_run": next_run})

    def stop_auto(self, novel_id: str):
        """Stop auto mode"""
        self.db.set_scheduler_state(novel_id, is_running=0)
        self.db.update_novel(novel_id, mode="creator")
        self.db.log(novel_id, "auto.stopped", {})

    def status(self, novel_id: str) -> dict:
        """Get auto mode status"""
        state = self.db.get_scheduler_state(novel_id)
        if not state:
            return {"novel_id": novel_id, "running": False}
        return {
            "novel_id": novel_id,
            "running": bool(state.get("is_running", 0)),
            "next_run": state.get("next_run_at"),
            "last_run": state.get("last_run_at"),
            "last_result": state.get("last_result"),
            "consecutive_failures": state.get("consecutive_failures", 0),
        }

    def run_once(self, novel_id: str) -> str:
        """Manual trigger: run one generate cycle"""
        from .generator import Generator
        from .story_state import ChapterMeta, Character, Plot, StoryState, World

        novel = self.db.get_novel(novel_id)
        if not novel:
            return "error: novel not found"

        if hasattr(self.db, "get_all_foreshadowing"):
            active_foreshadowing = [
                thread.get("description", "")
                for thread in self.db.get_all_foreshadowing(novel_id)
                if thread.get("description") and thread.get("status", "active") in ("active", "overdue")
            ]
        else:
            active_foreshadowing = [
                thread.get("description", "")
                for thread in self.db.get_active_foreshadowing(novel_id)
                if thread.get("description")
            ]
        next_plot_points = [
            point.get("content", "")
            for point in novel.get("plot_points", [])
            if point.get("content") and point.get("type", "plot") == "plot" and not point.get("is_resolved")
        ][:8]

        state = StoryState(
            novel_id=novel_id, title=novel["title"], author=novel["author"],
            synopsis=novel.get("synopsis",""), genre=novel["genre"],
            world=World(name=novel.get("world_name",""), era=novel.get("world_era",""),
                         geography=novel.get("world_geo",""), power_system=novel.get("power_system","")),
            characters=[Character(id=ch["char_key"], name=ch["name"], role=ch["role"],
                         personality=ch.get("personality",""), background=ch.get("background",""),
                         current_power_level=ch.get("power_level",""))
                         for ch in novel.get("characters", [])],
            plot=Plot(premise=novel.get("synopsis",""), main_arc=novel.get("main_arc",""),
                       current_arc=novel.get("current_arc","开篇"),
                       arc_chapter_start=novel.get("arc_chapter_start",1),
                       next_plot_points=next_plot_points,
                       foreshadowing=active_foreshadowing),
            chapters=[ChapterMeta(number=ch["number"], title=ch["title"],
                         word_count=ch["word_count"], summary=ch.get("summary",""),
                         content=ch.get("content",""),
                         ending_hook=ch.get("ending_hook",""),
                         key_events=_safe_json_list(ch.get("key_events")),
                         revelations=_safe_json_list(ch.get("revelations")),
                         narrative_facts=_safe_json_list(ch.get("narrative_facts")),
                         generated_at=ch.get("generated_at",""))
                         for ch in novel.get("chapters", []) if ch.get("word_count", 0) > 0],
        )

        try:
            # Use provider model if configured
            from .config import Config as Cfg
            provider_id = novel.get("provider_id", "openai")
            provider = self.db.get_provider(provider_id)
            model = self.cfg.model
            api_key = self.cfg.openai_api_key
            base_url = self.cfg.openai_base_url
            if provider:
                model = provider.get("models", "deepseek-v4-pro")[0] if provider.get("models") else model
                api_key = provider.get("api_key", api_key)
                base_url = provider.get("base_url", base_url)
            gen_cfg = Cfg(openai_api_key=api_key, openai_base_url=base_url, model=model)
            gen = Generator(gen_cfg)

            # Load outline for context injection
            outline = []
            try:
                next_outline_ch = self.db.get_next_chapter_number(novel_id) if hasattr(self.db, "get_next_chapter_number") else (state.total_chapters + 1)
                with self.db.conn() as conn:
                    rows = conn.execute(
                        """SELECT number, title, summary FROM chapters
                           WHERE novel_id=? AND word_count=0 AND number>=? AND number<?
                           ORDER BY number""",
                        (novel_id, next_outline_ch, next_outline_ch + 1)
                    ).fetchall()
                    outline = [{"number": r["number"], "title": r["title"], "summary": r["summary"]} for r in rows]
            except Exception:
                pass

            # RAG context
            rag_context = gen.retrieve_relevant_context(state.plot.current_arc if state.plot else "", novel_id, top_k=5)

            # ── Generation + Quality + De-AI pipeline ──
            def _process(chapter, body):
                """Score, de-AI, and save a generated chapter. Returns (cid, cleaned_body, quality)."""
                cleaned_body, de_ai_changes = gen.de_ai(body)
                if de_ai_changes > 0:
                    print(f"[SCHED] de-AI: {de_ai_changes} changes")
                final_body = cleaned_body or body
                quality = gen.score_quality(final_body, state)
                try:
                    gen.refresh_chapter_content(chapter, final_body)
                except Exception:
                    pass
                if chapter.content != final_body:
                    chapter.content = final_body
                    chapter.word_count = len(final_body)
                    chapter.summary = final_body[:200]
                rejection = chapter_content_rejection("", chapter.content)
                if rejection:
                    raise ValueError(f"生成结果不是有效章节正文：{rejection}")
                cid = self.db.add_chapter(
                    novel_id=novel_id, number=chapter.number, title=chapter.title,
                    word_count=chapter.word_count, summary=chapter.summary,
                    content=chapter.content,
                    ending_hook=chapter.ending_hook,
                    key_events=json.dumps(chapter.key_events),
                    revelations=json.dumps(chapter.revelations),
                    narrative_facts=json.dumps(chapter.narrative_facts, ensure_ascii=False),
                    quality_score=quality['overall'], model_used=gen_cfg.model,
                )
                # Store embeddings (non-blocking)
                try:
                    gen.store_chapter_embedding(cid, novel_id, chapter.content)  # type: ignore[attr-defined]
                except Exception:
                    pass
                return cid, cleaned_body, quality

            chapter, quality = gen.batch_generate(state, n=2, rag_context=rag_context, outline=outline)
            body = chapter.content or chapter.summary

            # Retry on low quality
            retries = 0
            while quality['overall'] < 0.5 and retries < 2:
                retries += 1
                print(f"[SCHED] {novel_id} Q={quality['overall']} — retry {retries}")
                chapter, quality = gen.batch_generate(state, n=1, rag_context=rag_context, outline=outline)
                body = chapter.content or chapter.summary

            cid, cleaned_body, quality = _process(chapter, body)
            try:
                _sync_resolved_foreshadowing(self.db, novel_id, state, chapter.number)
                _sync_new_foreshadowing(self.db, novel_id, state, chapter.number)
                _sync_next_plot_points(self.db, novel_id, state)
            except Exception as sync_exc:
                self.db.log(novel_id, "story_state.sync_failed", {"error": str(sync_exc)[:200]})

            self.db.record_scheduler_run(novel_id, "success")
            self.db.log(novel_id, "chapter.generated", {
                "chapter": chapter.number, "words": chapter.word_count,
                "quality": quality['overall'], "grade": quality['grade'],
            })
            return f"success: chapter {chapter.number} ({chapter.word_count}w, Q:{quality['grade']})"
        except Exception as e:
            self.db.record_scheduler_run(novel_id, "failed")
            self.db.log(novel_id, "error.critical", {"error": str(e)})
            return f"failed: {e}"

    def run_daemon(self):
        """Daemon mode: loop and run at scheduled time for all active novels"""
        self._running = True
        signal.signal(signal.SIGTERM, lambda s, f: self._shutdown())
        signal.signal(signal.SIGINT, lambda s, f: self._shutdown())

        print(f"[Scheduler] Daemon started. Daily run at {self.cfg.daily_run_time}")
        while self._running:
            secs = self._seconds_until_next_run()
            print(f"[Scheduler] Next run in {secs:.0f}s ({secs/3600:.1f}h)")
            # Sleep in chunks, checking if we should stop
            sleep_time = min(secs, 60)
            for _ in range(int(secs / sleep_time)):
                if not self._running:
                    break
                time.sleep(sleep_time)
            if self._running and self._should_run_now():
                self._run_all_active()

    def _run_all_active(self):
        """Execute generation for all novels with active auto mode (parallel, max 3)."""
        from concurrent.futures import ThreadPoolExecutor, as_completed

        novels = self.db.list_novels()
        active_ids = []
        for n in novels:
            ss = self.db.get_scheduler_state(n["id"])
            if ss is not None and ss.get("is_running"):
                active_ids.append(n["id"])
        if not active_ids:
            return

        with ThreadPoolExecutor(max_workers=min(3, len(active_ids))) as executor:
            futures = {executor.submit(self.run_once, nid): nid for nid in active_ids}
            for f in as_completed(futures):
                print(f"[Scheduler] {futures[f]}: {f.result()}")

    def _shutdown(self):
        print("[Scheduler] Shutting down...")
        self._running = False

    def _calc_next_run(self) -> str:
        now = datetime.now()
        try:
            target = datetime.strptime(self.cfg.daily_run_time, "%H:%M").replace(
                year=now.year, month=now.month, day=now.day)
        except ValueError:
            target = now.replace(hour=9, minute=0)
        if target <= now:
            target += timedelta(days=1)
        return target.isoformat()

    def _seconds_until_next_run(self) -> float:
        target = datetime.strptime(self.cfg.daily_run_time, "%H:%M").replace(
            year=datetime.now().year, month=datetime.now().month, day=datetime.now().day)
        if target <= datetime.now():
            target += timedelta(days=1)
        return max(0, (target - datetime.now()).total_seconds())

    def _should_run_now(self) -> bool:
        return self._seconds_until_next_run() < 60
