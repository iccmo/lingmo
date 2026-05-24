# 灵墨 — 数据库设计

**版本**: 2.0 | **日期**: 2026-05-19 | **数据库**: SQLite 3 | **表数**: 13

---

## 0. 选型理由

- 单用户本地运行，SQLite 零配置
- WAL 模式支持读写并发
- 外键 + UNIQUE 保证数据完整性
- 一个 `.db` 文件，备份即复制
- V2 升级 PostgreSQL：SQLAlchemy 换一行配置

---

## 1. ER 图

```
                    ┌─────────────────────────────────────────────────┐
                    │                  novels                          │
                    │  id, title, author, synopsis, genre, status,     │
                    │  mode, main_arc, current_arc, arc_chapter_start, │
                    │  world_*, power_system, world_rules(JSON),       │
                    │  created_at, updated_at, deleted_at              │
                    └──┬──┬──┬──┬──┬──┬──┬──┬──┬──┬──────────────────┘
                       │  │  │  │  │  │  │  │  │  │
         ┌─────────────┘  │  │  │  │  │  │  │  │  └──────────┐
         ▼                │  │  │  │  │  │  │  └───────┐      │
  ┌─────────────┐         │  │  │  │  │  │  ┌───────┐ │      │
  │  characters  │         │  │  │  │  │  │  │       │ │      │
  │  id, novel_id│         │  │  │  │  │  │  │       │ │      │
  │  char_key,   │         │  │  │  │  │  │  │       │ │      │
  │  name, role, │         │  │  │  │  │  │  │       │ │      │
  │  personality,│         │  │  │  │  │  │  │       │ │      │
  │  power_level,│         │  │  │  │  │  │  │       │ │      │
  │  secrets(JSON│         │  │  │  │  │  │  │       │ │      │
  │  status      │         │  │  │  │  │  │  │       │ │      │
  └──────┬──────┘         │  │  │  │  │  │  │       │ │      │
         │                │  │  │  │  │  │  │       │ │      │
         ▼                │  │  │  │  │  │  │       │ │      │
┌──────────────────┐      │  │  │  │  │  │  │       │ │      │
│ character_relations│    │  │  │  │  │  │  │       │ │      │
│ id, novel_id,      │    │  │  │  │  │  │  │       │ │      │
│ char_1_id, char_2_id, │  │  │  │  │  │  │  │       │ │      │
│ relation           │    │  │  │  │  │  │  │       │ │      │
└────────────────────┘    │  │  │  │  │  │  │       │ │      │
                          │  │  │  │  │  │  │       │ │      │
              ┌───────────┘  │  │  │  │  │  │       │ │      │
              ▼              │  │  │  │  │  │       │ │      │
       ┌────────────┐        │  │  │  │  │  │       │ │      │
       │  factions   │        │  │  │  │  │  │       │ │      │
       │  id, novel_id       │  │  │  │  │  │       │ │      │
       │  name, desc, leader  │  │  │  │  │  │       │ │      │
       └────────────┘        │  │  │  │  │  │       │ │      │
                             │  │  │  │  │  │       │ │      │
                 ┌───────────┘  │  │  │  │  │       │ │      │
                 ▼              │  │  │  │  │       │ │      │
          ┌─────────────┐       │  │  │  │  │       │ │      │
          │   chapters   │       │  │  │  │  │       │ │      │
          │  id, novel_id│       │  │  │  │  │       │ │      │
          │  number, title│      │  │  │  │  │       │ │      │
          │  word_count,  │      │  │  │  │  │       │ │      │
          │  content,     │      │  │  │  │  │       │ │      │
          │  quality_score│      │  │  │  │  │       │ │      │
          │  model_used,  │      │  │  │  │  │       │ │      │
          │  prompt_version      │  │  │  │  │       │ │      │
          │  cost,        │      │  │  │  │  │       │ │      │
          │  edit_ratio   │      │  │  │  │  │       │ │      │
          └──┬───┬───────┘      │  │  │  │  │       │ │      │
             │   │              │  │  │  │  │       │ │      │
             │   └───────┐      │  │  │  │  │       │ │      │
             ▼           ▼      │  │  │  │  │       │ │      │
    ┌──────────────┐ ┌──────────────────┐  │  │  │  │  │
    │chapter_drafts│ │ publish_records  │  │  │  │  │  │
    │ id, chapter_id │ id, chapter_id   │  │  │  │  │  │
    │ draft_label, │ │ platform, url,   │  │  │  │  │  │
    │ direction,   │ │ success, error,  │  │  │  │  │  │
    │ preview, hook│ │ screenshot_path  │  │  │  │  │  │
    │ is_selected  │ └──────────────────┘  │  │  │  │  │
    └──────────────┘                       │  │  │  │  │
                                           │  │  │  │  │
                               ┌───────────┘  │  │  │  │
                               ▼              │  │  │  │
                        ┌────────────┐         │  │  │  │
                        │ plot_points │         │  │  │  │
                        │ id, novel_id│         │  │  │  │
                        │ type, content│        │  │  │  │
                        │ is_resolved │         │  │  │  │
                        │ sort_order  │         │  │  │  │
                        └────────────┘         │  │  │  │
                                               │  │  │  │
                                   ┌───────────┘  │  │  │
                                   ▼              │  │  │
                            ┌──────────────┐      │  │  │
                            │  run_logs     │      │  │  │
                            │  id, novel_id │      │  │  │
                            │  event, detail│      │  │  │
                            │  (JSON)       │      │  │  │
                            │  created_at   │      │  │  │
                            └──────────────┘      │  │  │
                                                  │  │  │
                                      ┌───────────┘  │  │
                                      ▼              │  │
                               ┌────────────────┐    │  │
                               │reanchor_snapshots│   │  │
                               │ id, novel_id     │   │  │
                               │ trigger_chapter  │   │  │
                               │ world_snapshot   │   │  │
                               │ chars_snapshot   │   │  │
                               │ plot_snapshot    │   │  │
                               │ (all JSON)       │   │  │
                               └──────────────────┘   │  │
                                                      │  │
                                          ┌───────────┘  │
                                          ▼              │
                                   ┌───────────────┐     │
                                   │ scheduler_state│     │
                                   │ novel_id (PK)  │     │
                                   │ is_running,    │     │
                                   │ next_run_at,   │     │
                                   │ last_run_at,   │     │
                                   │ last_result,   │     │
                                   │ failures       │     │
                                   └────────────────┘     │
                                                          │
                                              ┌───────────┘
                                              ▼
                                       ┌──────────────┐
                                       │ platform_auth │
                                       │ platform (PK) │
                                       │ auth_data(JSON│
                                       │ is_valid      │
                                       │ updated_at    │
                                       └──────────────┘
```

