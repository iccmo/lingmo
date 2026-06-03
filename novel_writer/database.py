"""数据库访问层 — SQLite + WAL"""

import datetime
import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path

SCHEMA_PATH = Path(__file__).parent / "schema.sql"


class Database:
    def __init__(self, db_path: str = "data/novel_writer.db"):
        self.db_path = db_path
        self._init()

    def _init(self):
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        with self.conn() as conn:
            if SCHEMA_PATH.exists():
                conn.executescript(SCHEMA_PATH.read_text())
            # V4: Add provider_id column if not exists
            try:
                conn.execute("ALTER TABLE novels ADD COLUMN provider_id TEXT DEFAULT 'openai'")
            except Exception:
                pass  # Column already exists
            # V11: Add updated_at column to foreshadowing_tracker
            try:
                conn.execute("ALTER TABLE foreshadowing_tracker ADD COLUMN updated_at TEXT NOT NULL DEFAULT (datetime('now'))")
            except Exception:
                pass  # Column already exists
            # V9-V10: Create cost_logs and chapter_summaries tables if schema didn't run
            try:
                conn.execute("""CREATE TABLE IF NOT EXISTS cost_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, novel_id TEXT NOT NULL,
                    chapter_number INTEGER NOT NULL DEFAULT 0, model TEXT NOT NULL DEFAULT '',
                    prompt_tokens INTEGER NOT NULL DEFAULT 0, completion_tokens INTEGER NOT NULL DEFAULT 0,
                    total_tokens INTEGER NOT NULL DEFAULT 0, cost REAL NOT NULL DEFAULT 0,
                    purpose TEXT NOT NULL DEFAULT 'generate', created_at TEXT NOT NULL DEFAULT (datetime('now')))""")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_cost_logs_novel ON cost_logs(novel_id)")
                conn.execute("""CREATE TABLE IF NOT EXISTS chapter_summaries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, novel_id TEXT NOT NULL,
                    chapter_num INTEGER NOT NULL, summary_text TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    UNIQUE(novel_id, chapter_num))""")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_chapter_summaries_novel ON chapter_summaries(novel_id)")
            except Exception:
                pass
            # V28: soul_fingerprints
            try:
                conn.execute('''CREATE TABLE IF NOT EXISTS soul_fingerprints (novel_id TEXT PRIMARY KEY, polarity TEXT DEFAULT '', position INTEGER DEFAULT 5, answer TEXT DEFAULT '', created_at TEXT DEFAULT (datetime(''now'')), updated_at TEXT DEFAULT (datetime(''now'')))''')
            except Exception:
                pass
            # V29: character_blueprints
            try:
                conn.execute('''CREATE TABLE IF NOT EXISTS character_blueprints (novel_id TEXT PRIMARY KEY, characters_json TEXT DEFAULT '[]', created_at TEXT DEFAULT (datetime(''now'')), updated_at TEXT DEFAULT (datetime(''now'')))''')
            except Exception:
                pass
            # V12: chapter_versions table
            try:
                conn.execute("""CREATE TABLE IF NOT EXISTS chapter_versions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chapter_id INTEGER NOT NULL REFERENCES chapters(id) ON DELETE CASCADE,
                    content TEXT NOT NULL DEFAULT '',
                    word_count INTEGER NOT NULL DEFAULT 0,
                    version INTEGER NOT NULL DEFAULT 1,
                    reason TEXT DEFAULT '',
                    created_at TEXT DEFAULT (datetime('now')))""")
            except Exception:
                pass

    @contextmanager
    def conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    async def aconn(self):
        """异步数据库连接上下文管理器（aiosqlite）。"""
        import aiosqlite
        conn = await aiosqlite.connect(self.db_path)
        conn.row_factory = aiosqlite.Row
        await conn.execute("PRAGMA journal_mode=WAL")
        await conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
            await conn.commit()
        except Exception:
            await conn.rollback()
            raise
        finally:
            await conn.close()

    # ═══════════════════ Novel CRUD ═══════════════════

    def create_novel(self, **kw: object) -> dict:
        defaults = dict(id='', title='', author='AI', synopsis='', genre='玄幻',
                        world_name='', world_era='', world_geo='', power_system='',
                        world_rules='[]', main_arc='', current_arc='开篇', arc_chapter_start=1)
        defaults.update(kw)
        kw = defaults
        with self.conn() as c:
            c.execute("""INSERT INTO novels (id,title,author,synopsis,genre,
                world_name,world_era,world_geo,power_system,world_rules,
                main_arc,current_arc,arc_chapter_start)
                VALUES (:id,:title,:author,:synopsis,:genre,
                :world_name,:world_era,:world_geo,:power_system,:world_rules,
                :main_arc,:current_arc,:arc_chapter_start)""", kw)
            if kw.get("tags"):
                for tag in kw["tags"]:  # type: ignore[attr-defined]
                    c.execute("INSERT OR IGNORE INTO novel_tags (novel_id,tag) VALUES (?,?)",
                              (kw["id"], tag))
            if kw.get("char_key"):
                cdef: dict[str, object] = dict(secrets='[]', personality='', background='', power_level='')
                cdef.update(kw)
                c.execute("""INSERT INTO characters (novel_id,char_key,name,role,
                    personality,background,power_level,secrets)
                    VALUES (:id,:char_key,:name,:role,
                    :personality,:background,:power_level,:secrets)""", cdef)
        result = self.get_novel(str(kw["id"]))
        assert result is not None
        return result

    def get_novel(self, novel_id: str) -> dict | None:
        with self.conn() as c:
            row = c.execute("SELECT * FROM active_novels WHERE id=?", (novel_id,)).fetchone()
            if not row:
                return None
            d = dict(row)
            d["tags"] = [r["tag"] for r in c.execute(
                "SELECT tag FROM novel_tags WHERE novel_id=?", (novel_id,))]
            d["characters"] = [dict(r) for r in c.execute(
                "SELECT * FROM characters WHERE novel_id=?", (novel_id,))]
            d["factions"] = [dict(r) for r in c.execute(
                "SELECT * FROM factions WHERE novel_id=? ORDER BY sort_order", (novel_id,))]
            d["chapters"] = [dict(r) for r in c.execute(
                "SELECT number,title,word_count,summary,ending_hook,quality_score,model_used,generated_at FROM chapters WHERE novel_id=? ORDER BY number", (novel_id,))]
            d["plot_points"] = [dict(r) for r in c.execute(
                "SELECT * FROM plot_points WHERE novel_id=? ORDER BY is_resolved,sort_order", (novel_id,))]
            d["total_chapters"] = len(d["chapters"])
            d["total_words"] = sum(ch["word_count"] for ch in d["chapters"])
            latest = d["chapters"][-1] if d["chapters"] else None
            d["latest_chapter"] = {"number": latest["number"], "title": latest["title"],
                                    "generated_at": latest["generated_at"]} if latest else None
            # Character relations
            rels = c.execute("""SELECT cr.*, c1.name as c1_name, c2.name as c2_name
                FROM character_relations cr
                JOIN characters c1 ON c1.id=cr.char_1_id
                JOIN characters c2 ON c2.id=cr.char_2_id
                WHERE cr.novel_id=?""", (novel_id,)).fetchall()
            d["character_relations"] = [dict(r) for r in rels]
            return d

    def list_novels(self) -> list[dict]:
        with self.conn() as c:
            rows = c.execute("""SELECT n.id, n.title, n.author, n.genre, n.synopsis, n.status, n.mode,
                COUNT(c.id) as total_chapters,
                COALESCE(SUM(c.word_count), 0) as total_words,
                (SELECT c2.title FROM chapters c2 WHERE c2.novel_id=n.id ORDER BY c2.number DESC LIMIT 1) as latest_title,
                (SELECT c2.number FROM chapters c2 WHERE c2.novel_id=n.id ORDER BY c2.number DESC LIMIT 1) as latest_number,
                (SELECT c2.generated_at FROM chapters c2 WHERE c2.novel_id=n.id ORDER BY c2.number DESC LIMIT 1) as latest_generated_at
                FROM active_novels n
                LEFT JOIN chapters c ON c.novel_id = n.id
                GROUP BY n.id ORDER BY n.updated_at DESC""").fetchall()
            result = []
            for row in rows:
                d = dict(row)
                d["latest_chapter"] = {"number": d["latest_number"], "title": d["latest_title"],
                                        "generated_at": d["latest_generated_at"]} if d["latest_number"] else None
                result.append(d)
            return result

    ALLOWED_NOVEL_COLS = {
        'title','author','synopsis','genre','status','mode',
        'world_name','world_era','world_geo','power_system','world_rules',
        'main_arc','current_arc','arc_chapter_start','deleted_at','provider_id'
    }

    def update_novel(self, novel_id: str, **kw):
        bad = [k for k in kw if k not in self.ALLOWED_NOVEL_COLS]
        if bad:
            raise ValueError(f"Invalid column(s): {bad}")
        if not kw:
            return
        sets = ", ".join(f"{k}=:{k}" for k in kw)
        sets += ", updated_at=datetime('now')"
        kw["id"] = novel_id
        with self.conn() as c:
            c.execute(f"UPDATE novels SET {sets} WHERE id=:id", kw)

    def soft_delete_novel(self, novel_id: str):
        with self.conn() as c:
            c.execute("UPDATE novels SET deleted_at=datetime('now') WHERE id=?", (novel_id,))

    # ═══════════════════ Chapter CRUD ═══════════════════

    def add_chapter(self, novel_id: str, **kw) -> int:
        defaults = dict(number=0, title='', word_count=0, summary='', content='',
                        ending_hook='', key_events='[]', revelations='[]',
                        quality_score=0, model_used='', prompt_version='',
                        prompt_tokens=0, completion_tokens=0, cost=0, generation_duration_ms=0)
        defaults.update(kw)
        kw = defaults
        kw["novel_id"] = novel_id
        with self.conn() as c:
            # Use INSERT OR REPLACE — outline chapters (word_count=0) will be overwritten by generated ones
            cur = c.execute("""INSERT OR REPLACE INTO chapters (novel_id,number,title,word_count,summary,content,
                ending_hook,key_events,revelations,quality_score,model_used,
                prompt_version,prompt_tokens,completion_tokens,cost,generation_duration_ms)
                VALUES (:novel_id,:number,:title,:word_count,:summary,:content,
                :ending_hook,:key_events,:revelations,:quality_score,:model_used,
                :prompt_version,:prompt_tokens,:completion_tokens,:cost,:generation_duration_ms)""", kw)
            c.execute("UPDATE novels SET updated_at=datetime('now') WHERE id=?", (novel_id,))
            return cur.lastrowid

    def get_chapter(self, novel_id: str, number: int) -> dict | None:
        with self.conn() as c:
            row = c.execute("SELECT * FROM chapters WHERE novel_id=? AND number=?",
                            (novel_id, number)).fetchone()
            return dict(row) if row else None

    def update_chapter(self, novel_id: str, number: int, **kw):
        if not kw:
            return
        sets = ", ".join(f"{k}=:{k}" for k in kw)
        kw["novel_id"] = novel_id
        kw["number"] = number
        with self.conn() as c:
            c.execute(f"UPDATE chapters SET {sets} WHERE novel_id=:novel_id AND number=:number", kw)

    # ═══════════════════ Drafts ═══════════════════

    def save_drafts(self, chapter_id: int, drafts: list[dict]):
        with self.conn() as c:
            for d in drafts:
                c.execute("""INSERT INTO chapter_drafts (chapter_id,draft_label,direction,preview,hook,is_selected)
                    VALUES (?,?,?,?,?,?)""",
                    (chapter_id, d["id"], d["direction"], d.get("preview", ""),
                     d.get("hook", ""), 1 if d.get("selected") else 0))

    # ═══════════════════ Scheduler ═══════════════════

    def set_scheduler_state(self, novel_id: str, **kw):
        with self.conn() as c:
            c.execute("""INSERT OR REPLACE INTO scheduler_state
                (novel_id,is_running,next_run_at,updated_at)
                VALUES (?,?,?,datetime('now'))""",
                (novel_id, kw.get("is_running", 0), kw.get("next_run_at")))

    def get_scheduler_state(self, novel_id: str) -> dict | None:
        with self.conn() as c:
            row = c.execute("SELECT * FROM scheduler_state WHERE novel_id=?", (novel_id,)).fetchone()
            return dict(row) if row else None

    def record_scheduler_run(self, novel_id: str, result: str):
        with self.conn() as c:
            c.execute("""UPDATE scheduler_state SET last_run_at=datetime('now'),
                last_result=?, consecutive_failures=CASE WHEN ?='failed' THEN consecutive_failures+1 ELSE 0 END,
                updated_at=datetime('now')
                WHERE novel_id=?""", (result, result, novel_id))

    # ═══════════════════ Auth ═══════════════════

    def save_auth(self, platform: str, data: dict):
        with self.conn() as c:
            c.execute("""INSERT OR REPLACE INTO platform_auth (platform,auth_data,is_valid,updated_at)
                VALUES (?,?,?,datetime('now'))""",
                (platform, json.dumps(data), 1 if data else 0))

    def get_auth(self, platform: str) -> dict | None:
        with self.conn() as c:
            row = c.execute("SELECT * FROM platform_auth WHERE platform=?", (platform,)).fetchone()
            if not row:
                return None
            d = dict(row)
            d["auth_data"] = json.loads(d["auth_data"]) if d["auth_data"] else {}
            return d

    # ═══════════════════ Logging ═══════════════════

    def log(self, novel_id: str | None, event: str, detail: dict):
        with self.conn() as c:
            c.execute("INSERT INTO run_logs (novel_id,event,detail) VALUES (?,?,?)",
                      (novel_id, event, json.dumps(detail)))

    def get_logs(self, limit: int = 50) -> list[dict]:
        with self.conn() as c:
            rows = c.execute(
                "SELECT * FROM run_logs ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
            return [dict(r) for r in rows]

    # ═══════════════════ Reanchor ═══════════════════

    def save_snapshot(self, novel_id: str, chapter: int, world: dict, chars: dict, plot: dict):
        with self.conn() as c:
            c.execute("""INSERT OR REPLACE INTO reanchor_snapshots
                (novel_id,trigger_chapter,world_snapshot,chars_snapshot,plot_snapshot)
                VALUES (?,?,?,?,?)""",
                (novel_id, chapter, json.dumps(world), json.dumps(chars), json.dumps(plot)))

    # ═══════════════════ Publish ═══════════════════

    def record_publish(self, chapter_id: int, platform: str, success: bool,
                       url: str = "", error: str = "", screenshot: str = ""):
        with self.conn() as c:
            c.execute("""INSERT INTO publish_records (chapter_id,platform,success,url,error,screenshot_path)
                VALUES (?,?,?,?,?,?)""",
                (chapter_id, platform, 1 if success else 0, url, error, screenshot))
            if success:
                c.execute("UPDATE chapters SET published_at=datetime('now') WHERE id=?", (chapter_id,))


    # ═══════════════════ Style Profiles ═══════════════════

    def get_style_profile(self, novel_id: str) -> dict | None:
        """Get novel style profile. Returns None to use genre default."""
        with self.conn() as conn:
            row = conn.execute(
                "SELECT profile_json FROM style_profiles WHERE novel_id = ?",
                (novel_id,)
            ).fetchone()
        if row and row["profile_json"]:
            return json.loads(row["profile_json"])
        return None

    def save_style_profile(self, novel_id: str, profile: dict):
        """Save or update style profile."""
        with self.conn() as conn:
            conn.execute("""INSERT OR REPLACE INTO style_profiles (novel_id, profile_json, version, updated_at)
                VALUES (?, ?, COALESCE((SELECT version+1 FROM style_profiles WHERE novel_id=?), 1),
                datetime('now'))""",
                (novel_id, json.dumps(profile, ensure_ascii=False, default=str), novel_id))

    def save_character_voice_style(self, novel_id: str, char_key: str, voice_data: dict):
        """Persist character voice style data (writing patterns) to characters.voice_data."""
        with self.conn() as conn:
            conn.execute(
                "UPDATE characters SET voice_data=?, updated_at=datetime('now') WHERE novel_id=? AND char_key=?",
                (json.dumps(voice_data, ensure_ascii=False), novel_id, char_key))

    def get_character_voice_styles(self, novel_id: str) -> dict[str, dict]:
        """Load all character voice style data (writing patterns) for a novel."""
        with self.conn() as c:
            rows = c.execute(
                "SELECT char_key, voice_data FROM characters WHERE novel_id=? AND voice_data IS NOT NULL AND voice_data != '{}'",
                (novel_id,)).fetchall()
        return {r["char_key"]: json.loads(r["voice_data"]) for r in rows if r["voice_data"]}

    def log_cost(self, novel_id: str, chapter_number: int, model: str,
                 prompt_tokens: int, completion_tokens: int, total_tokens: int,
                 cost: float, purpose: str = "generate"):
        """Insert a cost tracking record."""
        with self.conn() as conn:
            conn.execute("""INSERT INTO cost_logs (novel_id, chapter_number, model,
                prompt_tokens, completion_tokens, total_tokens, cost, purpose)
                VALUES (?,?,?,?,?,?,?,?)""",
                (novel_id, chapter_number, model, prompt_tokens, completion_tokens,
                 total_tokens, round(cost, 6), purpose))

    def save_chapter_version(self, novel_id: str, chapter_num: int, content: str, reason: str = ""):
        """Save a version snapshot for a chapter."""
        with self.conn() as c:
            ch = c.execute("SELECT id FROM chapters WHERE novel_id=? AND number=?",
                          (novel_id, chapter_num)).fetchone()
            if not ch:
                return
            ver = (c.execute("SELECT COALESCE(MAX(version),0)+1 FROM chapter_versions WHERE chapter_id=?",
                            (ch["id"],)).fetchone()[0])
            c.execute("INSERT INTO chapter_versions (chapter_id, content, word_count, version, reason) VALUES (?,?,?,?,?)",
                     (ch["id"], content, len(content), ver, reason))

    def get_chapter_versions(self, novel_id: str, chapter_num: int) -> list[dict]:
        """Get all version snapshots for a chapter."""
        with self.conn() as c:
            ch = c.execute("SELECT id FROM chapters WHERE novel_id=? AND number=?",
                          (novel_id, chapter_num)).fetchone()
            if not ch:
                return []
            rows = c.execute("""SELECT id, word_count, version, reason, created_at
                              FROM chapter_versions WHERE chapter_id=? ORDER BY version DESC""",
                            (ch["id"],)).fetchall()
        return [dict(r) for r in rows]

    def get_chapter_version_content(self, version_id: int) -> str | None:
        """Get a specific version's content."""
        with self.conn() as c:
            row = c.execute("SELECT content FROM chapter_versions WHERE id=?", (version_id,)).fetchone()
        return row["content"] if row else None

    def save_chapter_trace(self, data: dict):
        """Save generation pipeline trace for a chapter."""
        import json as _json
        steps_json = _json.dumps(data.get("steps", []))
        with self.conn() as c:
            c.execute("""INSERT OR REPLACE INTO chapter_traces
                (novel_id, chapter_num, steps_json, final_quality, total_duration_ms, total_cost)
                VALUES (?, ?, ?, ?, ?, ?)""",
                (data["novel_id"], data["chapter_num"], steps_json,
                 data.get("final_quality", 0), data.get("total_duration_ms", 0),
                 data.get("total_cost", 0)))

    def get_chapter_traces(self, novel_id: str) -> list[dict]:
        """Get all generation traces for a novel, newest first."""
        import json as _json
        with self.conn() as c:
            rows = c.execute("""SELECT * FROM chapter_traces WHERE novel_id=?
                ORDER BY chapter_num DESC""", (novel_id,)).fetchall()
        return [{
            "chapter_num": r["chapter_num"],
            "steps": _json.loads(r["steps_json"]),
            "final_quality": r["final_quality"],
            "total_duration_ms": r["total_duration_ms"],
            "total_cost": r["total_cost"],
            "created_at": r["created_at"],
        } for r in rows]

    def save_soul_fingerprint(self, novel_id: str, polarity: str, position: int, answer: str):
        with self.conn() as c:
            c.execute("INSERT OR REPLACE INTO soul_fingerprints (novel_id, polarity, position, answer, updated_at) VALUES (?, ?, ?, ?, datetime('now'))", (novel_id, polarity, position, answer))

    def get_soul_fingerprint(self, novel_id: str):
        with self.conn() as c:
            row = c.execute("SELECT * FROM soul_fingerprints WHERE novel_id=?", (novel_id,)).fetchone()
            return dict(row) if row else None

    def delete_soul_fingerprint(self, novel_id: str):
        with self.conn() as c:
            c.execute("DELETE FROM soul_fingerprints WHERE novel_id=?", (novel_id,))

    def save_character_blueprints(self, novel_id: str, characters: list[dict]):
        """Save all character blueprints for a novel as a JSON array."""
        import json as _json
        with self.conn() as c:
            c.execute(
                "INSERT OR REPLACE INTO character_blueprints (novel_id, characters_json, updated_at) VALUES (?, ?, datetime('now'))",
                (novel_id, _json.dumps(characters, ensure_ascii=False)),
            )

    def get_character_blueprints(self, novel_id: str) -> list[dict]:
        """Get all character blueprints for a novel."""
        import json as _json
        with self.conn() as c:
            row = c.execute("SELECT characters_json FROM character_blueprints WHERE novel_id=?", (novel_id,)).fetchone()
            if not row:
                return []
            try:
                return _json.loads(row[0])
            except Exception:
                return []

    def delete_character_blueprint(self, novel_id: str, char_id: str) -> bool:
        """Delete a single character blueprint by id. Returns True if deleted."""
        import json as _json
        with self.conn() as c:
            row = c.execute("SELECT characters_json FROM character_blueprints WHERE novel_id=?", (novel_id,)).fetchone()
            if not row:
                return False
            try:
                chars = _json.loads(row[0])
            except Exception:
                return False
            new_chars = [c for c in chars if c.get("id") != char_id]
            if len(new_chars) == len(chars):
                return False  # nothing deleted
            c.execute(
                "UPDATE character_blueprints SET characters_json=?, updated_at=datetime('now') WHERE novel_id=?",
                (_json.dumps(new_chars, ensure_ascii=False), novel_id),
            )
            return True

    def get_cost_summary(self, novel_id: str = "") -> dict:
        """Get cost summary for a novel or all novels."""
        with self.conn() as c:
            if novel_id:
                rows = c.execute("""SELECT model, COUNT(*) as calls,
                    SUM(prompt_tokens) as pt, SUM(completion_tokens) as ct,
                    SUM(total_tokens) as tt, SUM(cost) as total_cost
                    FROM cost_logs WHERE novel_id=? GROUP BY model""", (novel_id,)).fetchall()
                by_novel_rows = c.execute("""SELECT cl.novel_id, n.title,
                    SUM(cl.cost) as cost, COUNT(*) as chapters
                    FROM cost_logs cl JOIN novels n ON n.id=cl.novel_id
                    WHERE cl.novel_id=? GROUP BY cl.novel_id""", (novel_id,)).fetchall()
            else:
                rows = c.execute("""SELECT model, COUNT(*) as calls,
                    SUM(prompt_tokens) as pt, SUM(completion_tokens) as ct,
                    SUM(total_tokens) as tt, SUM(cost) as total_cost
                    FROM cost_logs GROUP BY model""").fetchall()
                by_novel_rows = c.execute("""SELECT cl.novel_id, n.title,
                    SUM(cl.cost) as cost, COUNT(*) as chapters
                    FROM cost_logs cl JOIN novels n ON n.id=cl.novel_id
                    GROUP BY cl.novel_id ORDER BY cost DESC""").fetchall()
        return {
            "by_model": [dict(r) for r in rows],
            "by_novel": [dict(r) for r in by_novel_rows],
            "total_cost": round(sum(r["total_cost"] for r in rows), 4),
            "total_tokens": sum(r["tt"] for r in rows),
            "total_calls": sum(r["calls"] for r in rows),
        }

    # ═══════════════════ Chapter Summaries ═══════════════════

    def save_chapter_summary(self, novel_id: str, chapter_num: int, summary_text: str):
        """Save or update a chapter summary for smart context window."""
        with self.conn() as c:
            c.execute("""INSERT OR REPLACE INTO chapter_summaries (novel_id, chapter_num, summary_text, created_at)
                VALUES (?, ?, ?, datetime('now'))""",
                (novel_id, chapter_num, summary_text))

    def get_chapter_summaries(self, novel_id: str, chapter_nums: list[int] | None = None) -> list[dict]:
        """Get chapter summaries for a novel. Optionally filter by chapter numbers."""
        with self.conn() as c:
            if chapter_nums:
                placeholders = ",".join("?" for _ in chapter_nums)
                rows = c.execute(f"""SELECT * FROM chapter_summaries
                    WHERE novel_id=? AND chapter_num IN ({placeholders})
                    ORDER BY chapter_num""",
                    (novel_id, *chapter_nums)).fetchall()
            else:
                rows = c.execute("""SELECT * FROM chapter_summaries
                    WHERE novel_id=? ORDER BY chapter_num""",
                    (novel_id,)).fetchall()
        return [dict(r) for r in rows]

    def has_chapter_summaries(self, novel_id: str, up_to_chapter: int) -> bool:
        """Check if summaries exist for chapters 1..up_to_chapter."""
        with self.conn() as c:
            count = c.execute("""SELECT COUNT(*) FROM chapter_summaries
                WHERE novel_id=? AND chapter_num BETWEEN 1 AND ?""",
                (novel_id, up_to_chapter)).fetchone()[0]
        return count >= up_to_chapter

    # ═══════════════════ Model Providers ═══════════════════


    def list_providers(self) -> list[dict]:
        with self.conn() as c:
            rows = c.execute(
                "SELECT * FROM model_providers WHERE is_enabled=1 ORDER BY priority DESC"
            ).fetchall()
            result = []
            for r in rows:
                d = dict(r)
                d["models"] = json.loads(d.get("models", "[]"))
                d["api_key"] = "***" + d["api_key"][-4:] if d["api_key"] else ""
                result.append(d)
            return result

    def get_provider(self, provider_id: str) -> dict | None:
        with self.conn() as c:
            row = c.execute(
                "SELECT * FROM model_providers WHERE id=?", (provider_id,)
            ).fetchone()
            if not row:
                return None
            d = dict(row)
            d["models"] = json.loads(d.get("models", "[]"))
            return d

    def save_provider(self, provider_id: str, **kw):
        with self.conn() as c:
            existing = c.execute(
                "SELECT id FROM model_providers WHERE id=?", (provider_id,)
            ).fetchone()
            if existing:
                sets = ", ".join(f"{k}=:{k}" for k in kw)
                sets += ", updated_at=datetime('now')"
                kw["id"] = provider_id
                c.execute(f"UPDATE model_providers SET {sets} WHERE id=:id", kw)
            else:
                kw["id"] = provider_id
                kw.setdefault("name", provider_id)
                kw.setdefault("base_url", "")
                kw.setdefault("models", "[]")
                c.execute("""INSERT INTO model_providers (id,name,base_url,api_key,models)
                    VALUES (:id,:name,:base_url,:api_key,:models)""", kw)



    # ═══════════════════ Audio Data ═══════════════════

    def save_audio_progress(self, novel_id: str, chapter_num: int, position_sec: float):
        with self.conn() as c:
            c.execute("""INSERT INTO audio_progress (novel_id, chapter_num, position_sec, updated_at)
                VALUES (?, ?, ?, datetime('now'))
                ON CONFLICT(novel_id) DO UPDATE SET
                    chapter_num=excluded.chapter_num, position_sec=excluded.position_sec,
                    updated_at=datetime('now')""",
                (novel_id, chapter_num, position_sec))

    def get_audio_progress(self, novel_id: str) -> dict | None:
        with self.conn() as c:
            row = c.execute("SELECT * FROM audio_progress WHERE novel_id=?", (novel_id,)).fetchone()
            return dict(row) if row else None

    def get_all_audio_progress(self) -> list[dict]:
        with self.conn() as c:
            return [dict(r) for r in c.execute("SELECT * FROM audio_progress ORDER BY updated_at DESC").fetchall()]

    def save_audio_bookmarks(self, bookmarks: list[dict]):
        with self.conn() as c:
            c.execute("DELETE FROM audio_bookmarks")
            for b in bookmarks:
                c.execute("""INSERT OR REPLACE INTO audio_bookmarks
                    (id, novel_id, novel_title, chapter_num, chapter_title, position, note, tag, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (b.get('id'), b.get('novelId'), b.get('novelTitle', ''),
                     b.get('chapterNum', 0), b.get('chapterTitle', ''),
                     b.get('position', 0), b.get('note', ''), b.get('tag', ''),
                     b.get('createdAt', datetime.datetime.now().isoformat())))

    def load_audio_bookmarks(self) -> list[dict]:
        with self.conn() as c:
            return [dict(r) for r in c.execute("SELECT * FROM audio_bookmarks ORDER BY created_at DESC").fetchall()]

    def save_audio_setting(self, key: str, value: str):
        with self.conn() as c:
            c.execute("INSERT OR REPLACE INTO audio_settings (key, value) VALUES (?, ?)", (key, value))

    def load_audio_settings(self) -> dict:
        with self.conn() as c:
            rows = c.execute("SELECT key, value FROM audio_settings").fetchall()
            return {r['key']: r['value'] for r in rows}

    # ── Film Studio settings ────────────────────────────────────────

    def save_film_setting(self, key: str, value: str) -> None:
        with self.conn() as c:
            c.execute("INSERT OR REPLACE INTO film_settings (key, value) VALUES (?, ?)", (key, value))

    def load_film_settings(self) -> dict[str, str]:
        with self.conn() as c:
            rows = c.execute("SELECT key, value FROM film_settings").fetchall()
            return {r["key"]: r["value"] for r in rows}

    # ── Audio playlist ──────────────────────────────────────────────

    def save_audio_playlist(self, items: list[dict]):
        with self.conn() as c:
            c.execute("DELETE FROM audio_playlist")
            for i, item in enumerate(items):
                c.execute("""INSERT INTO audio_playlist (novel_id, novel_title, chapter_num, chapter_title, sort_order)
                    VALUES (?, ?, ?, ?, ?)""",
                    (item.get('novelId'), item.get('novelTitle', ''), item.get('chapterNum', 0),
                     item.get('chapterTitle', ''), i))

    def load_audio_playlist(self) -> list[dict]:
        with self.conn() as c:
            return [dict(r) for r in c.execute("SELECT * FROM audio_playlist ORDER BY sort_order").fetchall()]

    def save_audio_stats(self, stats: dict):
        with self.conn() as c:
            for k, v in stats.items():
                c.execute("INSERT OR REPLACE INTO audio_stats (stat_key, stat_value, updated_at) VALUES (?, ?, datetime('now'))",
                    (k, str(v)))

    def load_audio_stats(self) -> dict:
        with self.conn() as c:
            rows = c.execute("SELECT stat_key, stat_value FROM audio_stats").fetchall()
            return {r['stat_key']: r['stat_value'] for r in rows}


    # ═══════════════════ Story Bible ═══════════════════

    def save_character_state(self, novel_id: str, chapter_num: int, char_name: str,
                              emotion: str = '', physical_state: str = '', knowledge: str = '[]',
                              goal: str = '', location: str = '', relationships: str = '[]',
                              notes: str = ''):
        with self.conn() as c:
            c.execute("""INSERT INTO character_state (novel_id, chapter_num, char_name, emotion,
                physical_state, knowledge, goal, location, relationships, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (novel_id, chapter_num, char_name, emotion, physical_state, knowledge, goal, location, relationships, notes))

    def get_character_state(self, novel_id: str, chapter_num: int | None = None) -> list[dict]:
        with self.conn() as c:
            if chapter_num:
                rows = c.execute("""SELECT * FROM character_state WHERE novel_id=? AND chapter_num=?
                    ORDER BY id""", (novel_id, chapter_num)).fetchall()
            else:
                rows = c.execute("""SELECT cs.* FROM character_state cs
                    WHERE cs.novel_id=? AND cs.chapter_num = (
                        SELECT MAX(chapter_num) FROM character_state WHERE novel_id=cs.novel_id AND char_name=cs.char_name
                    ) ORDER BY cs.char_name""", (novel_id,)).fetchall()
            return [dict(r) for r in rows]

    def get_all_character_states(self, novel_id: str, char_name: str = '',
                                up_to_chapter: int = 9999) -> list[dict]:
        """获取角色在所有章节的状态记录（含中间章节）。

        与 get_character_state 不同，此方法返回所有章节的记录，
        不限于最大章节号。用于角色视觉一致性记忆等需要历史追踪的场景。
        """
        with self.conn() as c:
            if char_name:
                rows = c.execute(
                    """SELECT * FROM character_state
                       WHERE novel_id=? AND char_name=? AND chapter_num<=?
                       ORDER BY chapter_num, id""",
                    (novel_id, char_name, up_to_chapter),
                ).fetchall()
            else:
                rows = c.execute(
                    """SELECT * FROM character_state
                       WHERE novel_id=? AND chapter_num<=?
                       ORDER BY char_name, chapter_num, id""",
                    (novel_id, up_to_chapter),
                ).fetchall()
            return [dict(r) for r in rows]

    def save_foreshadowing(self, novel_id: str, chapter_num: int, description: str,
                           hint_text: str = '', due_by: int | None = None):
        with self.conn() as c:
            c.execute("""INSERT INTO foreshadowing_tracker (novel_id, created_chapter, description, hint_text, due_by_chapter)
                VALUES (?, ?, ?, ?, ?)""", (novel_id, chapter_num, description, hint_text, due_by))

    def resolve_foreshadowing(self, fs_id: int, resolved_chapter: int, resolved_text: str = ""):
        with self.conn() as c:
            c.execute(
                "UPDATE foreshadowing_tracker SET status='resolved', resolved_chapter=?, resolved_text=?, updated_at=datetime('now') WHERE id=?",
                (resolved_chapter, resolved_text, fs_id)
            )

    def get_active_foreshadowing(self, novel_id: str) -> list[dict]:
        with self.conn() as c:
            rows = c.execute("""SELECT * FROM foreshadowing_tracker WHERE novel_id=? AND status='active'
                ORDER BY due_by_chapter""", (novel_id,)).fetchall()
            return [dict(r) for r in rows]

    def get_all_foreshadowing(self, novel_id: str) -> list[dict]:
        """Get ALL foreshadowing threads regardless of status (for scoring)."""
        with self.conn() as c:
            rows = c.execute("""SELECT * FROM foreshadowing_tracker WHERE novel_id=?
                ORDER BY created_chapter""", (novel_id,)).fetchall()
            return [dict(r) for r in rows]

    def save_location_history(self, novel_id: str, chapter_num: int, location_name: str,
                              event: str = '', state_change: str = ''):
        with self.conn() as c:
            c.execute("INSERT INTO location_history (novel_id, chapter_num, location_name, event, state_change) VALUES (?,?,?,?,?)",
                (novel_id, chapter_num, location_name, event, state_change))

    def get_location_history(self, novel_id: str, location_name: str | None = None) -> list[dict]:
        with self.conn() as c:
            if location_name:
                rows = c.execute("SELECT * FROM location_history WHERE novel_id=? AND location_name=? ORDER BY chapter_num",
                    (novel_id, location_name)).fetchall()
            else:
                rows = c.execute("SELECT * FROM location_history WHERE novel_id=? ORDER BY chapter_num",
                    (novel_id,)).fetchall()
            return [dict(r) for r in rows]

    def save_timeline_event(self, novel_id: str, chapter_num: int, absolute_time: str = '',
                             relative_time: str = '', event_summary: str = ''):
        with self.conn() as c:
            c.execute("INSERT INTO story_timeline (novel_id, chapter_num, absolute_time, relative_time, event_summary) VALUES (?,?,?,?,?)",
                (novel_id, chapter_num, absolute_time, relative_time, event_summary))

    def get_timeline(self, novel_id: str) -> list[dict]:
        with self.conn() as c:
            return [dict(r) for r in c.execute("SELECT * FROM story_timeline WHERE novel_id=? ORDER BY chapter_num",
                (novel_id,)).fetchall()]

    def save_world_state(self, novel_id: str, chapter_num: int, rule_name: str,
                         rule_description: str = '', is_broken: bool = False):
        with self.conn() as c:
            c.execute("INSERT INTO world_state (novel_id, chapter_num, rule_name, rule_description, is_broken) VALUES (?,?,?,?,?)",
                (novel_id, chapter_num, rule_name, rule_description, int(is_broken)))

    def get_world_state(self, novel_id: str) -> list[dict]:
        with self.conn() as c:
            return [dict(r) for r in c.execute("SELECT * FROM world_state WHERE novel_id=? ORDER BY chapter_num",
                (novel_id,)).fetchall()]

    def log_consistency_issue(self, novel_id: str, chapter_num: int, check_type: str,
                               severity: str, description: str, fix_suggestion: str = ''):
        with self.conn() as c:
            c.execute("""INSERT INTO consistency_log (novel_id, chapter_num, check_type, severity, description, fix_suggestion)
                VALUES (?,?,?,?,?,?)""", (novel_id, chapter_num, check_type, severity, description, fix_suggestion))

    def get_consistency_log(self, novel_id: str) -> list[dict]:
        with self.conn() as c:
            return [dict(r) for r in c.execute("SELECT * FROM consistency_log WHERE novel_id=? ORDER BY chapter_num DESC",
                (novel_id,)).fetchall()]

    def save_unsaid(self, novel_id: str, entry: str):
        with self.conn() as c:
            c.execute("INSERT INTO unsaid_book (novel_id, entry) VALUES (?, ?)", (novel_id, entry))

    def get_unsaid(self, novel_id: str) -> list[dict]:
        with self.conn() as c:
            return [dict(r) for r in c.execute("SELECT * FROM unsaid_book WHERE novel_id=? ORDER BY id DESC", (novel_id,)).fetchall()]

    def delete_unsaid(self, entry_id: int):
        with self.conn() as c:
            c.execute("DELETE FROM unsaid_book WHERE id=?", (entry_id,))

    def save_voice_sample(self, novel_id: str, chapter_num: int, before_text: str, after_text: str):
        with self.conn() as c:
            c.execute("INSERT INTO voice_profile (novel_id, chapter_num, before_text, after_text) VALUES (?,?,?,?)",
                (novel_id, chapter_num, before_text[:500], after_text[:500]))

    def get_voice_samples(self, novel_id: str, limit: int = 20) -> list[dict]:
        with self.conn() as c:
            return [dict(r) for r in c.execute(
                "SELECT * FROM voice_profile WHERE novel_id=? ORDER BY id DESC LIMIT ?",
                (novel_id, limit)).fetchall()]

    def save_cost_entry(self, novel_id: str, chapter_num: int, character_name: str,
                         gain: str, loss: str, gain_type: str = 'info', loss_type: str = 'none',
                         is_immediate: bool = True):
        with self.conn() as c:
            c.execute("""INSERT INTO cost_ledger (novel_id, chapter_num, character_name, gain, loss, gain_type, loss_type, is_immediate)
                VALUES (?,?,?,?,?,?,?,?)""",
                (novel_id, chapter_num, character_name, gain, loss, gain_type, loss_type, int(is_immediate)))

    def get_cost_ledger(self, novel_id: str) -> list[dict]:
        with self.conn() as c:
            return [dict(r) for r in c.execute(
                "SELECT * FROM cost_ledger WHERE novel_id=? ORDER BY chapter_num", (novel_id,)).fetchall()]

    def get_character_location(self, novel_id: str, char_name: str) -> str | None:
        """Get a character's latest known location from character_state table."""
        with self.conn() as c:
            row = c.execute(
                """SELECT location FROM character_state
                   WHERE novel_id=? AND char_name=? AND location != ''
                   ORDER BY chapter_num DESC LIMIT 1""",
                (novel_id, char_name)
            ).fetchone()
            return row["location"] if row else None

    def get_relationship_changes(self, novel_id: str) -> list[dict]:
        """Get relationship state transitions from character_state.relationships JSON."""
        with self.conn() as c:
            rows = c.execute(
                """SELECT chapter_num, char_name, relationships FROM character_state
                   WHERE novel_id=? AND relationships != '[]' AND relationships != ''
                   ORDER BY chapter_num""",
                (novel_id,)
            ).fetchall()
        result: list[dict] = []
        for r in rows:
            try:
                rels = json.loads(r["relationships"])
                for rel in rels:
                    result.append({
                        "chapter_num": r["chapter_num"],
                        "char_name": r["char_name"],
                        "target": rel.get("target", ""),
                        "relation": rel.get("relation", ""),
                        "change": rel.get("change", ""),
                    })
            except (json.JSONDecodeError, TypeError):
                pass
        return result

    def get_knowledge_state(self, novel_id: str, char_name: str) -> list[str]:
        """Get what a character knows (from character_state.knowledge JSON array)."""
        with self.conn() as c:
            rows = c.execute(
                """SELECT knowledge FROM character_state
                   WHERE novel_id=? AND char_name=? AND knowledge != '[]' AND knowledge != ''
                   ORDER BY chapter_num DESC LIMIT 5""",
                (novel_id, char_name)
            ).fetchall()
        all_knowledge: list[str] = []
        for r in rows:
            try:
                items = json.loads(r["knowledge"])
                all_knowledge.extend(items)
            except (json.JSONDecodeError, TypeError):
                pass
        return list(dict.fromkeys(all_knowledge))  # dedup preserve order

    def mark_consistency_fixed(self, issue_id: int):
        with self.conn() as c:
            c.execute("UPDATE consistency_log SET was_fixed=1 WHERE id=?", (issue_id,))

    # ═══════════════════ AI Film Studio ═══════════════════

    def save_visual_character(self, novel_id: str, char_key: str, data: dict):
        with self.conn() as c:
            c.execute("""INSERT INTO visual_characters
                (novel_id, char_key, appearance, default_expression, signature_pose,
                 color_palette, costume, injury_marks, voice_character, reference_images)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(novel_id, char_key) DO UPDATE SET
                    appearance=excluded.appearance,
                    default_expression=excluded.default_expression,
                    signature_pose=excluded.signature_pose,
                    color_palette=excluded.color_palette,
                    costume=excluded.costume,
                    injury_marks=excluded.injury_marks,
                    voice_character=excluded.voice_character,
                    reference_images=excluded.reference_images,
                    updated_at=datetime('now')""",
                (novel_id, char_key,
                 data.get("appearance", ""),
                 data.get("default_expression", ""),
                 data.get("signature_pose", ""),
                 data.get("color_palette", ""),
                 data.get("costume", ""),
                 data.get("injury_marks", ""),
                 data.get("voice_character", ""),
                 json.dumps(data.get("reference_images", []), ensure_ascii=False)))

    def get_visual_characters(self, novel_id: str) -> list[dict]:
        with self.conn() as c:
            rows = c.execute(
                "SELECT * FROM visual_characters WHERE novel_id=? ORDER BY id",
                (novel_id,)
            ).fetchall()
            result = []
            for r in rows:
                d = dict(r)
                d["reference_images"] = json.loads(d.get("reference_images", "[]"))
                result.append(d)
            return result

    def save_storyboard(self, novel_id: str, chapter_num: int, data: dict):
        with self.conn() as c:
            c.execute("""INSERT INTO storyboards
                (novel_id, chapter_num, title, total_duration_sec, overall_mood,
                 pacing, color_grade, music_theme, shots_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(novel_id, chapter_num) DO UPDATE SET
                    title=excluded.title,
                    total_duration_sec=excluded.total_duration_sec,
                    overall_mood=excluded.overall_mood,
                    pacing=excluded.pacing,
                    color_grade=excluded.color_grade,
                    music_theme=excluded.music_theme,
                    shots_json=excluded.shots_json""",
                (novel_id, chapter_num,
                 data.get("title", ""),
                 data.get("total_duration_sec", 0),
                 data.get("overall_mood", ""),
                 data.get("pacing", ""),
                 data.get("color_grade", ""),
                 data.get("music_theme", ""),
                 json.dumps(data.get("shots", []), ensure_ascii=False)))

    def get_storyboard(self, novel_id: str, chapter_num: int) -> dict | None:
        with self.conn() as c:
            row = c.execute(
                "SELECT * FROM storyboards WHERE novel_id=? AND chapter_num=?",
                (novel_id, chapter_num)
            ).fetchone()
            if not row:
                return None
            d = dict(row)
            d["shots"] = json.loads(d.pop("shots_json", "[]"))
            return d

    def list_storyboards(self, novel_id: str) -> list[dict]:
        with self.conn() as c:
            rows = c.execute(
                "SELECT * FROM storyboards WHERE novel_id=? ORDER BY chapter_num",
                (novel_id,)
            ).fetchall()
            result = []
            for r in rows:
                d = dict(r)
                d["shots"] = json.loads(d.pop("shots_json", "[]"))
                result.append(d)
            return result

    # ─── Character Voices ───

    def save_character_voice(self, novel_id: str, char_key: str, data: dict) -> None:
        with self.conn() as c:
            c.execute(
                """INSERT INTO character_voices
                   (novel_id, char_key, voice_id, speed, pitch, emotion_default, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
                   ON CONFLICT(novel_id, char_key) DO UPDATE SET
                     voice_id=excluded.voice_id,
                     speed=excluded.speed,
                     pitch=excluded.pitch,
                     emotion_default=excluded.emotion_default,
                     updated_at=datetime('now')""",
                (
                    novel_id, char_key,
                    data.get("voice_id", ""),
                    float(data.get("speed", 1.0)),
                    data.get("pitch", "+0Hz"),
                    data.get("emotion_default", "calm"),
                ),
            )

    def get_character_voices(self, novel_id: str) -> list[dict]:
        with self.conn() as c:
            rows = c.execute(
                "SELECT * FROM character_voices WHERE novel_id=?",
                (novel_id,),
            ).fetchall()
            return [dict(r) for r in rows]
