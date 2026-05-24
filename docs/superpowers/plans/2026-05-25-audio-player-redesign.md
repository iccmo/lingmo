# Audio Player Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the hidden AudioPlayer with a dedicated ListenPage (/listen), global MiniPlayer, and backend-synced listening progress.

**Architecture:** Backend adds an `audio_progress` table and an aggregation endpoint `/api/audio/library`. Frontend wraps play state in `AudioContext`, renders a full-page library browser at `/listen`, and a persistent bottom MiniPlayer across all routes.

**Tech Stack:** FastAPI + SQLite (backend), React + TypeScript + Tailwind CSS (frontend)

---

## File Structure

```
novel_writer/
├── schema.sql              [MODIFY] Add audio_progress table
├── database.py             [MODIFY] Add audio progress CRUD methods
└── server.py               [MODIFY] Add 3 endpoints

frontend/src/
├── types/index.ts           [MODIFY] Add AudioProgress, AudioLibrary types
├── lib/api.ts               [MODIFY] Add audio API methods
├── lib/AudioContext.tsx      [CREATE] Global audio state + playback controls
├── components/novels/
│   ├── AudioPlayer.tsx       [MODIFY] Strip float logic, keep control panel only
│   └── MiniPlayer.tsx        [CREATE] Fixed bottom bar with now-playing
├── pages/ListenPage.tsx      [CREATE] Library browser + full player
├── components/layout/
│   └── Sidebar.tsx           [MODIFY] Add 🎧 听书 nav link
└── App.tsx                   [MODIFY] AudioProvider, MiniPlayer, /listen route
```

---

### Task 1: Backend — audio_progress table + schema migration

**Files:**
- Modify: `novel_writer/schema.sql` (append new table)

- [ ] **Step 1: Add audio_progress table to schema.sql**

Append to end of `novel_writer/schema.sql`:

```sql
-- V7: Audio listening progress
CREATE TABLE IF NOT EXISTS audio_progress (
    novel_id     TEXT PRIMARY KEY REFERENCES novels(id) ON DELETE CASCADE,
    chapter_num  INTEGER NOT NULL,
    position_sec REAL NOT NULL DEFAULT 0,
    updated_at   TEXT NOT NULL DEFAULT (datetime('now'))
);
```

- [ ] **Step 2: Verify schema**

```bash
sqlite3 /Users/z/CodeBuddy/wechat/data/novel_writer.db ".schema audio_progress"
```

Expected: table doesn't exist yet (will be created on next server restart)

- [ ] **Step 3: Commit**

```bash
git add novel_writer/schema.sql
git commit -m "feat: add audio_progress table for listening history"
```

---

### Task 2: Backend — database.py audio methods

**Files:**
- Modify: `novel_writer/database.py` (add methods after existing CRUD)

- [ ] **Step 1: Add save_audio_progress method**

Insert after the last method in `Database` class (before the class ends):

```python
def save_audio_progress(self, novel_id: str, chapter_num: int, position_sec: float):
    with self.conn() as c:
        c.execute("""INSERT INTO audio_progress (novel_id, chapter_num, position_sec, updated_at)
            VALUES (?, ?, ?, datetime('now'))
            ON CONFLICT(novel_id) DO UPDATE SET
                chapter_num=excluded.chapter_num,
                position_sec=excluded.position_sec,
                updated_at=excluded.updated_at""",
            (novel_id, chapter_num, position_sec))
```

- [ ] **Step 2: Add get_audio_progress method**

```python
def get_audio_progress(self, novel_id: str) -> dict | None:
    with self.conn() as c:
        row = c.execute(
            "SELECT novel_id, chapter_num, position_sec, updated_at FROM audio_progress WHERE novel_id=?",
            (novel_id,)
        ).fetchone()
        return dict(row) if row else None
```

- [ ] **Step 3: Add get_latest_chapter method (helper for /api/audio/library)**

```python
def get_latest_chapters(self, novel_id: str, limit: int = 5) -> list[dict]:
    with self.conn() as c:
        rows = c.execute(
            "SELECT number, title, word_count, generated_at FROM chapters WHERE novel_id=? ORDER BY number DESC LIMIT ?",
            (novel_id, limit)
        ).fetchall()
        return [dict(r) for r in reversed(rows)]
```

- [ ] **Step 4: Add get_audio_library method**

