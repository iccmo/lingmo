"""数据库访问层 — SQLite + WAL"""

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

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
            except:
                pass  # Column already exists

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

    # ═══════════════════ Novel CRUD ═══════════════════

    def create_novel(self, **kw) -> dict:
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
                for tag in kw["tags"]:
                    c.execute("INSERT OR IGNORE INTO novel_tags (novel_id,tag) VALUES (?,?)",
                              (kw["id"], tag))
            if kw.get("char_key"):
                cdef = dict(secrets='[]', personality='', background='', power_level='')
                cdef.update(kw)
                c.execute("""INSERT INTO characters (novel_id,char_key,name,role,
                    personality,background,power_level,secrets)
                    VALUES (:id,:char_key,:name,:role,
                    :personality,:background,:power_level,:secrets)""", cdef)
        return self.get_novel(kw["id"])

    def get_novel(self, novel_id: str) -> Optional[dict]:
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
            char_map = {ch["id"]: ch["name"] for ch in d["characters"]}
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
        'main_arc','current_arc','arc_chapter_start','deleted_at'
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

    def get_chapter(self, novel_id: str, number: int) -> Optional[dict]:
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

    def get_scheduler_state(self, novel_id: str) -> Optional[dict]:
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

    def get_auth(self, platform: str) -> Optional[dict]:
        with self.conn() as c:
            row = c.execute("SELECT * FROM platform_auth WHERE platform=?", (platform,)).fetchone()
            if not row:
                return None
            d = dict(row)
            d["auth_data"] = json.loads(d["auth_data"]) if d["auth_data"] else {}
            return d

    # ═══════════════════ Logging ═══════════════════

    def log(self, novel_id: Optional[str], event: str, detail: dict):
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

    def save_character_voice(self, novel_id: str, char_key: str, voice_data: dict):
        """Persist character voice data to DB."""
        with self.conn() as conn:
            conn.execute(
                "UPDATE characters SET voice_data=?, updated_at=datetime('now') WHERE novel_id=? AND char_key=?",
                (json.dumps(voice_data, ensure_ascii=False), novel_id, char_key))

    def get_character_voices(self, novel_id: str) -> dict[str, dict]:
        """Load all character voice data for a novel."""
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
            if not ch: return
            ver = (c.execute("SELECT COALESCE(MAX(version),0)+1 FROM chapter_versions WHERE chapter_id=?",
                            (ch["id"],)).fetchone()[0])
            c.execute("INSERT INTO chapter_versions (chapter_id, content, word_count, version, reason) VALUES (?,?,?,?,?)",
                     (ch["id"], content, len(content), ver, reason))

    def get_chapter_versions(self, novel_id: str, chapter_num: int) -> list[dict]:
        """Get all version snapshots for a chapter."""
        with self.conn() as c:
            ch = c.execute("SELECT id FROM chapters WHERE novel_id=? AND number=?",
                          (novel_id, chapter_num)).fetchone()
            if not ch: return []
            rows = c.execute("""SELECT id, word_count, version, reason, created_at
                              FROM chapter_versions WHERE chapter_id=? ORDER BY version DESC""",
                            (ch["id"],)).fetchall()
        return [dict(r) for r in rows]

    def get_chapter_version_content(self, version_id: int) -> str | None:
        """Get a specific version's content."""
        with self.conn() as c:
            row = c.execute("SELECT content FROM chapter_versions WHERE id=?", (version_id,)).fetchone()
        return row["content"] if row else None

    def get_cost_summary(self, novel_id: str = "") -> dict:
        """Get cost summary for a novel or all novels."""
        with self.conn() as c:
            if novel_id:
                rows = c.execute("""SELECT model, COUNT(*) as calls,
                    SUM(prompt_tokens) as pt, SUM(completion_tokens) as ct,
                    SUM(total_tokens) as tt, SUM(cost) as total_cost
                    FROM cost_logs WHERE novel_id=? GROUP BY model""", (novel_id,)).fetchall()
            else:
                rows = c.execute("""SELECT model, COUNT(*) as calls,
                    SUM(prompt_tokens) as pt, SUM(completion_tokens) as ct,
                    SUM(total_tokens) as tt, SUM(cost) as total_cost
                    FROM cost_logs GROUP BY model""").fetchall()
        return {
            "by_model": [dict(r) for r in rows],
            "total_cost": round(sum(r["total_cost"] for r in rows), 4),
            "total_tokens": sum(r["tt"] for r in rows),
            "total_calls": sum(r["calls"] for r in rows),
        }

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

    def get_provider(self, provider_id: str) -> Optional[dict]:
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
