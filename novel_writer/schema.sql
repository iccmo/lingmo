PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS novels (
    id                TEXT PRIMARY KEY,
    title             TEXT NOT NULL,
    author            TEXT NOT NULL DEFAULT 'AI',
    synopsis          TEXT DEFAULT '',
    genre             TEXT NOT NULL DEFAULT '玄幻',
    status            TEXT NOT NULL DEFAULT 'draft'
                      CHECK(status IN ('draft','writing','paused','completed')),
    mode              TEXT NOT NULL DEFAULT 'creator'
                      CHECK(mode IN ('auto','creator')),
    world_name        TEXT DEFAULT '',
    world_era         TEXT DEFAULT '',
    world_geo         TEXT DEFAULT '',
    power_system      TEXT DEFAULT '',
    world_rules       TEXT DEFAULT '[]',
    main_arc          TEXT DEFAULT '',
    current_arc       TEXT DEFAULT '开篇',
    arc_chapter_start INTEGER NOT NULL DEFAULT 1,
    created_at        TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at        TEXT NOT NULL DEFAULT (datetime('now')),
    deleted_at        TEXT
);

CREATE TABLE IF NOT EXISTS characters (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    novel_id        TEXT NOT NULL REFERENCES novels(id) ON DELETE CASCADE,
    char_key        TEXT NOT NULL,
    name            TEXT NOT NULL,
    role            TEXT NOT NULL DEFAULT '配角'
                    CHECK(role IN ('主角','反派','配角','导师','路人')),
    personality     TEXT DEFAULT '',
    background      TEXT DEFAULT '',
    power_level     TEXT DEFAULT '',
    secrets         TEXT DEFAULT '[]',
    status          TEXT NOT NULL DEFAULT 'alive'
                    CHECK(status IN ('alive','injured','dead','missing')),
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(novel_id, char_key)
);

CREATE TABLE IF NOT EXISTS character_relations (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    novel_id        TEXT NOT NULL REFERENCES novels(id) ON DELETE CASCADE,
    char_1_id       INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    char_2_id       INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    relation        TEXT NOT NULL,
    UNIQUE(novel_id, char_1_id, char_2_id),
    CHECK(char_1_id != char_2_id)
);

CREATE TABLE IF NOT EXISTS factions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    novel_id        TEXT NOT NULL REFERENCES novels(id) ON DELETE CASCADE,
    name            TEXT NOT NULL,
    description     TEXT DEFAULT '',
    leader          TEXT DEFAULT '',
    sort_order      INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS chapters (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    novel_id          TEXT NOT NULL REFERENCES novels(id) ON DELETE CASCADE,
    number            INTEGER NOT NULL,
    title             TEXT NOT NULL,
    word_count        INTEGER NOT NULL DEFAULT 0,
    summary           TEXT DEFAULT '',
    content           TEXT DEFAULT '',
    ending_hook       TEXT DEFAULT '',
    key_events        TEXT DEFAULT '[]',
    revelations       TEXT DEFAULT '[]',
    quality_score     REAL DEFAULT 0,
    model_used        TEXT DEFAULT '',
    prompt_version    TEXT DEFAULT '',
    prompt_tokens     INTEGER DEFAULT 0,
    completion_tokens INTEGER DEFAULT 0,
    cost              REAL DEFAULT 0,
    generation_duration_ms INTEGER DEFAULT 0,
    edit_ratio        REAL DEFAULT 0,
    generated_at      TEXT DEFAULT (datetime('now')),
    published_at      TEXT,
    UNIQUE(novel_id, number)
);