---

## 2. 完整 DDL

```sql
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

-- ═══════════════════════════════════════════
-- 1. novels — 小说主表
-- ═══════════════════════════════════════════
CREATE TABLE novels (
    id                TEXT PRIMARY KEY,
    title             TEXT NOT NULL,
    author            TEXT NOT NULL DEFAULT 'AI',
    synopsis          TEXT DEFAULT '',
    genre             TEXT NOT NULL DEFAULT '玄幻',
    status            TEXT NOT NULL DEFAULT 'draft'
                      CHECK(status IN ('draft','writing','paused','completed')),
    mode              TEXT NOT NULL DEFAULT 'creator'
                      CHECK(mode IN ('auto','creator')),

    -- 世界观
    world_name        TEXT DEFAULT '',
    world_era         TEXT DEFAULT '',
    world_geo         TEXT DEFAULT '',
    power_system      TEXT DEFAULT '',
    world_rules       TEXT DEFAULT '[]',       -- JSON array

    -- 情节
    main_arc          TEXT DEFAULT '',
    current_arc       TEXT DEFAULT '开篇',
    arc_chapter_start INTEGER NOT NULL DEFAULT 1,

    created_at        TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at        TEXT NOT NULL DEFAULT (datetime('now')),
    deleted_at        TEXT                         -- 软删除
);

-- ═══════════════════════════════════════════
-- 2. characters — 角色
-- ═══════════════════════════════════════════
CREATE TABLE characters (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    novel_id        TEXT NOT NULL REFERENCES novels(id) ON DELETE CASCADE,
    char_key        TEXT NOT NULL,             -- "protagonist", "villain_1"
    name            TEXT NOT NULL,
    role            TEXT NOT NULL DEFAULT '配角'
                    CHECK(role IN ('主角','反派','配角','导师','路人')),
    personality     TEXT DEFAULT '',
    background      TEXT DEFAULT '',
    power_level     TEXT DEFAULT '',
    secrets         TEXT DEFAULT '[]',         -- JSON array
    status          TEXT NOT NULL DEFAULT 'alive'
                    CHECK(status IN ('alive','injured','dead','missing')),
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(novel_id, char_key)
);

-- ═══════════════════════════════════════════
-- 3. character_relations — 角色关系
-- ═══════════════════════════════════════════
CREATE TABLE character_relations (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    novel_id        TEXT NOT NULL REFERENCES novels(id) ON DELETE CASCADE,
    char_1_id       INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    char_2_id       INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    relation        TEXT NOT NULL,            -- "师徒", "仇敌", "道侣"
    UNIQUE(novel_id, char_1_id, char_2_id),
    CHECK(char_1_id != char_2_id)
);

-- ═══════════════════════════════════════════
-- 4. factions — 势力/门派
-- ═══════════════════════════════════════════
CREATE TABLE factions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    novel_id        TEXT NOT NULL REFERENCES novels(id) ON DELETE CASCADE,
    name            TEXT NOT NULL,
    description     TEXT DEFAULT '',
    leader          TEXT DEFAULT '',
    sort_order      INTEGER DEFAULT 0
);

-- ═══════════════════════════════════════════
-- 5. chapters — 章节
-- ═══════════════════════════════════════════
CREATE TABLE chapters (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    novel_id          TEXT NOT NULL REFERENCES novels(id) ON DELETE CASCADE,
    number            INTEGER NOT NULL,
    title             TEXT NOT NULL,
    word_count        INTEGER NOT NULL DEFAULT 0,
    summary           TEXT DEFAULT '',
    content           TEXT DEFAULT '',         -- 完整正文
    ending_hook       TEXT DEFAULT '',
    key_events        TEXT DEFAULT '[]',       -- JSON array
    revelations       TEXT DEFAULT '[]',       -- JSON array
    quality_score     REAL DEFAULT 0,          -- 0.0 ~ 1.0
    model_used        TEXT DEFAULT '',
    prompt_version    TEXT DEFAULT '',         -- 使用的 prompt 版本号
    prompt_tokens     INTEGER DEFAULT 0,
    completion_tokens INTEGER DEFAULT 0,
    cost              REAL DEFAULT 0,          -- API 调用费用 (USD)
    generation_duration_ms INTEGER DEFAULT 0,
    edit_ratio        REAL DEFAULT 0,          -- 人工修改比例 0~1
    generated_at      TEXT DEFAULT (datetime('now')),
    published_at      TEXT,                    -- 首次发布时间
    UNIQUE(novel_id, number)
);

-- ═══════════════════════════════════════════
-- 6. chapter_drafts — 章节草稿（模式 B）
-- ═══════════════════════════════════════════
CREATE TABLE chapter_drafts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    chapter_id      INTEGER REFERENCES chapters(id) ON DELETE CASCADE,
    draft_label     TEXT NOT NULL,            -- "A", "B", "C"
    direction       TEXT NOT NULL,
    preview         TEXT DEFAULT '',
    hook            TEXT DEFAULT '',
    is_selected     INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ═══════════════════════════════════════════
-- 7. plot_points — 剧情点 & 伏笔
-- ═══════════════════════════════════════════
CREATE TABLE plot_points (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    novel_id        TEXT NOT NULL REFERENCES novels(id) ON DELETE CASCADE,
    type            TEXT NOT NULL DEFAULT 'plot'
                    CHECK(type IN ('plot','foreshadowing')),
    content         TEXT NOT NULL,
    is_resolved     INTEGER NOT NULL DEFAULT 0,
    resolved_at     TEXT,
    sort_order      INTEGER DEFAULT 0,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ═══════════════════════════════════════════
-- 8. publish_records — 发布记录
-- ═══════════════════════════════════════════
CREATE TABLE publish_records (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    chapter_id      INTEGER NOT NULL REFERENCES chapters(id) ON DELETE CASCADE,
    platform        TEXT NOT NULL,            -- "fanqie", "feilu", "qidian"
    success         INTEGER NOT NULL DEFAULT 1,
    url             TEXT DEFAULT '',
    error           TEXT DEFAULT '',
    screenshot_path TEXT DEFAULT '',          -- 发布确认截图
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ═══════════════════════════════════════════
-- 9. reanchor_snapshots — 30章重锚快照
-- ═══════════════════════════════════════════
CREATE TABLE reanchor_snapshots (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    novel_id          TEXT NOT NULL REFERENCES novels(id) ON DELETE CASCADE,
    trigger_chapter   INTEGER NOT NULL,       -- 触发时的章节数 (30, 60, 90...)
    world_snapshot    TEXT NOT NULL,           -- JSON: 当时的世界观摘要
    chars_snapshot    TEXT NOT NULL,           -- JSON: 当时的角色状态
    plot_snapshot     TEXT NOT NULL,           -- JSON: 当时的伏笔/剧情点
    created_at        TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(novel_id, trigger_chapter)
);

-- ═══════════════════════════════════════════
-- 10. scheduler_state — 全自动调度状态
-- ═══════════════════════════════════════════
CREATE TABLE scheduler_state (
    novel_id          TEXT PRIMARY KEY REFERENCES novels(id) ON DELETE CASCADE,
    is_running        INTEGER NOT NULL DEFAULT 0,
    next_run_at       TEXT,                   -- ISO datetime
    last_run_at       TEXT,
    last_result       TEXT DEFAULT ''         -- "success" / "failed" / "skipped"
                      CHECK(last_result IN ('','success','failed','skipped')),
    consecutive_failures INTEGER NOT NULL DEFAULT 0,
    updated_at        TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ═══════════════════════════════════════════
-- 11. platform_auth — 平台登录态
-- ═══════════════════════════════════════════
CREATE TABLE platform_auth (
    platform          TEXT PRIMARY KEY,       -- "fanqie", "feilu", "qidian"
    auth_data         TEXT NOT NULL,          -- JSON: Playwright storageState
    is_valid          INTEGER NOT NULL DEFAULT 0,
    last_verified_at  TEXT,
    updated_at        TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ═══════════════════════════════════════════
-- 12. run_logs — 运行日志
-- ═══════════════════════════════════════════
CREATE TABLE run_logs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    novel_id        TEXT REFERENCES novels(id) ON DELETE SET NULL,
    event           TEXT NOT NULL,            -- "chapter.generated", "publish.success", "error.critical"
    detail          TEXT DEFAULT '{}',        -- JSON: {duration_ms, model, tokens, error_msg, ...}
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ═══════════════════════════════════════════
-- 13. novel_tags — 小说标签（多对多）
-- ═══════════════════════════════════════════
CREATE TABLE novel_tags (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    novel_id        TEXT NOT NULL REFERENCES novels(id) ON DELETE CASCADE,
    tag             TEXT NOT NULL,            -- "系统流", "扮猪吃虎", "热血"
    UNIQUE(novel_id, tag)
);

-- ═══════════════════════════════════════════
-- 索引
-- ═══════════════════════════════════════════
CREATE INDEX idx_characters_novel    ON characters(novel_id);
CREATE INDEX idx_chapters_novel      ON chapters(novel_id);
CREATE INDEX idx_chapters_published  ON chapters(novel_id, published_at);
CREATE INDEX idx_plot_points_novel   ON plot_points(novel_id, type, is_resolved);
CREATE INDEX idx_run_logs_novel      ON run_logs(novel_id, event);
CREATE INDEX idx_run_logs_time       ON run_logs(created_at);
CREATE INDEX idx_publish_records_ch  ON publish_records(chapter_id);
CREATE INDEX idx_drafts_chapter      ON chapter_drafts(chapter_id);
CREATE INDEX idx_relations_novel     ON character_relations(novel_id);

-- 软删除视图
CREATE VIEW active_novels AS
    SELECT * FROM novels WHERE deleted_at IS NULL;
```

