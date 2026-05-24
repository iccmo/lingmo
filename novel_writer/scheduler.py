"""调度器 — 模式 A 全自动定时执行"""
import time, signal, sys
from datetime import datetime, timedelta
from typing import Optional

from .database import Database
from .config import Config, config


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
        from .story_state import StoryState, World, Plot, Character, ChapterMeta

        novel = self.db.get_novel(novel_id)
        if not novel:
            return "error: novel not found"

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
                       arc_chapter_start=novel.get("arc_chapter_start",1)),
            chapters=[ChapterMeta(number=ch["number"], title=ch["title"],
                         word_count=ch["word_count"], summary=ch.get("summary",""),
                         ending_hook=ch.get("ending_hook",""),
                         generated_at=ch.get("generated_at",""))
                         for ch in novel.get("chapters", []) if ch.get("word_count", 0) > 0],
        )

        import json
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
                with self.db.conn() as conn:
                    rows = conn.execute(
                        "SELECT number, title, summary FROM chapters WHERE novel_id=? AND word_count=0 ORDER BY number LIMIT 5",
                        (novel_id,)
                    ).fetchall()
                    outline = [{"number": r["number"], "title": r["title"], "summary": r["summary"]} for r in rows]
            except Exception:
                pass

            # RAG context
            rag_context = gen.retrieve_relevant_context(state.plot.current_arc, novel_id, top_k=5)

            # ── Generation + Quality + De-AI pipeline ──
            def _process(chapter, body):
                """Score, de-AI, and save a generated chapter. Returns (cid, cleaned_body, quality)."""
                quality = gen.score_quality(body, state)
                cleaned_body, de_ai_changes = gen.de_ai(body)
                if de_ai_changes > 0:
                    print(f"[SCHED] de-AI: {de_ai_changes} changes")
                cid = self.db.add_chapter(
                    novel_id=novel_id, number=chapter.number, title=chapter.title,
                    word_count=chapter.word_count, summary=chapter.summary,
                    content=cleaned_body or chapter.content or chapter.summary,
                    ending_hook=chapter.ending_hook,
                    key_events=json.dumps(chapter.key_events),
                    revelations=json.dumps(chapter.revelations),
                    quality_score=quality['overall'], model_used=gen_cfg.model,
                )
                # Store embeddings (non-blocking)
                try:
                    gen.store_chapter_embedding(cid, novel_id, chapter.summary)
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
        active_ids = [
            n["id"] for n in novels
            if self.db.get_scheduler_state(n["id"]) and self.db.get_scheduler_state(n["id"]).get("is_running")
        ]
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
