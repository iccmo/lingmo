/** 核心音频播放状态 + HTMLAudioElement 管理 */
import { create } from 'zustand';
import { useSettingsStore } from './settingsStore';
import { usePlaylistStore, type PlaylistItem } from './playlistStore';

export interface ListenRecord {
  chapterNum: number;
  status: 'done' | 'partial';
  position: number;
  timestamp: number;
}

export interface AudioState {
  // Player state
  playing: boolean;
  paused: boolean;
  loading: boolean;
  current: PlaylistItem | null;
  progress: number;     // 0-100
  positionSec: number;  // current position in seconds (updated ~250ms)
  speed: number;
  voice: string;
  volume: number;
  skipSeconds: number;
  duration: number;

  // Actions
  playChapter: (item: PlaylistItem, seekTo?: number) => void;
  togglePause: () => void;
  stop: () => void;
  skipChapter: (dir: 1 | -1) => void;
  playRandom: () => void;
  changeVoice: (v: string) => void;
  changeSpeed: (s: number) => void;
  seekTo: (pct: number) => void;
  skip15s: (dir: 1 | -1) => void;
  cycleSkip: () => void;
  rewind30s: () => void;
  undoSkip: () => void;
  setVolume: (v: number) => void;

  // Listen tracking
  addListenRecord: (novelId: string, chapterNum: number, status: 'done' | 'partial', position: number) => void;
  getListenRecords: (novelId: string) => ListenRecord[];
  isListened: (novelId: string, chapterNum: number) => 'done' | 'partial' | null;
  getResume: () => { novelId: string; chapterNum: number; position: number; time: number } | null;
}

// Internal mutable refs (not reactive — avoids re-render on every tick)
let _audio: HTMLAudioElement | null = null;
let _positionTimer: ReturnType<typeof setInterval> | undefined;
let _skipHistory: number[] = [];

function _ttsUrl(item: PlaylistItem, speed: number, voice: string): string {
  const dramaticMode = useSettingsStore.getState().dramaticMode;
  const rate = speed === 1.0 ? '+0%'
    : speed > 1 ? `+${Math.round((speed - 1) * 100)}%`
      : `${Math.round((speed - 1) * 100)}%`;
  const endpoint = dramaticMode ? 'tts-dramatic' : 'tts';
  return `/api/novels/${item.novelId}/chapters/${item.chapterNum}/${endpoint}?voice=${voice}&rate=${encodeURIComponent(rate)}`;
}

function _cleanupAudio() {
  if (_positionTimer) { clearInterval(_positionTimer); _positionTimer = undefined; }
  if (_audio) {
    _audio.pause();
    _audio.src = '';
    _audio.load();
    _audio = null;
  }
}