---

## 3. 关键查询

```sql
-- Dashboard: 小说列表 + 进度
SELECT n.id, n.title, n.genre, n.status, n.mode,
       COUNT(c.id) as ch_count,
       COALESCE(SUM(c.word_count), 0) as total_words,
       COALESCE(SUM(c.cost), 0) as total_cost,
       (SELECT title FROM chapters WHERE novel_id=n.id ORDER BY number DESC LIMIT 1) as latest
FROM active_novels n
LEFT JOIN chapters c ON c.novel_id = n.id
GROUP BY n.id
ORDER BY n.updated_at DESC;

-- 小说详情：全部章节
SELECT number, title, word_count, quality_score, model_used,
       prompt_version, cost, generated_at, published_at
FROM chapters WHERE novel_id = ? ORDER BY number;

-- 质量趋势：最近 10 章
SELECT number, quality_score, word_count, edit_ratio
FROM chapters WHERE novel_id = ?
ORDER BY number DESC LIMIT 10;

-- 伏笔状态
SELECT type, content, is_resolved, created_at
FROM plot_points WHERE novel_id = ?
ORDER BY is_resolved, created_at;

-- 发布历史
SELECT c.number, c.title, pr.platform, pr.success, pr.error, pr.created_at
FROM publish_records pr
JOIN chapters c ON c.id = pr.chapter_id
WHERE c.novel_id = ?
ORDER BY pr.created_at DESC;

-- 调度状态（模式 A）
SELECT ss.*, n.title
FROM scheduler_state ss
JOIN novels n ON n.id = ss.novel_id
WHERE ss.is_running = 1;

-- 成本统计（本月）
SELECT n.title,
       COUNT(c.id) as chapters,
       COALESCE(SUM(c.cost), 0) as total_cost,
       COALESCE(SUM(c.prompt_tokens + c.completion_tokens), 0) as total_tokens
FROM novels n
JOIN chapters c ON c.novel_id = n.id
WHERE c.generated_at > datetime('now', 'start of month')
GROUP BY n.id;

-- 平台登录态检查
SELECT platform, is_valid, last_verified_at
FROM platform_auth;
```