```python
def get_audio_library(self) -> dict:
    """Aggregate all novels with recent chapters and listening progress."""
    with self.conn() as c:
        novels = self.list_novels()
        result = {"continue_listening": None, "novels": []}

        # Latest progress
        latest_progress = c.execute(
            "SELECT novel_id, chapter_num, position_sec, updated_at FROM audio_progress ORDER BY updated_at DESC LIMIT 1"
        ).fetchone()

        if latest_progress:
            p = dict(latest_progress)
            ch = c.execute(
                "SELECT title FROM chapters WHERE novel_id=? AND number=?",
                (p["novel_id"], p["chapter_num"])
            ).fetchone()
            n = c.execute("SELECT title FROM novels WHERE id=?", (p["novel_id"],)).fetchone()
            if ch and n:
                result["continue_listening"] = {
                    "novel_id": p["novel_id"],
                    "novel_title": n["title"],
                    "chapter_num": p["chapter_num"],
                    "chapter_title": ch["title"],
                    "position_sec": p["position_sec"],
                    "updated_at": p["updated_at"],
                }

        for n in novels:
            chapters = self.get_latest_chapters(n["id"], 5)
            progress = None
            ap = c.execute(
                "SELECT chapter_num, position_sec FROM audio_progress WHERE novel_id=?",
                (n["id"],)
            ).fetchone()
            if ap:
                total = n.get("total_chapters", 0)
                progress = {
                    "chapter_num": ap["chapter_num"],
                    "position_sec": ap["position_sec"],
                    "pct": round(ap["chapter_num"] / total, 2) if total > 0 else 0,
                }

            result["novels"].append({
                "id": n["id"],
                "title": n["title"],
                "author": n.get("author", "AI"),
                "genre": n.get("genre", ""),
                "total_chapters": n.get("total_chapters", 0),
                "total_words": n.get("total_words", 0),
                "recent_chapters": chapters,
                "progress": progress,
            })

        return result
```

- [ ] **Step 5: Commit**

```bash
git add novel_writer/database.py
git commit -m "feat: add audio progress and library aggregation methods to Database"
```

---

### Task 3: Backend — API endpoints

**Files:**
- Modify: `novel_writer/server.py` (add 3 endpoints near the TTS endpoint)

- [ ] **Step 1: Add GET /api/audio/library endpoint**

Insert after the TTS endpoint (~line 2432):

```python
@app.get("/api/audio/library")
def audio_library():
    """Aggregated audio library: all novels + recent chapters + listening progress."""
    try:
        return db.get_audio_library()
    except Exception as e:
        raise HTTPException(500, str(e))
```

- [ ] **Step 2: Add POST /api/audio/progress endpoint**

```python
@app.post("/api/audio/progress")
def save_audio_progress(data: dict):
    """Save listening position. Body: {novel_id, chapter_num, position_sec}."""
    novel_id = data.get("novel_id")
    chapter_num = data.get("chapter_num")
    position_sec = data.get("position_sec", 0)
    if not novel_id or chapter_num is None:
        raise HTTPException(400, "novel_id and chapter_num required")
    try:
        db.save_audio_progress(novel_id, int(chapter_num), float(position_sec))
        return {"ok": True}
    except Exception as e:
        raise HTTPException(500, str(e))
```

- [ ] **Step 3: Add GET /api/audio/progress/{novel_id} endpoint**

```python
@app.get("/api/audio/progress/{novel_id}")
def get_audio_progress(novel_id: str):
    """Get listening progress for a specific novel."""
    progress = db.get_audio_progress(novel_id)
    if not progress:
        return {"novel_id": novel_id, "chapter_num": 0, "position_sec": 0}
    return progress
```

- [ ] **Step 4: Commit**

```bash
git add novel_writer/server.py
git commit -m "feat: add /api/audio/library and /api/audio/progress endpoints"
```

---

### Task 4: Frontend — types and API client

**Files:**
- Modify: `frontend/src/types/index.ts`
- Modify: `frontend/src/lib/api.ts`

- [ ] **Step 1: Add AudioProgress and AudioLibrary types to types/index.ts**

Append to `frontend/src/types/index.ts`:

```typescript
export interface AudioProgress {
  novel_id: string;
  chapter_num: number;
  position_sec: number;
  updated_at?: string;
}

export interface ContinueListening {
  novel_id: string;
  novel_title: string;
  chapter_num: number;
  chapter_title: string;
  position_sec: number;
  updated_at: string;
}

export interface AudioNovelEntry {
  id: string;
  title: string;
  author: string;
  genre: string;
  total_chapters: number;
  total_words: number;
  recent_chapters: ChapterMeta[];
  progress: { chapter_num: number; position_sec: number; pct: number } | null;
}

export interface AudioLibrary {
  continue_listening: ContinueListening | null;
  novels: AudioNovelEntry[];
}
```

- [ ] **Step 2: Add audio API methods to api.ts**

Append inside `api` object (after `status`), in `frontend/src/lib/api.ts`:

```typescript
audio: {
  library:   () => get<AudioLibrary>('/audio/library'),
  progress:  (novelId: string) => get<AudioProgress>(`/audio/progress/${novelId}`),
  saveProgress: (novelId: string, chapterNum: number, positionSec: number) =>
    post('/audio/progress', { novel_id: novelId, chapter_num: chapterNum, position_sec: positionSec }),
},
```

Add the import at top, modifying line 1:

```typescript
import type { NovelSummary, NovelDetail, DraftOption, SystemStatus, PublishResult, AudioLibrary, AudioProgress } from 'src/types';
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/types/index.ts frontend/src/lib/api.ts
git commit -m "feat: add audio types and API client methods"
```

---