CREATE TABLE IF NOT EXISTS chapter_drafts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    chapter_id      INTEGER REFERENCES chapters(id) ON DELETE CASCADE,
    draft_label     TEXT NOT NULL,
    direction       TEXT NOT NULL,
    preview         TEXT DEFAULT '',
    hook            TEXT DEFAULT '',
    is_selected     INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS plot_points (
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

CREATE TABLE IF NOT EXISTS publish_records (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    chapter_id      INTEGER NOT NULL REFERENCES chapters(id) ON DELETE CASCADE,
    platform        TEXT NOT NULL,
    success         INTEGER NOT NULL DEFAULT 1,
    url             TEXT DEFAULT '',
    error           TEXT DEFAULT '',
    screenshot_path TEXT DEFAULT '',
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS reanchor_snapshots (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    novel_id          TEXT NOT NULL REFERENCES novels(id) ON DELETE CASCADE,
    trigger_chapter   INTEGER NOT NULL,
    world_snapshot    TEXT NOT NULL,
    chars_snapshot    TEXT NOT NULL,
    plot_snapshot     TEXT NOT NULL,
    created_at        TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(novel_id, trigger_chapter)
);

CREATE TABLE IF NOT EXISTS scheduler_state (
    novel_id          TEXT PRIMARY KEY REFERENCES novels(id) ON DELETE CASCADE,
    is_running        INTEGER NOT NULL DEFAULT 0,
    next_run_at       TEXT,
    last_run_at       TEXT,
    last_result       TEXT DEFAULT ''
                      CHECK(last_result IN ('','success','failed','skipped')),
    consecutive_failures INTEGER NOT NULL DEFAULT 0,
    updated_at        TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS platform_auth (
    platform          TEXT PRIMARY KEY,
    auth_data         TEXT NOT NULL,
    is_valid          INTEGER NOT NULL DEFAULT 0,
    last_verified_at  TEXT,
    updated_at        TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS run_logs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    novel_id        TEXT REFERENCES novels(id) ON DELETE SET NULL,
    event           TEXT NOT NULL,
    detail          TEXT DEFAULT '{}',
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS novel_tags (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    novel_id        TEXT NOT NULL REFERENCES novels(id) ON DELETE CASCADE,
    tag             TEXT NOT NULL,
    UNIQUE(novel_id, tag)
);

CREATE INDEX IF NOT EXISTS idx_characters_novel    ON characters(novel_id);
CREATE INDEX IF NOT EXISTS idx_chapters_novel      ON chapters(novel_id);
CREATE INDEX IF NOT EXISTS idx_chapters_published  ON chapters(novel_id, published_at);
CREATE INDEX IF NOT EXISTS idx_plot_points_novel   ON plot_points(novel_id, type, is_resolved);
CREATE INDEX IF NOT EXISTS idx_run_logs_novel      ON run_logs(novel_id, event);
CREATE INDEX IF NOT EXISTS idx_run_logs_time       ON run_logs(created_at);
CREATE INDEX IF NOT EXISTS idx_publish_records_ch  ON publish_records(chapter_id);
CREATE INDEX IF NOT EXISTS idx_drafts_chapter      ON chapter_drafts(chapter_id);
CREATE INDEX IF NOT EXISTS idx_relations_novel     ON character_relations(novel_id);

CREATE VIEW IF NOT EXISTS active_novels AS
    SELECT * FROM novels WHERE deleted_at IS NULL;

-- V3: Embedding storage for RAG context retrieval
CREATE TABLE IF NOT EXISTS chapter_embeddings (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    chapter_id      INTEGER NOT NULL REFERENCES chapters(id) ON DELETE CASCADE,
    chunk_index     INTEGER NOT NULL DEFAULT 0,
    chunk_text      TEXT NOT NULL,               -- 摘要片段 (≤ 500 chars)
    embedding       TEXT NOT NULL,               -- JSON float array (1536-dim)
    model           TEXT NOT NULL DEFAULT 'text-embedding-3-small',
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(chapter_id, chunk_index)
);
CREATE INDEX IF NOT EXISTS idx_embeddings_chapter ON chapter_embeddings(chapter_id);

-- V4: Model provider configuration
CREATE TABLE IF NOT EXISTS model_providers (
    id              TEXT PRIMARY KEY,           -- "openai", "deepseek", "kimi"
    name            TEXT NOT NULL,              -- "OpenAI GPT-4o"
    base_url        TEXT NOT NULL,              -- "https://api.openai.com/v1"
    api_key         TEXT NOT NULL DEFAULT '',   -- encrypted or env-ref
    models          TEXT NOT NULL DEFAULT '[]', -- JSON: ["gpt-4o","gpt-4o-mini"]
    is_enabled      INTEGER NOT NULL DEFAULT 1,
    priority        INTEGER NOT NULL DEFAULT 0, -- higher = preferred
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Default providers (国内 + OpenAI + Google)
INSERT OR IGNORE INTO model_providers (id, name, base_url, api_key, models, priority) VALUES
  -- 国际
  ('openai',  'OpenAI GPT',    'https://api.openai.com/v1',                     '', '["gpt-4o","gpt-4o-mini"]', 10),
  ('google',  'Google Gemini', 'https://generativelanguage.googleapis.com/v1beta/openai', '', '["gemini-2.5-flash","gemini-2.5-pro"]', 8),
  -- 国内
  ('deepseek','DeepSeek',      'https://api.deepseek.com',                       '', '["deepseek-v4-flash","deepseek-v4-pro"]', 9),
  ('qwen',    '通义千问',       'https://dashscope.aliyuncs.com/compatible-mode/v1', '', '["qwen-turbo","qwen-plus","qwen-max"]', 7),
  ('kimi',    'Kimi 月之暗面',   'https://api.moonshot.cn/v1',                    '', '["moonshot-v1-8k","moonshot-v1-32k","moonshot-v1-128k"]', 7),
  ('zhipu',   '智谱 ChatGLM',  'https://open.bigmodel.cn/api/paas/v4',           '', '["glm-4-plus","glm-4-flash"]', 6),
  ('doubao',  '字节豆包',       'https://ark.cn-beijing.volces.com/api/v3',       '', '["doubao-pro-256k","doubao-lite-128k"]', 6),
  ('baidu',   '百度文心',       'https://qianfan.baidubce.com/v2',                '', '["ernie-4.0-turbo","ernie-speed"]', 5),
  ('xunfei',  '讯飞星火',       'https://spark-api-open.xf-yun.com/v1',           '', '["spark-lite","spark-pro","spark-max"]', 5),
  ('minimax', 'MiniMax',       'https://api.minimax.chat/v1',                    '', '["abab7-chat","abab6.5s-chat"]', 4);

-- Novel model assignment
-- V4: provider_id added in database.py _init()
-- V5: Chapter performance tracking
CREATE TABLE IF NOT EXISTS performance_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    novel_id TEXT NOT NULL,
    chapter_number INTEGER NOT NULL,
    views INTEGER DEFAULT 0,
    comments INTEGER DEFAULT 0,
    collected_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (novel_id) REFERENCES novels(id)
);
CREATE INDEX IF NOT EXISTS idx_perf_novel ON performance_logs(novel_id, chapter_number);
-- V6: Per-novel style profiles
CREATE TABLE IF NOT EXISTS style_profiles (
    novel_id TEXT PRIMARY KEY,
    profile_json TEXT NOT NULL DEFAULT '{}',
    version INTEGER DEFAULT 1,
    updated_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (novel_id) REFERENCES novels(id) ON DELETE CASCADE
);


-- V8: Audio player persistent storage (replaces localStorage)
CREATE TABLE IF NOT EXISTS audio_bookmarks (
    id            TEXT PRIMARY KEY,
    novel_id      TEXT NOT NULL,
    novel_title   TEXT NOT NULL DEFAULT '',
    chapter_num   INTEGER NOT NULL,
    chapter_title TEXT NOT NULL DEFAULT '',
    position      INTEGER NOT NULL DEFAULT 0,
    note          TEXT NOT NULL DEFAULT '',
    tag           TEXT NOT NULL DEFAULT '',
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS audio_settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS audio_playlist (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    novel_id      TEXT NOT NULL,
    novel_title   TEXT NOT NULL DEFAULT '',
    chapter_num   INTEGER NOT NULL,
    chapter_title TEXT NOT NULL DEFAULT '',
    sort_order    INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS audio_stats (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    stat_key      TEXT NOT NULL UNIQUE,
    stat_value    TEXT NOT NULL DEFAULT '0',
    updated_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS audio_progress (
    novel_id    TEXT PRIMARY KEY REFERENCES novels(id) ON DELETE CASCADE,
    chapter_num INTEGER NOT NULL,
    position_sec REAL NOT NULL DEFAULT 0,
    updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

-- V9: Cost tracking log
CREATE TABLE IF NOT EXISTS cost_logs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    novel_id        TEXT NOT NULL REFERENCES novels(id) ON DELETE CASCADE,
    chapter_number  INTEGER NOT NULL DEFAULT 0,
    model           TEXT NOT NULL DEFAULT '',
    prompt_tokens   INTEGER NOT NULL DEFAULT 0,
    completion_tokens INTEGER NOT NULL DEFAULT 0,
    total_tokens    INTEGER NOT NULL DEFAULT 0,
    cost            REAL NOT NULL DEFAULT 0,
    purpose         TEXT NOT NULL DEFAULT 'generate',
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_cost_logs_novel ON cost_logs(novel_id);

-- V10: Chapter summaries for smart context window
CREATE TABLE IF NOT EXISTS chapter_summaries (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    novel_id        TEXT NOT NULL REFERENCES novels(id) ON DELETE CASCADE,
    chapter_num     INTEGER NOT NULL,
    summary_text    TEXT NOT NULL DEFAULT '',
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(novel_id, chapter_num)
);
CREATE INDEX IF NOT EXISTS idx_chapter_summaries_novel ON chapter_summaries(novel_id);