---

## 4. run_logs 的 detail JSON Schema

```json
{
  "chapter.generated": {
    "duration_ms": 18500, "model": "gpt-4o",
    "prompt_version": "v3", "prompt_tokens": 3200,
    "completion_tokens": 2800, "cost": 0.05, "chapter": 42
  },
  "chapter.quality_failed": {
    "chapter": 42, "reason": "short", "word_count": 800
  },
  "publish.success": {
    "chapter": 42, "platform": "fanqie", "url": "https://..."
  },
  "publish.failed": {
    "chapter": 42, "platform": "fanqie",
    "error": "selector_mismatch", "screenshot": "/data/publish_logs/err_42.png"
  },
  "reanchor.triggered": {
    "chapter": 30, "duration_ms": 22000
  },
  "mode.switched": {
    "from": "auto", "to": "creator"
  },
  "error.critical": {
    "error": "state_file_corrupted", "path": "..."
  }
}
```

---

## 5. JSON → SQLite 迁移

```python
def migrate(json_dir: str, db_path: str):
    import json, sqlite3
    from pathlib import Path

    conn = sqlite3.connect(db_path)
    conn.executescript(open("schema.sql").read())

    for f in Path(json_dir).glob("*.json"):
        d = json.loads(f.read_text())
        nid = d["novel_id"]

        conn.execute("""INSERT INTO novels (id,title,author,synopsis,genre,status,mode,
            world_name,world_era,world_geo,power_system,world_rules,
            main_arc,current_arc,arc_chapter_start)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (nid, d["title"], d["author"], d["synopsis"], d["genre"],
             "writing", "creator",
             d["world"]["name"], d["world"]["era"], d["world"]["geography"],
             d["world"]["power_system"], json.dumps(d["world"].get("rules", [])),
             d["plot"].get("main_arc",""), d["plot"].get("current_arc","开篇"),
             d["plot"].get("arc_chapter_start", 1)))

        for ch in d.get("characters", []):
            conn.execute("""INSERT INTO characters (novel_id,char_key,name,role,
                personality,background,power_level,secrets,status)
                VALUES (?,?,?,?,?,?,?,?,?)""",
                (nid, ch["id"], ch["name"], ch["role"],
                 ch.get("personality",""), ch.get("background",""),
                 ch.get("current_power_level",""),
                 json.dumps(ch.get("secrets",[])), ch.get("status","alive")))

        for ch in d.get("chapters", []):
            conn.execute("""INSERT INTO chapters (novel_id,number,title,word_count,
                summary,ending_hook,key_events,revelations,generated_at)
                VALUES (?,?,?,?,?,?,?,?,?)""",
                (nid, ch["number"], ch["title"], ch["word_count"],
                 ch["summary"], ch.get("ending_hook",""),
                 json.dumps(ch.get("key_events",[])),
                 json.dumps(ch.get("revelations",[])),
                 ch.get("generated_at","")))

        for pt in d.get("plot",{}).get("next_plot_points",[]):
            conn.execute("INSERT INTO plot_points (novel_id,type,content) VALUES (?,?,?)",
                         (nid, "plot", pt))
        for fh in d.get("plot",{}).get("foreshadowing",[]):
            conn.execute("INSERT INTO plot_points (novel_id,type,content) VALUES (?,?,?)",
                         (nid, "foreshadowing", fh))

    conn.commit(); conn.close()
```