### Task 5: Frontend — AudioContext (global state)

**Files:**
- Create: `frontend/src/lib/AudioContext.tsx`

- [ ] **Step 1: Create AudioContext with full state management**

Write `frontend/src/lib/AudioContext.tsx`:

```typescript
import { createContext, useContext, useState, useRef, useCallback, useEffect, type ReactNode } from 'react';
import { toast } from 'sonner';
import { api } from 'src/lib/api';

const VOICES = [
  { id: 'zh-CN-XiaoxiaoNeural', name: '晓晓', gender: '女', style: '温柔' },
  { id: 'zh-CN-YunxiNeural', name: '云希', gender: '男', style: '沉稳' },
  { id: 'zh-CN-XiaoyiNeural', name: '晓伊', gender: '女', style: '活泼' },
  { id: 'zh-CN-YunyangNeural', name: '云扬', gender: '男', style: '新闻' },
  { id: 'zh-CN-XiaochenNeural', name: '晓辰', gender: '女', style: '自然' },
  { id: 'zh-CN-YunjianNeural', name: '云健', gender: '男', style: '运动' },
];

export interface PlaylistItem {
  novelId: string;
  novelTitle: string;
  chapterNum: number;
  chapterTitle: string;
}

interface AudioState {
  playing: boolean;
  paused: boolean;
  current: PlaylistItem | null;
  progress: number; // 0-100
  positionSec: number;
  speed: number;
  voice: string;
  playlist: PlaylistItem[];
  sleepTimer: number; // minutes, 0 = off
}

interface AudioActions {
  playChapter: (item: PlaylistItem, seekTo?: number) => void;
  togglePause: () => void;
  stop: () => void;
  skipChapter: (dir: 1 | -1) => void;
  playRandom: () => void;
  addToPlaylist: (item: PlaylistItem) => void;
  removeFromPlaylist: (idx: number) => void;
  changeVoice: (v: string) => void;
  changeSpeed: (s: number) => void;
  startSleepTimer: (mins: number) => void;
  cancelSleepTimer: () => void;
}

const AudioCtx = createContext<(AudioState & AudioActions) | null>(null);

function loadPlaylist(): PlaylistItem[] {
  try { return JSON.parse(localStorage.getItem('audio-playlist') || '[]'); } catch { return []; }
}
function savePlaylist(items: PlaylistItem[]) {
  localStorage.setItem('audio-playlist', JSON.stringify(items));
}

export function AudioProvider({ children }: { children: ReactNode }) {
  const [playing, setPlaying] = useState(false);
  const [paused, setPaused] = useState(false);
  const [current, setCurrent] = useState<PlaylistItem | null>(null);
  const [progress, setProgress] = useState(0);
  const [positionSec, setPositionSec] = useState(0);
  const [speed, setSpeed] = useState(1.0);
  const [voice, setVoice] = useState(() => localStorage.getItem('tts-voice') || 'zh-CN-XiaoxiaoNeural');
  const [playlist, setPlaylistState] = useState<PlaylistItem[]>(loadPlaylist);
  const [sleepTimer, setSleepTimer] = useState(0);

  const audioRef = useRef<HTMLAudioElement | null>(null);
  const sleepTimerRef = useRef<ReturnType<typeof setTimeout>>();
  const progressSyncRef = useRef<ReturnType<typeof setInterval>>();

  // Sync progress to backend every 10s
  useEffect(() => {
    if (playing && !paused && current) {
      progressSyncRef.current = setInterval(() => {
        if (audioRef.current && current) {
          api.audio.saveProgress(current.novelId, current.chapterNum, audioRef.current.currentTime).catch(() => {});
        }
      }, 10000);
    }
    return () => { if (progressSyncRef.current) clearInterval(progressSyncRef.current); };
  }, [playing, paused, current]);

  const playChapter = useCallback((item: PlaylistItem, seekTo = 0) => {
    if (audioRef.current) { audioRef.current.pause(); audioRef.current = null; }

    const rateParam = speed === 1.0 ? '+0%' : speed > 1 ? `+${Math.round((speed - 1) * 100)}%` : `${Math.round((speed - 1) * 100)}%`;
    const src = `/api/novels/${item.novelId}/chapters/${item.chapterNum}/tts?voice=${voice}&rate=${rateParam}`;
    const audio = new Audio(src);
    audioRef.current = audio;

    audio.onloadedmetadata = () => {
      audio.currentTime = seekTo;
      setCurrent(item);
      setPlaying(true);
      setPaused(false);
      api.audio.saveProgress(item.novelId, item.chapterNum, seekTo).catch(() => {});
    };

    audio.ontimeupdate = () => {
      if (audio.duration) {
        setProgress(Math.round((audio.currentTime / audio.duration) * 100));
        setPositionSec(audio.currentTime);
      }
    };

    audio.onended = () => {
      setProgress(100);
      api.audio.saveProgress(item.novelId, item.chapterNum, audio.duration || 0).catch(() => {});
      const idx = playlist.findIndex(p => p.novelId === item.novelId && p.chapterNum === item.chapterNum);
      const next = playlist[idx + 1];
      if (next) {
        toast.info(`${next.novelTitle} · 第${next.chapterNum}章`, { duration: 2000 });
        setTimeout(() => playChapter(next), 500);
      } else {
        setPlaying(false);
        toast.success('播放列表结束');
      }
    };

    audio.onerror = () => { toast.error('播放失败'); setPlaying(false); };
    audio.play().catch(() => toast.error('播放失败'));
  }, [speed, voice, playlist]);

  const togglePause = useCallback(() => {
    if (!audioRef.current) return;
    if (paused) { audioRef.current.play(); setPaused(false); }
    else {
      audioRef.current.pause();
      setPaused(true);
      if (current) api.audio.saveProgress(current.novelId, current.chapterNum, audioRef.current.currentTime).catch(() => {});
    }
  }, [paused, current]);

  const stop = useCallback(() => {
    if (audioRef.current) { audioRef.current.pause(); audioRef.current = null; }
    setPlaying(false);
    setPaused(false);
    setProgress(0);
    setPositionSec(0);
    cancelSleepTimer();
  }, []);

  const skipChapter = useCallback((dir: 1 | -1) => {
    if (!current) return;
    const idx = playlist.findIndex(p => p.novelId === current.novelId && p.chapterNum === current.chapterNum);
    const target = playlist[idx + dir];
    if (target) playChapter(target);
  }, [current, playlist, playChapter]);

  const playRandom = useCallback(() => {
    if (playlist.length === 0) return;
    const random = playlist[Math.floor(Math.random() * playlist.length)];
    playChapter(random);
  }, [playlist, playChapter]);

  const addToPlaylist = useCallback((item: PlaylistItem) => {
    setPlaylistState(prev => {
      if (prev.find(p => p.novelId === item.novelId && p.chapterNum === item.chapterNum)) return prev;
      const next = [...prev, item];
      savePlaylist(next);
      return next;
    });
    toast.success('已加入播放列表');
  }, []);

  const removeFromPlaylist = useCallback((idx: number) => {
    setPlaylistState(prev => {
      const next = prev.filter((_, i) => i !== idx);
      savePlaylist(next);
      return next;
    });
  }, []);

  const changeVoice = useCallback((v: string) => {
    setVoice(v);
    localStorage.setItem('tts-voice', v);
    if (current && audioRef.current) {
      const pos = audioRef.current.currentTime;
      playChapter(current, pos);
    }
  }, [current, playChapter]);

  const changeSpeed = useCallback((s: number) => {
    setSpeed(s);
    if (current && audioRef.current) {
      const pos = audioRef.current.currentTime;
      playChapter(current, pos);
    }
  }, [current, playChapter]);

  function startSleepTimer(mins: number) {
    if (sleepTimerRef.current) clearTimeout(sleepTimerRef.current);
    setSleepTimer(mins);
    sleepTimerRef.current = setTimeout(() => {
      toast.info('⏰ 定时结束，已暂停');
      if (audioRef.current) audioRef.current.pause();
      setPaused(true);
      setSleepTimer(0);
    }, mins * 60000);
  }

  function cancelSleepTimer() {
    if (sleepTimerRef.current) clearTimeout(sleepTimerRef.current);
    setSleepTimer(0);
  }

  return (
    <AudioCtx.Provider value={{
      playing, paused, current, progress, positionSec, speed, voice, playlist, sleepTimer,
      playChapter, togglePause, stop, skipChapter, playRandom, addToPlaylist, removeFromPlaylist,
      changeVoice, changeSpeed, startSleepTimer, cancelSleepTimer,
    }}>
      {children}
    </AudioCtx.Provider>
  );
}

export function useAudio() {
  const ctx = useContext(AudioCtx);
  if (!ctx) throw new Error('useAudio must be used within AudioProvider');
  return ctx;
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/lib/AudioContext.tsx
git commit -m "feat: add AudioContext for global audio playback state"
```

