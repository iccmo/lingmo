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

CREATE TABLE IF NOT EXISTS chapter_versions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    chapter_id  INTEGER NOT NULL REFERENCES chapters(id) ON DELETE CASCADE,
    content     TEXT NOT NULL DEFAULT '',
    word_count  INTEGER NOT NULL DEFAULT 0,
    version     INTEGER NOT NULL DEFAULT 1,
    reason      TEXT DEFAULT '',
    created_at  TEXT DEFAULT (datetime('now'))
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

-- Film Studio settings (image provider, API keys, etc.)
CREATE TABLE IF NOT EXISTS film_settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL DEFAULT ''
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

-- V11: Story Bible — structured memory for novel consistency
CREATE TABLE IF NOT EXISTS character_state (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    novel_id        TEXT NOT NULL REFERENCES novels(id) ON DELETE CASCADE,
    chapter_num     INTEGER NOT NULL,
    char_name       TEXT NOT NULL,
    emotion         TEXT NOT NULL DEFAULT '',
    physical_state  TEXT NOT NULL DEFAULT '',
    knowledge       TEXT NOT NULL DEFAULT '[]',
    goal            TEXT NOT NULL DEFAULT '',
    location        TEXT NOT NULL DEFAULT '',
    relationships   TEXT NOT NULL DEFAULT '[]',
    notes           TEXT NOT NULL DEFAULT '',
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_char_state_novel ON character_state(novel_id, char_name, chapter_num);

CREATE TABLE IF NOT EXISTS foreshadowing_tracker (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    novel_id            TEXT NOT NULL REFERENCES novels(id) ON DELETE CASCADE,
    created_chapter     INTEGER NOT NULL,
    description         TEXT NOT NULL,
    hint_text           TEXT NOT NULL DEFAULT '',
    due_by_chapter      INTEGER,
    status              TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','resolved','overdue')),
    resolved_chapter    INTEGER,
    resolved_text       TEXT NOT NULL DEFAULT '',
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at          TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_foreshadowing_novel ON foreshadowing_tracker(novel_id, status);

CREATE TABLE IF NOT EXISTS location_history (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    novel_id        TEXT NOT NULL REFERENCES novels(id) ON DELETE CASCADE,
    chapter_num     INTEGER NOT NULL,
    location_name   TEXT NOT NULL,
    event           TEXT NOT NULL DEFAULT '',
    state_change    TEXT NOT NULL DEFAULT '',
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_location_novel ON location_history(novel_id, chapter_num);

CREATE TABLE IF NOT EXISTS story_timeline (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    novel_id        TEXT NOT NULL REFERENCES novels(id) ON DELETE CASCADE,
    chapter_num     INTEGER NOT NULL,
    absolute_time   TEXT NOT NULL DEFAULT '',
    relative_time   TEXT NOT NULL DEFAULT '',
    event_summary   TEXT NOT NULL DEFAULT '',
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_timeline_novel ON story_timeline(novel_id, chapter_num);

CREATE TABLE IF NOT EXISTS world_state (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    novel_id            TEXT NOT NULL REFERENCES novels(id) ON DELETE CASCADE,
    chapter_num         INTEGER NOT NULL,
    rule_name           TEXT NOT NULL,
    rule_description    TEXT NOT NULL DEFAULT '',
    is_broken           INTEGER NOT NULL DEFAULT 0,
    created_at          TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_world_novel ON world_state(novel_id, chapter_num);

CREATE TABLE IF NOT EXISTS consistency_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    novel_id        TEXT NOT NULL REFERENCES novels(id) ON DELETE CASCADE,
    chapter_num     INTEGER NOT NULL,
    check_type      TEXT NOT NULL DEFAULT 'character',
    severity        TEXT NOT NULL DEFAULT 'warning' CHECK(severity IN ('error','warning','info')),
    description     TEXT NOT NULL DEFAULT '',
    fix_suggestion  TEXT NOT NULL DEFAULT '',
    was_fixed       INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_consistency_novel ON consistency_log(novel_id, chapter_num);

-- V12: Unsaid Book — hidden truths the author knows but the text never states
CREATE TABLE IF NOT EXISTS unsaid_book (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    novel_id    TEXT NOT NULL REFERENCES novels(id) ON DELETE CASCADE,
    entry       TEXT NOT NULL,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_unsaid_novel ON unsaid_book(novel_id);

-- V13: Voice Profile — track author edits to learn preferences
CREATE TABLE IF NOT EXISTS voice_profile (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    novel_id    TEXT NOT NULL REFERENCES novels(id) ON DELETE CASCADE,
    chapter_num INTEGER NOT NULL,
    before_text TEXT NOT NULL DEFAULT '',
    after_text  TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_voice_novel ON voice_profile(novel_id);

-- V14: Cost ledger — tracks gains vs losses per chapter (§50)
CREATE TABLE IF NOT EXISTS cost_ledger (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    novel_id        TEXT NOT NULL REFERENCES novels(id) ON DELETE CASCADE,
    chapter_num     INTEGER NOT NULL,
    character_name  TEXT NOT NULL DEFAULT '',
    gain            TEXT NOT NULL DEFAULT '',
    loss            TEXT NOT NULL DEFAULT '',
    gain_type       TEXT NOT NULL DEFAULT 'info',
    loss_type       TEXT NOT NULL DEFAULT 'none',
    is_immediate    INTEGER NOT NULL DEFAULT 1,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_cost_novel ON cost_ledger(novel_id, chapter_num);

-- ═══ AI Film Studio: 视觉圣经 ═══

CREATE TABLE IF NOT EXISTS visual_characters (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    novel_id        TEXT NOT NULL REFERENCES novels(id) ON DELETE CASCADE,
    char_key        TEXT NOT NULL,
    appearance      TEXT DEFAULT '',
    default_expression TEXT DEFAULT '',
    signature_pose  TEXT DEFAULT '',
    color_palette   TEXT DEFAULT '',
    costume         TEXT DEFAULT '',
    injury_marks    TEXT DEFAULT '',
    voice_character TEXT DEFAULT '',
    reference_images TEXT DEFAULT '[]',
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(novel_id, char_key)
);

-- ═══ AI Film Studio: 分镜脚本 ═══

CREATE TABLE IF NOT EXISTS storyboards (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    novel_id        TEXT NOT NULL REFERENCES novels(id) ON DELETE CASCADE,
    chapter_num     INTEGER NOT NULL,
    title           TEXT NOT NULL DEFAULT '',
    total_duration_sec REAL DEFAULT 0,
    overall_mood    TEXT DEFAULT '',
    pacing          TEXT DEFAULT '',
    color_grade     TEXT DEFAULT '',
    music_theme     TEXT DEFAULT '',
    shots_json      TEXT NOT NULL DEFAULT '[]',
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(novel_id, chapter_num)
);

-- ═══ AI Film Studio: 角色音色 ═══

CREATE TABLE IF NOT EXISTS character_voices (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    novel_id        TEXT NOT NULL REFERENCES novels(id) ON DELETE CASCADE,
    char_key        TEXT NOT NULL,
    voice_id        TEXT NOT NULL DEFAULT '',
    speed           REAL NOT NULL DEFAULT 1.0,
    pitch           TEXT NOT NULL DEFAULT '+0Hz',
    emotion_default TEXT NOT NULL DEFAULT 'calm',
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(novel_id, char_key)
);