---

## 6. 数据访问层

```python
# novel_writer/database.py
import sqlite3, json
from contextlib import contextmanager
from pathlib import Path

SCHEMA_PATH = Path(__file__).parent.parent / "schema.sql"

class Database:
    def __init__(self, db_path: str = "data/novel_writer.db"):
        self.db_path = db_path
        self._init()

    def _init(self):
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        with self.conn() as c:
            if SCHEMA_PATH.exists():
                c.executescript(SCHEMA_PATH.read_text())

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

    # ── Novel ──
    def create_novel(self, **kw) -> dict: ...
    def get_novel(self, id: str) -> dict | None: ...
    def list_novels(self, include_deleted=False) -> list[dict]: ...
    def update_novel(self, id: str, **kw): ...
    def soft_delete_novel(self, id: str): ...

    # ── Chapters ──
    def add_chapter(self, novel_id: str, **kw) -> int: ...
    def get_chapters(self, novel_id: str) -> list[dict]: ...
    def update_chapter(self, id: int, **kw): ...

    # ── Drafts ──
    def save_drafts(self, chapter_id: int, drafts: list[dict]): ...
    def get_drafts(self, chapter_id: int) -> list[dict]: ...

    # ── Scheduler ──
    def set_scheduler_state(self, novel_id: str, **kw): ...
    def get_scheduler_state(self, novel_id: str) -> dict | None: ...

    # ── Auth ──
    def save_auth(self, platform: str, data: dict): ...
    def get_auth(self, platform: str) -> dict | None: ...

    # ── Logging ──
    def log(self, novel_id: str, event: str, detail: dict): ...
    def get_logs(self, limit=50) -> list[dict]: ...

    # ── Reanchor ──
    def save_snapshot(self, novel_id: str, chapter: int, world: dict, chars: dict, plot: dict): ...
    def get_latest_snapshot(self, novel_id: str) -> dict | None: ...
```

---

## 7. 表职责速查

| 表 | 行数增长 | 对应需求 |
|----|---------|---------|
| novels | 1/本 | FR-01 |
| characters | 5-20/本 | US-C1 |
| character_relations | 0-30/本 | US-C1 |
| factions | 0-10/本 | FR-01 |
| chapters | ~365/本/年 | FR-A06, FR-B02 |
| chapter_drafts | ~3/章 (模式B) | FR-B01 |
| plot_points | 10-50/本 | FR-E01, FR-E06 |
| publish_records | 1/发布 | FR-P04 |
| reanchor_snapshots | 1/30章 | FR-E05 |
| scheduler_state | 1/本 | FR-A04 |
| platform_auth | 1/平台 | FR-P01 |
| run_logs | ~2/天/本 | NFR-08 |
| novel_tags | 3-8/本 | FR-01 |