export const useAudioStore = create<AudioState>((set, get) => ({
  playing: false,
  paused: false,
  loading: false,
  current: null,
  progress: 0,
  positionSec: 0,
  speed: 1.0,
  voice: (() => {
    try { return localStorage.getItem('tts-voice') || 'zh-CN-XiaoxiaoNeural'; }
    catch { return 'zh-CN-XiaoxiaoNeural'; }
  })(),
  volume: (() => {
    try { return Number(localStorage.getItem('audio-volume')) || 0.8; }
    catch { return 0.8; }
  })(),
  skipSeconds: 15,
  duration: 0,

  playChapter: (item, seekTo = 0) => {
    _cleanupAudio();
    set({ loading: true, current: item, playing: false, paused: false, progress: 0, positionSec: seekTo });

    const state = get();
    const url = _ttsUrl(item, state.speed, state.voice);
    const audio = new Audio(url);
    audio.volume = state.volume;
    _audio = audio;

    audio.onloadedmetadata = () => {
      if (audio !== _audio) return;
      set({ duration: audio.duration || 0 });
      if (seekTo > 0) audio.currentTime = seekTo;
    };

    audio.ontimeupdate = () => {
      if (audio !== _audio || !audio.duration) return;
      const pos = audio.currentTime;
      set({ positionSec: pos, progress: (pos / audio.duration) * 100 });
    };

    audio.onplaying = () => {
      if (audio !== _audio) return;
      set({ playing: true, paused: false, loading: false });
    };

    audio.onpause = () => {
      if (audio !== _audio) return;
      set({ playing: false, paused: true });
    };

    audio.onended = () => {
      if (audio !== _audio) return;
      const settings = useSettingsStore.getState();
      const playlist = usePlaylistStore.getState();
      usePlaylistStore.getState().addToHistory(item);

      // Mark as listened
      _markListened(item.novelId, item.chapterNum, 'done', audio.duration || 0);

      // Sleep stop
      if (settings.sleepAtChapterEnd && settings.sleepTimer > 0) {
        useSettingsStore.getState().setSleepAtChapterEnd(false);
        useSettingsStore.getState().setSleepTimer(0);
        useSettingsStore.getState().setSleepRemaining(0);
        _cleanupAudio();
        set({ playing: false, paused: false });
        return;
      }

      // Repeat one
      if (playlist.playMode === 'repeat-one') {
        setTimeout(() => get().playChapter(item), 300);
        return;
      }

      // Shuffle
      if (playlist.playMode === 'shuffle') {
        get().playRandom();
        return;
      }

      // Radio mode
      if (settings.radioMode) {
        get().playRandom();
        return;
      }

      // Speed train
      if (settings.speedTrain) {
        const lvl = settings.speedTrainLevel + 1;
        useSettingsStore.getState().setSpeedTrainLevel(lvl);
        const baseSpeed = lvl <= 1 ? 1.0 : lvl <= 3 ? 1.25 : lvl <= 5 ? 1.5 : lvl <= 8 ? 1.75 : 2.0;
        get().changeSpeed(baseSpeed);
      }

      // Sequential: play next
      if (settings.autoContinue) {
        get().skipChapter(1);
        return;
      }

      // No auto-continue — just stop
      _cleanupAudio();
      set({ playing: false, paused: false, current: null });
    };

    audio.onerror = () => {
      set({ loading: false, playing: false });
    };

    audio.play().catch((e: Error) => {
      if (e.name === 'AbortError') return;
      set({ loading: false });
    });
  },

  togglePause: () => {
    const audio = _audio;
    if (!audio) return;
    if (audio.paused) {
      audio.play();
    } else {
      audio.pause();
    }
  },

  stop: () => {
    _cleanupAudio();
    set({ playing: false, paused: false, loading: false, current: null, progress: 0, positionSec: 0 });
  },

  skipChapter: (dir) => {
    const state = get();
    const playlist = usePlaylistStore.getState();
    if (!state.current || playlist.playlist.length === 0) return;

    const idx = playlist.playlist.findIndex(
      (p) => p.novelId === state.current!.novelId && p.chapterNum === state.current!.chapterNum);
    if (idx === -1) return;

    let nextIdx = idx + dir;
    if (nextIdx < 0) nextIdx = playlist.playlist.length - 1;
    if (nextIdx >= playlist.playlist.length) nextIdx = 0;

    get().playChapter(playlist.playlist[nextIdx]);
  },

  playRandom: () => {
    const playlist = usePlaylistStore.getState();
    if (playlist.playlist.length === 0) return;
    const idx = Math.floor(Math.random() * playlist.playlist.length);
    get().playChapter(playlist.playlist[idx]);
  },

  changeVoice: (v) => {
    set({ voice: v });
    try { localStorage.setItem('tts-voice', v); } catch {}
    const state = get();
    if (state.current) {
      _cleanupAudio();
      get().playChapter(state.current, state.positionSec);
    }
  },

  changeSpeed: (s) => {
    set({ speed: s });
    const state = get();
    if (state.current) {
      _cleanupAudio();
      get().playChapter(state.current, state.positionSec);
    }
  },

  seekTo: (pct) => {
    const audio = _audio;
    if (!audio || !audio.duration) return;
    const pos = (pct / 100) * audio.duration;
    audio.currentTime = pos;
    set({ positionSec: pos, progress: pct });
  },

  skip15s: (dir) => {
    const audio = _audio;
    if (!audio || !audio.duration) return;
    const state = get();
    const delta = state.skipSeconds * dir;
    const newTime = Math.max(0, Math.min(audio.duration, audio.currentTime + delta));
    audio.currentTime = newTime;
    _skipHistory.push(state.skipSeconds);
    if (_skipHistory.length > 10) _skipHistory.shift();
  },

  cycleSkip: () => {
    const opts = [10, 15, 20, 30, 60];
    const state = get();
    const idx = opts.indexOf(state.skipSeconds);
    set({ skipSeconds: opts[(idx + 1) % opts.length] });
  },

  rewind30s: () => {
    const audio = _audio;
    if (!audio || !audio.duration) return;
    audio.currentTime = Math.max(0, audio.currentTime - 30);
  },

  undoSkip: () => {
    const audio = _audio;
    if (!audio || !audio.duration) return;
    const lastSkip = _skipHistory.pop();
    if (lastSkip) {
      audio.currentTime = Math.max(0, audio.currentTime - lastSkip);
    }
  },

  setVolume: (v) => {
    set({ volume: v });
    if (_audio) _audio.volume = v;
    try { localStorage.setItem('audio-volume', String(v)); } catch {}
  },

  // ── Listen tracking ──
  addListenRecord: (novelId, chapterNum, status, position) => {
    try {
      const key = `listen-${novelId}`;
      const raw = localStorage.getItem(key) || '[]';
      const records: ListenRecord[] = JSON.parse(raw);
      const idx = records.findIndex((r) => r.chapterNum === chapterNum);
      const entry: ListenRecord = { chapterNum, status, position, timestamp: Date.now() };
      if (idx >= 0) {
        records[idx] = entry;
      } else {
        records.push(entry);
      }
      localStorage.setItem(key, JSON.stringify(records.slice(-100)));
    } catch {}
  },

  getListenRecords: (novelId) => {
    try {
      const raw = localStorage.getItem(`listen-${novelId}`) || '[]';
      return JSON.parse(raw);
    } catch { return []; }
  },

  isListened: (novelId, chapterNum) => {
    try {
      const raw = localStorage.getItem(`listen-${novelId}`) || '[]';
      const records: ListenRecord[] = JSON.parse(raw);
      const r = records.find((r) => r.chapterNum === chapterNum);
      return r ? r.status : null;
    } catch { return null; }
  },

  getResume: () => {
    try {
      const raw = localStorage.getItem('audio-resume');
      return raw ? JSON.parse(raw) : null;
    } catch { return null; }
  },
}));

// ── Private helpers ──

function _markListened(novelId: string, chapterNum: number, status: 'done' | 'partial', position: number) {
  useAudioStore.getState().addListenRecord(novelId, chapterNum, status, position);
}