---

### Task 6: Frontend — MiniPlayer (global bottom bar)

**Files:**
- Create: `frontend/src/components/novels/MiniPlayer.tsx`

- [ ] **Step 1: Create MiniPlayer component**

Write `frontend/src/components/novels/MiniPlayer.tsx`:

```typescript
import { useAudio } from 'src/lib/AudioContext';
import { useNavigate } from 'react-router-dom';

export function MiniPlayer() {
  const { playing, paused, current, progress, togglePause, skipChapter } = useAudio();
  const navigate = useNavigate();

  if (!current || !playing) return null;

  return (
    <div className="fixed bottom-8 left-1/2 -translate-x-1/2 z-50 bg-card border border-border rounded-full shadow-xl px-4 py-2 flex items-center gap-3 text-xs animate-[fadeSlideIn_0.2s_ease-out]"
      style={{ userSelect: 'none' }}>
      <button onClick={() => navigate('/listen')} className="text-ink-muted hover:text-accent shrink-0">
        🎧
      </button>
      <div className="flex flex-col min-w-0 cursor-pointer" onClick={() => navigate('/listen')}>
        <span className="text-ink font-medium truncate max-w-[180px]">{current.novelTitle} · Ch{current.chapterNum}</span>
        <div className="h-0.5 bg-border rounded-full mt-0.5 w-full">
          <div className="h-full bg-accent rounded-full transition-all" style={{ width: `${progress}%` }} />
        </div>
      </div>
      <button onClick={(e) => { e.stopPropagation(); skipChapter(-1); }}
        className="text-ink-muted hover:text-ink shrink-0">⏮</button>
      <button onClick={(e) => { e.stopPropagation(); togglePause(); }}
        className="text-accent shrink-0">{paused ? '▶' : '⏸'}</button>
      <button onClick={(e) => { e.stopPropagation(); skipChapter(1); }}
        className="text-ink-muted hover:text-ink shrink-0">⏭</button>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/novels/MiniPlayer.tsx
git commit -m "feat: add MiniPlayer global bottom bar"
```

---

### Task 7: Frontend — ListenPage (library browser + player)

**Files:**
- Create: `frontend/src/pages/ListenPage.tsx`

- [ ] **Step 1: Create ListenPage with library and player**

Write `frontend/src/pages/ListenPage.tsx`:

```typescript
import { useState, useEffect } from 'react';
import { useAudio, type PlaylistItem } from 'src/lib/AudioContext';
import { api } from 'src/lib/api';
import type { AudioLibrary, AudioNovelEntry, ContinueListening } from 'src/types';

const VOICES = [
  { id: 'zh-CN-XiaoxiaoNeural', name: '晓晓', gender: '女', style: '温柔' },
  { id: 'zh-CN-YunxiNeural', name: '云希', gender: '男', style: '沉稳' },
  { id: 'zh-CN-XiaoyiNeural', name: '晓伊', gender: '女', style: '活泼' },
  { id: 'zh-CN-YunyangNeural', name: '云扬', gender: '男', style: '新闻' },
  { id: 'zh-CN-XiaochenNeural', name: '晓辰', gender: '女', style: '自然' },
  { id: 'zh-CN-YunjianNeural', name: '云健', gender: '男', style: '运动' },
];

function formatTime(sec: number): string {
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  return `${m}:${s.toString().padStart(2, '0')}`;
}

export function ListenPage() {
  const [library, setLibrary] = useState<AudioLibrary | null>(null);
  const [expandedNovel, setExpandedNovel] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const {
    playing, paused, current, progress, positionSec, speed, voice, playlist, sleepTimer,
    playChapter, togglePause, stop, skipChapter, playRandom,
    addToPlaylist, removeFromPlaylist, changeVoice, changeSpeed, startSleepTimer, cancelSleepTimer,
  } = useAudio();

  useEffect(() => {
    api.audio.library()
      .then(setLibrary)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  function handlePlayChapter(novelId: string, novelTitle: string, num: number, title: string) {
    const item: PlaylistItem = { novelId, novelTitle, chapterNum: num, chapterTitle: title };
    addToPlaylist(item);
    playChapter(item);
  }

  function handlePlayNovel(novel: AudioNovelEntry) {
    const chapters = novel.recent_chapters;
    if (chapters.length === 0) return;
    for (const ch of chapters.slice(0, 10)) {
      const item: PlaylistItem = { novelId: novel.id, novelTitle: novel.title, chapterNum: ch.number, chapterTitle: ch.title };
      addToPlaylist(item);
    }
    const first = chapters[0];
    playChapter({ novelId: novel.id, novelTitle: novel.title, chapterNum: first.number, chapterTitle: first.title });
  }

  if (loading) {
    return (
      <div className="space-y-6 animate-pulse">
        <div className="h-32 bg-card rounded-xl" />
        <div className="h-12 bg-card rounded-lg" />
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
          {[1, 2, 3, 4, 5, 6].map(i => <div key={i} className="h-24 bg-card rounded-lg" />)}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 pb-24">
      {/* Page header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-ink">🎧 听书</h2>
          <p className="text-xs text-ink-muted mt-0.5">AI 语音朗读 · Edge TTS 自然语音</p>
        </div>
        <button onClick={playRandom} disabled={playlist.length === 0}
          className="text-xs px-3 py-1.5 rounded-lg border border-border hover:border-accent/30 text-ink-muted hover:text-accent transition-colors disabled:opacity-30">
          🔀 随机播放
        </button>
      </div>

      {/* Continue Listening */}
      {library?.continue_listening && (
        <div className="p-4 rounded-xl bg-gradient-to-r from-accent-soft/30 to-card border border-accent/20">
          <p className="text-[10px] text-ink-subtle mb-1 uppercase tracking-wider">继续收听</p>
          <div className="flex items-center justify-between">
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-ink truncate">{library.continue_listening.novel_title}</p>
              <p className="text-xs text-ink-muted">
                第{library.continue_listening.chapter_num}章 · {library.continue_listening.chapter_title}
                <span className="ml-2 text-ink-subtle">{formatTime(library.continue_listening.position_sec)}</span>
              </p>
            </div>
            <button
              onClick={() => {
                const cl = library.continue_listening!;
                const item: PlaylistItem = { novelId: cl.novel_id, novelTitle: cl.novel_title, chapterNum: cl.chapter_num, chapterTitle: cl.chapter_title };
                playChapter(item, cl.position_sec);
              }}
              className="shrink-0 px-4 py-2 bg-accent text-white text-xs font-medium rounded-full hover:opacity-90 transition-opacity"
            >
              继续 ▶
            </button>
          </div>
        </div>
      )}

      {/* Now Playing */}
      {current && playing && (
        <div className="p-4 rounded-xl bg-accent-soft/20 border border-accent/10">
          <div className="flex items-center justify-between">
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-ink truncate">{current.novelTitle}</p>
              <p className="text-xs text-ink-muted">第{current.chapterNum}章 {current.chapterTitle}</p>
            </div>
            <span className="text-xs text-ink-subtle tabular-nums shrink-0 ml-3">{formatTime(positionSec)} · {progress}%</span>
          </div>
          <div className="h-1.5 bg-border rounded-full mt-2 overflow-hidden">
            <div className="h-full bg-accent rounded-full transition-all duration-300" style={{ width: `${progress}%` }} />
          </div>

          {/* Controls */}
          <div className="flex items-center justify-center gap-3 mt-3">
            <button onClick={() => skipChapter(-1)} className="text-sm p-1 text-ink-muted hover:text-ink disabled:opacity-20" disabled={!current}>⏮</button>
            <button onClick={togglePause} className="text-2xl p-1 text-accent hover:scale-110 transition-transform">{paused ? '▶' : '⏸'}</button>
            <button onClick={stop} className="text-sm p-1 text-red-400 hover:text-red-600 disabled:opacity-20" disabled={!playing}>⏹</button>
            <button onClick={() => skipChapter(1)} className="text-sm p-1 text-ink-muted hover:text-ink disabled:opacity-20" disabled={!current}>⏭</button>
          </div>

          {/* Voice + Speed */}
          <div className="flex items-center gap-2 mt-2">
            <select value={voice} onChange={e => changeVoice(e.target.value)}
              className="flex-1 text-[10px] rounded border border-input bg-card px-2 py-1">
              {VOICES.map(v => <option key={v.id} value={v.id}>{v.name} · {v.gender} {v.style}</option>)}
            </select>
            <div className="flex gap-0.5">
              {[0.8, 1.0, 1.2, 1.5].map(s => (
                <button key={s} onClick={() => changeSpeed(s)}
                  className={`text-[9px] px-1.5 py-0.5 rounded ${speed === s ? 'bg-accent text-white' : 'text-ink-muted hover:text-ink'}`}>
                  {s}x
                </button>
              ))}
            </div>
          </div>

          {/* Sleep timer */}
          <div className="flex items-center gap-1 justify-center mt-2">
            <span className="text-[9px] text-ink-muted">⏰</span>
            {[15, 30, 45, 60].map(m => (
              <button key={m} onClick={() => sleepTimer === m ? cancelSleepTimer() : startSleepTimer(m)}
                className={`text-[9px] px-1.5 py-0.5 rounded ${sleepTimer === m ? 'bg-accent text-white' : 'text-ink-muted hover:text-ink'}`}>
                {m}min
              </button>
            ))}
            {sleepTimer > 0 && <span className="text-[9px] text-amber-500">{sleepTimer}分钟后暂停</span>}
          </div>
        </div>
      )}

      {/* Novel grid */}
      {library?.novels && library.novels.length > 0 && (
        <div>
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold text-ink">我的书架</h3>
            <span className="text-[10px] text-ink-subtle">{library.novels.length} 部作品</span>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {library.novels.map(novel => (
              <div key={novel.id}
                className={`rounded-xl border transition-colors ${
                  expandedNovel === novel.id ? 'border-accent/30 bg-accent-soft/5' : 'border-border bg-card hover:border-accent/20'
                }`}>
                {/* Novel card */}
                <div className="p-3 cursor-pointer" onClick={() => setExpandedNovel(expandedNovel === novel.id ? null : novel.id)}>
                  <div className="flex items-start justify-between">
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-ink truncate">{novel.title}</p>
                      <p className="text-[10px] text-ink-muted">{novel.genre} · {novel.total_chapters}章 · {novel.total_words.toLocaleString()}字</p>
                    </div>
                    <span className="text-[10px] text-ink-subtle">{expandedNovel === novel.id ? '▴' : '▾'}</span>
                  </div>
                  {novel.progress && (
                    <div className="h-1 bg-border rounded-full mt-2 overflow-hidden">
                      <div className="h-full bg-accent/60 rounded-full" style={{ width: `${novel.progress.pct * 100}%` }} />
                    </div>
                  )}
                </div>

                {/* Expanded chapter list */}
                {expandedNovel === novel.id && (
                  <div className="border-t border-border px-3 py-2 space-y-1">
                    <button
                      onClick={(e) => { e.stopPropagation(); handlePlayNovel(novel); }}
                      className="w-full text-[10px] text-accent hover:text-accent/80 font-medium py-1"
                    >
                      ▶ 播放最近章节
                    </button>
                    {novel.recent_chapters.length === 0 && (
                      <p className="text-[10px] text-ink-subtle text-center py-2">暂无章节</p>
                    )}
                    {novel.recent_chapters.map(ch => {
                      const isCurrent = current?.novelId === novel.id && current?.chapterNum === ch.number;
                      return (
                        <div key={ch.number}
                          onClick={(e) => { e.stopPropagation(); handlePlayChapter(novel.id, novel.title, ch.number, ch.title); }}
                          className={`flex items-center gap-2 px-2 py-1 rounded text-[10px] cursor-pointer transition-colors ${
                            isCurrent ? 'bg-accent-soft/30 text-accent' : 'hover:bg-paper text-ink'
                          }`}
                        >
                          <span className="text-ink-subtle shrink-0">{isCurrent && playing ? '🔊' : '🎵'}</span>
                          <span className="flex-1 truncate">第{ch.number}章 {ch.title}</span>
                          <span className="text-ink-subtle shrink-0">{ch.word_count.toLocaleString()}字</span>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Playlist sidebar */}
      {playlist.length > 0 && (
        <div className="border-t border-border pt-4">
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-sm font-semibold text-ink">播放列表 ({playlist.length})</h3>
            <button onClick={() => {
              localStorage.removeItem('audio-playlist');
              window.location.reload();
            }} className="text-[10px] text-red-400 hover:text-red-600">清空</button>
          </div>
          <div className="space-y-0.5 max-h-[300px] overflow-y-auto">
            {playlist.map((item, i) => {
              const isCurrent = current?.novelId === item.novelId && current?.chapterNum === item.chapterNum;
              return (
                <div key={`${item.novelId}-${item.chapterNum}`}
                  onClick={() => playChapter(item)}
                  className={`flex items-center gap-2 px-3 py-2 rounded text-xs cursor-pointer transition-colors ${
                    isCurrent ? 'bg-accent-soft/30 text-accent' : 'hover:bg-paper text-ink'
                  }`}
                >
                  <span className="text-ink-subtle shrink-0">{isCurrent && playing ? '🔊' : '🎵'}</span>
                  <span className="flex-1 truncate">{item.novelTitle} · 第{item.chapterNum}章</span>
                  <button onClick={e => { e.stopPropagation(); removeFromPlaylist(i); }}
                    className="text-ink-subtle hover:text-red-500 shrink-0">×</button>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/pages/ListenPage.tsx
git commit -m "feat: add ListenPage with library browser and player controls"
```

---

### Task 8: Frontend — App.tsx integration (AudioProvider + MiniPlayer + /listen route)

**Files:**
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Add imports**

Update imports at top of `frontend/src/App.tsx`:

```typescript
import { AudioProvider } from 'src/lib/AudioContext';
import { MiniPlayer } from 'src/components/novels/MiniPlayer';
import { ListenPage } from 'src/pages/ListenPage';
```

- [ ] **Step 2: Add /listen route**

Inside `<Routes>`, after `<Route path="/" .../>`:

```typescript
<Route path="/listen" element={<ListenPage />} />
```

- [ ] **Step 3: Wrap AppLayout with AudioProvider and add MiniPlayer**

Inside `AppLayout`, wrap the entire return in `<AudioProvider>` and add `<MiniPlayer />` before the closing `</div>`:

```typescript
return (
  <AudioProvider>
    <div className="h-screen flex flex-col font-[family-name:var(--font-ui)] bg-paper">
      {/* ... existing content ... */}
      <MiniPlayer />
    </div>
  </AudioProvider>
);
```

Important: the `</div>` before `MiniPlayer` — `MiniPlayer` goes inside the main flex container but after `<Footer />` and before `<CommandPalette />`.

The modified section (lines 71-107) becomes:

```typescript
  return (
    <AudioProvider>
    <div className="h-screen flex flex-col font-[family-name:var(--font-ui)] bg-paper">
      <TopLoader />
      <Header mode={mode} onModeChange={setMode} dark={dark} onDarkToggle={toggleDark}
        sidebarOpen={sidebarOpen} onSidebarToggle={toggleSidebar} />
      {sidebarOpen && (
        <div className="fixed inset-0 z-40 bg-black/20 lg:hidden" onClick={toggleSidebar} />
      )}
      <div className="flex flex-1 overflow-hidden">
        <div className={`shrink-0 overflow-hidden transition-all duration-300 ease-in-out
          lg:relative ${sidebarOpen ? 'fixed inset-y-0 left-0 z-50 lg:static' : ''}
          ${sidebarOpen ? 'w-[200px] min-w-[200px]' : 'w-0 min-w-0'}`}>
          <Sidebar onNovelSelect={() => { if (window.innerWidth < 1024) toggleSidebar(); }} />
        </div>
        <main className="flex-1 overflow-y-auto px-6 py-6 sm:px-8 lg:px-12 lg:py-10" id="main-content">
          <ErrorBoundary>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/listen" element={<ListenPage />} />
            <Route path="/novels/:id" element={<NovelDetail mode={mode} />} />
            <Route path="/settings" element={<Settings />} />
            <Route path="/logs" element={<Logs />} />
            <Route path="/stats" element={<Stats />} />
            <Route path="/novels/:id/memory" element={<MemoryBank />} />
            <Route path="/novels/:id/edit" element={<Editor />} />
            <Route path="/novels/:id/world" element={<WorldEditor />} />
            <Route path="/novels/:id/outline" element={<Outline />} />
            <Route path="/novels/:id/foreshadowing" element={<Foreshadowing />} />
          </Routes>
          </ErrorBoundary>
        </main>
      </div>
      <Footer />
      <MiniPlayer />
      <CommandPalette />
      <ShortcutsSheet />
      <QuickActions />
      <Toaster duration={3000} />
    </div>
    </AudioProvider>
  );
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/App.tsx
git commit -m "feat: integrate AudioProvider, MiniPlayer, and /listen route into App"
```

---

### Task 9: Frontend — Sidebar navigation link

**Files:**
- Modify: `frontend/src/components/layout/Sidebar.tsx`

- [ ] **Step 1: Add 🎧 听书 nav item**

Insert after the Stats button (line ~69, before `<Separator>`):

```typescript
      <button
        onClick={() => navigate('/listen')}
        className={`flex items-center gap-2.5 px-3 py-2 mx-3 rounded-md text-[13px] transition-colors text-left ${
          isActive('/listen') ? 'bg-accent-soft text-accent font-medium' : 'text-ink hover:bg-paper'
        }`}
      >
        🎧 听书
      </button>
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/layout/Sidebar.tsx
git commit -m "feat: add 🎧 听书 navigation link to sidebar"
```

---

### Task 10: Frontend — Clean up old AudioPlayer.tsx

**Files:**
- Modify: `frontend/src/components/novels/AudioPlayer.tsx`

- [ ] **Step 1: Strip out floating window and state management**

Since state is now in AudioContext, AudioPlayer.tsx becomes a thin control panel for use inside NovelDetail (the "🎧 听书" button to add chapters to playlist). Replace the entire file with:

```typescript
import { useAudio, type PlaylistItem } from 'src/lib/AudioContext';

interface ChapterInfo { number: number; title: string; word_count: number; novelId: string; novelTitle: string; }

export function AudioPlayer() {
  const { addToPlaylist, playChapter } = useAudio();
  // AudioPlayer is now just a helper rendered in NovelDetail for quick chapter add
  return null;
}

/** Hook for chapter list integration — now uses AudioContext */
export function useAddToPlaylist() {
  const { addToPlaylist, playChapter } = useAudio();
  return (novelId: string, novelTitle: string, ch: { number: number; title: string; word_count: number }, playNow = false) => {
    const item: PlaylistItem = { novelId, novelTitle, chapterNum: ch.number, chapterTitle: ch.title };
    addToPlaylist(item);
    if (playNow) playChapter(item);
  };
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/novels/AudioPlayer.tsx
git commit -m "refactor: strip AudioPlayer to thin wrapper, state moved to AudioContext"
```

---

### Task 11: Integration test — full flow verification

**Files:** None (verification only)

- [ ] **Step 1: Start backend and verify /api/audio/library returns data**

```bash
cd /Users/z/CodeBuddy/wechat && python3 -m uvicorn novel_writer.server:app --port 8000 &
sleep 2
curl -s http://localhost:8000/api/audio/library | python3 -m json.tool | head -30
```

Expected: JSON with `continue_listening` (null on first run) and `novels` array.

- [ ] **Step 2: Test POST /api/audio/progress**

```bash
# Replace NOVEL_ID with an actual novel ID from the library response
curl -s -X POST http://localhost:8000/api/audio/progress \
  -H "Content-Type: application/json" \
  -d '{"novel_id":"test-id","chapter_num":1,"position_sec":120.5}'
```

Expected: `{"ok":true}`

- [ ] **Step 3: Verify progress persistence**

```bash
curl -s http://localhost:8000/api/audio/progress/test-id | python3 -m json.tool
```

Expected: `{"novel_id":"test-id","chapter_num":1,"position_sec":120.5}`

- [ ] **Step 4: Start frontend and verify page renders**

```bash
cd /Users/z/CodeBuddy/wechat/frontend && npx vite --port 5173 &
sleep 3
curl -s http://localhost:5173/ | head -5
```

Expected: HTML page loads successfully.

- [ ] **Step 5: Check TypeScript compilation**

```bash
cd /Users/z/CodeBuddy/wechat/frontend && npx tsc --noEmit 2>&1 | head -20
```

Expected: No errors.

- [ ] **Step 6: Commit final verification state**

```bash
git status
# No uncommitted changes expected
```
