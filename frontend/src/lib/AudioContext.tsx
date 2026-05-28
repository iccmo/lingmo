import { createContext, useContext, useState, useEffect, useRef, useCallback, type ReactNode } from 'react';
import { toast } from 'sonner';
import { startAmbient, stopAmbient, setAmbientVolume as seSetAmbVol, startMusic, stopMusic, setMusicVolume as seSetMusVol } from 'src/lib/SoundEngine';

const VOICES = [
  { id: 'zh-CN-XiaoxiaoNeural', name: '晓晓', gender: '女', style: '温柔' },
  { id: 'zh-CN-YunxiNeural', name: '云希', gender: '男', style: '沉稳' },
  { id: 'zh-CN-XiaoyiNeural', name: '晓伊', gender: '女', style: '活泼' },
  { id: 'zh-CN-YunyangNeural', name: '云扬', gender: '男', style: '新闻' },
  { id: 'zh-CN-YunjianNeural', name: '云健', gender: '男', style: '运动' },
  { id: 'zh-CN-YunxiaNeural', name: '云夏', gender: '男', style: '深情' },
  { id: 'zh-CN-liaoning-XiaobeiNeural', name: '晓北', gender: '女', style: '东北话' },
  { id: 'zh-CN-shaanxi-XiaoniNeural', name: '晓妮', gender: '女', style: '陕西话' },
] as const;

export type PlaylistItem = {
  novelId: string;
  novelTitle: string;
  chapterNum: number;
  chapterTitle: string;
};

export type ListenStatus = 'done' | 'partial';

export interface ListenRecord {
  chapterNum: number;
  status: ListenStatus;
  position: number;
  timestamp: number;
}

export interface Achievement {
  id: string;
  title: string;
  desc: string;
  icon: string;
  unlocked: boolean;
  progress: number;
  target: number;
}

export interface Bookmark {
  id: string;
  novelId: string;
  novelTitle: string;
  chapterNum: number;
  chapterTitle: string;
  position: number;
  note: string;
  tag: string;
  createdAt: number;
}

interface ResumeData {
  novelId: string;
  chapterNum: number;
  position: number;
  time: number;
}

interface AudioActions {
  playChapter: (item: PlaylistItem, seekTo?: number) => void;
  togglePause: () => void;
  stop: () => void;
  skipChapter: (dir: 1 | -1) => void;
  playRandom: () => void;
  addToPlaylist: (item: PlaylistItem) => void;
  removeFromPlaylist: (idx: number) => void;
  clearPlaylist: () => void;
  changeVoice: (v: string) => void;
  changeSpeed: (s: number) => void;
  startSleepTimer: (mins: number) => void;
  cancelSleepTimer: () => void;
  sleepAtChapterEnd: boolean;
  setSleepAtChapterEnd: (v: boolean) => void;
  getResume: () => ResumeData | null;
  getListened: (novelId: string) => ListenRecord[];
  isListened: (novelId: string, chapterNum: number) => ListenStatus | null;
  addBookmark: (note?: string) => void;
  removeBookmark: (id: string) => void;
  getBookmarks: () => Bookmark[];
  getHistory: () => PlaylistItem[];
  autoContinue: boolean;
  toggleAutoContinue: () => void;
  seekTo: (pct: number) => void;
  skip15s: (dir: 1 | -1) => void;
  cycleSkip: () => void;
  skipSeconds: number;
  rewind30s: () => void;
  undoSkip: () => void;
  achievements: Achievement[];
  volume: number;
  setVolume: (v: number) => void;
  speed: number;
  playMode: 'sequential' | 'shuffle' | 'repeat-one';
  cyclePlayMode: () => void;
  sleepRemaining: number;
  showRemaining: boolean;
  toggleTimeDisplay: () => void;
  ambient: string | null;
  setAmbient: (a: string | null) => void;
  ambientVolume: number;
  setAmbientVolume: (v: number) => void;
  music: string | null;
  setMusic: (m: string | null) => void;
  musicVolume: number;
  setMusicVolume: (v: number) => void;
  sleepStory: boolean;
  toggleSleepStory: () => void;
  speedTrain: boolean;
  toggleSpeedTrain: () => void;
  speedTrainLevel: number;
}

interface AudioState {
  playing: boolean;
  paused: boolean;
  loading: boolean;
  current: PlaylistItem | null;
  progress: number;
  positionSec: number;
  speed: number;
  voice: string;
  playlist: PlaylistItem[];
  sleepTimer: number;
  voices: typeof VOICES;
  autoContinue: boolean;
  playMode: 'sequential' | 'shuffle' | 'repeat-one';
  sleepRemaining: number;
  showRemaining: boolean;
  ambient: string | null;
  ambientVolume: number;
  music: string | null;
  musicVolume: number;
  sleepStory: boolean;
  speedTrain: boolean;
  speedTrainLevel: number;
  achievements: Achievement[];
  radioMode: boolean;
  toggleRadioMode: () => void;
  dramaticMode: boolean;
  toggleDramaticMode: () => void;
  eqPreset: 'flat' | 'voice' | 'bass';
  cycleEQ: () => void;
}

const AudioCtx = createContext<(AudioState & AudioActions) | null>(null);

// ── localStorage helpers ──

function loadPlaylist(): PlaylistItem[] {
  try { return JSON.parse(localStorage.getItem('audio-playlist') || '[]'); } catch { return []; }
}
function savePlaylist(items: PlaylistItem[]) {
  localStorage.setItem('audio-playlist', JSON.stringify(items));
}
function loadResume(): ResumeData | null {
  try { return JSON.parse(localStorage.getItem('audio-resume') || 'null'); } catch { return null; }
}
function loadListened(novelId: string): ListenRecord[] {
  try { return JSON.parse(localStorage.getItem(`audio-listened-${novelId}`) || '[]'); } catch { return []; }
}
function saveListened(novelId: string, records: ListenRecord[]) {
  localStorage.setItem(`audio-listened-${novelId}`, JSON.stringify(records));
}
function loadBookmarks(): Bookmark[] {
  try { return JSON.parse(localStorage.getItem('audio-bookmarks') || '[]'); } catch { return []; }
}
function saveBookmarks(bookmarks: Bookmark[]) {
  localStorage.setItem('audio-bookmarks', JSON.stringify(bookmarks));
}

// ── Provider ──

export function AudioProvider({ children }: { children: ReactNode }) {
  const [playing, setPlaying] = useState(false);
  const [paused, setPaused] = useState(false);
  const [loading, setLoading] = useState(false);
  const [current, setCurrent] = useState<PlaylistItem | null>(null);
  const [progress, setProgress] = useState(0);
  const [positionSec, setPositionSec] = useState(0);
  const [speed, setSpeed] = useState(1.0);
  const [voice, setVoice] = useState(() => {
    const saved = localStorage.getItem('tts-voice');
    // Fallback if saved voice no longer exists (e.g., XiaochenNeural was removed)
    const valid = VOICES.map(v => v.id);
    return saved && valid.includes(saved as typeof valid[number]) ? saved : 'zh-CN-XiaoxiaoNeural';
  });
  const [playlist, setPlaylist] = useState<PlaylistItem[]>(loadPlaylist);
  const [sleepTimer, setSleepTimer] = useState(0);
  const [autoContinue, setAutoContinue] = useState(() => localStorage.getItem('audio-autocontinue') !== 'false');
  const [volumeState, setVolumeState] = useState(() => {
    const v = localStorage.getItem('audio-volume');
    return v ? parseFloat(v) : 0.8;
  });
  const [playMode, setPlayMode] = useState<'sequential' | 'shuffle' | 'repeat-one'>(() => {
    const m = localStorage.getItem('audio-playmode');
    return (m as 'sequential' | 'shuffle' | 'repeat-one') || 'sequential';
  });
  const [sleepRemaining, setSleepRemaining] = useState(0);
  const sleepEndRef = useRef<number>(0);
  const [skipSeconds, setSkipSeconds] = useState(15);
  const [sleepAtChapterEnd, setSleepAtChapterEnd] = useState(false);
  const [eqPreset, setEqPreset] = useState<'flat' | 'voice' | 'bass'>(() => {
    const p = localStorage.getItem('audio-eq');
    return (p as 'flat' | 'voice' | 'bass') || 'flat';
  });
  const [showRemaining, setShowRemaining] = useState(false);
  const [ambient, setAmbientState] = useState<string | null>(null);
  const [ambientVolume, setAmbientVolumeState] = useState(0.3);
  const [sleepStory, setSleepStoryState] = useState(false);
  const [speedTrain, setSpeedTrainState] = useState(false);
  const [speedTrainLevel, setSpeedTrainLevel] = useState(0);
  const [radioMode, setRadioMode] = useState(false);
  const [dramaticMode, setDramaticMode] = useState(false);
  const [music, setMusicState] = useState<string | null>(null);
  const [musicVolume, setMusicVolumeState] = useState(0.5);

  const audioRef = useRef<HTMLAudioElement | null>(null);
  const preloadRef = useRef<HTMLAudioElement | null>(null);
  const volumeRef = useRef(volumeState);
  volumeRef.current = volumeState;
  const eqCtxRef = useRef<AudioContext | null>(null);

  // ── Server data sync (every 30s) ──
  useEffect(() => {
    // Load from server on mount (merge with localStorage)
    fetch('/api/audio/data').then(r => r.json()).then(data => {
      if (data.bookmarks?.length) {
        const existing = loadBookmarks();
        const merged = [...data.bookmarks, ...existing.filter((e: Bookmark) => !data.bookmarks.find((d: Bookmark) => d.id === e.id))];
        saveBookmarks(merged.slice(0, 200));
      }
      if (data.playlist?.length && loadPlaylist().length === 0) {
        savePlaylist(data.playlist);
        setPlaylist(data.playlist);
      }
      if (data.settings) {
        Object.entries(data.settings).forEach(([k, v]) => {
          if (!localStorage.getItem(k)) localStorage.setItem(k, v as string);
        });
      }
    }).catch(() => {});

    // Periodic sync to server
    const syncInterval = setInterval(() => {
      const payload: Record<string, unknown> = {
        bookmarks: loadBookmarks(),
        playlist: loadPlaylist(),
        settings: {
          'tts-voice': localStorage.getItem('tts-voice') || '',
          'audio-volume': localStorage.getItem('audio-volume') || '0.8',
          'audio-autocontinue': localStorage.getItem('audio-autocontinue') || 'true',
          'audio-playmode': localStorage.getItem('audio-playmode') || 'sequential',
          'audio-eq': localStorage.getItem('audio-eq') || 'flat',
          'dark': localStorage.getItem('dark') || '',
        },
        stats: JSON.parse(localStorage.getItem('audio-stats') || '{}'),
      };
      fetch('/api/audio/sync', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      }).catch(() => {});
    }, 30000);
    return () => clearInterval(syncInterval);
  }, []);

  // ── Browser tab title ──
  useEffect(() => {
    if (playing && !paused && currentRef.current) {
      document.title = `🔊 ${currentRef.current.novelTitle} · 第${currentRef.current.chapterNum}章`;
    }
    return () => { document.title = '灵墨'; };
  }, [playing, paused, current]);

  // ── Recently played history ──
  function addHistory(item: PlaylistItem) {
    try {
      const history: PlaylistItem[] = JSON.parse(localStorage.getItem('audio-history') || '[]');
      const filtered = history.filter(h => !(h.novelId === item.novelId && h.chapterNum === item.chapterNum));
      filtered.unshift(item);
      localStorage.setItem('audio-history', JSON.stringify(filtered.slice(0, 20)));
    } catch {}
  }
  function getHistory(): PlaylistItem[] {
    try { return JSON.parse(localStorage.getItem('audio-history') || '[]'); } catch { return []; }
  }
  const sleepTimerRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const sleepCountdownRef = useRef<ReturnType<typeof setInterval> | undefined>(undefined);
  const currentRef = useRef<PlaylistItem | null>(null);
  const lastPauseTime = useRef(0);
  const lastSkipPos = useRef<{ item: PlaylistItem; position: number } | null>(null);

  currentRef.current = current;

  // ── Listened tracking ──

  function markListened(item: PlaylistItem, status: ListenStatus, pos: number) {
    const records = loadListened(item.novelId);
    const existing = records.findIndex(r => r.chapterNum === item.chapterNum);
    const record: ListenRecord = { chapterNum: item.chapterNum, status, position: Math.round(pos), timestamp: Date.now() };
    if (existing >= 0) {
      records[existing] = record;
    } else {
      records.push(record);
    }
    saveListened(item.novelId, records);
  }

  function getListened(novelId: string): ListenRecord[] {
    return loadListened(novelId);
  }

  function isListened(novelId: string, chapterNum: number): ListenStatus | null {
    const records = loadListened(novelId);
    const r = records.find(r => r.chapterNum === chapterNum);
    return r ? r.status : null;
  }

  // ── Bookmarks ──

  function addBookmark(note?: string) {
    const item = currentRef.current;
    const audio = audioRef.current;
    if (!item || !audio) {
      toast.info('没有正在播放的内容');
      return;
    }
    const bookmarks = loadBookmarks();
    const bookmark: Bookmark = {
      id: `bm-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
      novelId: item.novelId,
      novelTitle: item.novelTitle,
      chapterNum: item.chapterNum,
      chapterTitle: item.chapterTitle,
      position: Math.round(audio.currentTime),
      note: note || '',
      tag: '',
      createdAt: Date.now(),
    };
    bookmarks.push(bookmark);
    saveBookmarks(bookmarks);
    toast.success(note ? '已标记：' + note.slice(0, 20) : '已标记时间戳');
  }

  function removeBookmark(id: string) {
    const bookmarks = loadBookmarks().filter(b => b.id !== id);
    saveBookmarks(bookmarks);
    toast.success('已删除标记');
  }

  function getBookmarks(): Bookmark[] {
    return loadBookmarks().sort((a, b) => b.createdAt - a.createdAt);
  }

  // ── Save resume ──

  function saveResume(item: PlaylistItem, pos: number) {
    localStorage.setItem('audio-resume', JSON.stringify({
      novelId: item.novelId, chapterNum: item.chapterNum, position: pos, time: Date.now(),
    }));
    setPositionSec(pos);
  }

  // ── Build TTS URL ──

  function ttsUrl(item: PlaylistItem): string {
    const rateParam = speed === 1.0 ? '+0%'
      : speed > 1 ? `+${Math.round((speed - 1) * 100)}%`
        : `${Math.round((speed - 1) * 100)}%`;
    const endpoint = dramaticMode ? 'tts-dramatic' : 'tts';
    return `/api/novels/${item.novelId}/chapters/${item.chapterNum}/${endpoint}?voice=${voice}&rate=${encodeURIComponent(rateParam)}`;
  }

  // ── Preload next chapter ──

  function preloadNext() {
    const pl = loadPlaylist();
    const cur = currentRef.current;
    if (!cur) return;
    const idx = pl.findIndex(p => p.novelId === cur.novelId && p.chapterNum === cur.chapterNum);
    const next = pl[idx + 1];
    if (!next) return;

    // Cancel existing preload
    if (preloadRef.current) {
      preloadRef.current.src = '';
      preloadRef.current = null;
    }

    const preload = new Audio(ttsUrl(next));
    preload.preload = 'auto';
    preloadRef.current = preload;
  }

  // ── Play chapter ──

  const playChapter = useCallback((item: PlaylistItem, seekTo = 0) => {
    // Clean up old audio completely before creating new one
    const oldAudio = audioRef.current;
    if (oldAudio) {
      oldAudio.onerror = null;
      oldAudio.pause();
      oldAudio.src = '';
      audioRef.current = null;
    }

    setCurrent(item);
    setLoading(true);
    setPlaying(false);
    setPaused(false);
    setProgress(0);

    // Use preloaded audio if it matches
    if (preloadRef.current && preloadRef.current.src.includes(`/chapters/${item.chapterNum}/tts`)) {
      audioRef.current = preloadRef.current;
      preloadRef.current = null;
    } else {
      if (preloadRef.current) {
        preloadRef.current.src = '';
        preloadRef.current = null;
      }
      audioRef.current = new Audio(ttsUrl(item));
    }

    const audio = audioRef.current!;

    const onMeta = () => {
      audio.currentTime = seekTo;
      audio.volume = volumeRef.current;
      addHistory(item);
      applyEQ(audio);
      setLoading(false);
      setPlaying(true);
      setPaused(false);
      // Show chapter summary as "previously on" for chapter 2+
      if (item.chapterNum > 1 && item.chapterTitle) {
        setTimeout(() => {
          toast(`📖 ${item.chapterTitle}`, { duration: 2500, description: `第${item.chapterNum}章` });
        }, 500);
      }
    };

    const onTime = () => {
      if (audio.duration) {
        const pct = Math.round((audio.currentTime / audio.duration) * 100);
        setProgress(pct);
        setPositionSec(audio.currentTime);
        saveResume(item, audio.currentTime);
        if (pct >= 85) preloadNext();
        if (autoContinue && pct >= 90) {
          const pl = loadPlaylist();
          const idx = pl.findIndex(p => p.novelId === item.novelId && p.chapterNum === item.chapterNum);
          const nextInPl = pl[idx + 1];
          if (!nextInPl) {
            fetch(`/api/novels/${item.novelId}`)
              .then(r => r.json())
              .then(data => {
                const chapters: { number: number; title: string }[] = data.chapters || [];
                const nextCh = chapters.find((c: { number: number }) => c.number === item.chapterNum + 1);
                if (nextCh) {
                  const nextItem: PlaylistItem = { novelId: item.novelId, novelTitle: item.novelTitle, chapterNum: nextCh.number, chapterTitle: nextCh.title };
                  setPlaylist(prev => {
                    if (prev.find(p => p.novelId === nextItem.novelId && p.chapterNum === nextItem.chapterNum)) return prev;
                    const next = [...prev, nextItem];
                    savePlaylist(next);
                    return next;
                  });
                }
              })
              .catch(() => {});
          }
        }
      }
    };

    const onEnd = () => {
      setProgress(100);
      markListened(item, 'done', audio.duration || 0);
      saveResume(item, audio.duration || 0);
      updateStats(item, audio.duration || 0);

      // Sleep-at-chapter-end: stop after this chapter
      if (sleepAtChapterEnd && sleepTimer > 0) {
        setSleepAtChapterEnd(false);
        cancelSleepTimer();
        setPlaying(false);
        toast.success('⏰ 章节结束，定时停止');
        return;
      }

      // Speed training: increment level per chapter
      if (speedTrain) {
        const newLevel = speedTrainLevel + 1;
        setSpeedTrainLevel(newLevel);
        const newSpd = Math.min(2.0, +(1.0 + newLevel * 0.05).toFixed(2));
        setSpeed(newSpd);
        if (newSpd < 2.0) {
          toast.info(`🏃 语速训练 Lv${newLevel}: ${newSpd}x`, { duration: 2000 });
        } else {
          toast.success('🏆 语速训练完成! 已达 2.0x 上限');
          setSpeedTrainState(false);
          setSpeedTrainLevel(0);
        }
      }

      const pl = loadPlaylist();
      const idx = pl.findIndex(p => p.novelId === item.novelId && p.chapterNum === item.chapterNum);

      // Respect play mode
      if (playMode === 'repeat-one') {
        setTimeout(() => playChapter(item), 300);
        return;
      }

      let next: PlaylistItem | undefined;
      if (playMode === 'shuffle') {
        const others = pl.filter(p => !(p.novelId === item.novelId && p.chapterNum === item.chapterNum));
        if (others.length > 0) {
          next = others[Math.floor(Math.random() * others.length)];
        }
      } else {
        next = pl[idx + 1];
      }

      if (next) {
        toast.info(`${next.novelTitle} · 第${next.chapterNum}章`, { duration: 1500 });
        // Cross-fade: short overlap for smooth transition
        setTimeout(() => playChapter(next), 200);
        // The new playChapter will start at volume 0 and fade in
        setTimeout(() => {
          if (audioRef.current) {
            const rampUp = (step: number) => {
              if (!audioRef.current || step > 10) return;
              const v = volumeRef.current * (step / 10);
              audioRef.current.volume = Math.max(0.01, v);
              if (step < 10) setTimeout(() => rampUp(step + 1), 150);
            };
            audioRef.current.volume = 0;
            rampUp(1);
          }
        }, 250);
      } else if (radioMode) {
        // Radio mode: pick random chapter from any novel
        pickRandomChapter().then(randomCh => {
          if (randomCh) {
            toast.info(`📻 ${randomCh.novelTitle} · 第${randomCh.chapterNum}章`, { duration: 2000 });
            setTimeout(() => playChapter(randomCh), 500);
          } else {
            setPlaying(false);
            toast.success('电台播放结束');
          }
        });
      } else {
        setPlaying(false);
        toast.success('播放列表结束');
      }
    };

    const onErr = () => {
      const err = audio.error;
      const code = err ? err.code : 'unknown';
      const codes: Record<number, string> = { 1: 'ABORTED', 2: 'NETWORK', 3: 'DECODE', 4: 'SRC_NOT_SUPPORTED' };
      console.error(`[Audio] Error code=${code} (${codes[code as number] || '?'}), src=${audio.src.slice(0, 100)}`);
      toast.error(`播放失败 (${codes[code as number] || code})`);
      setLoading(false);
      setPlaying(false);
      setCurrent(null);
    };

    audio.onloadedmetadata = onMeta;
    audio.ontimeupdate = onTime;
    audio.onended = onEnd;
    audio.onerror = onErr;

    audio.play().catch((e: DOMException) => {
      if (e.name === 'AbortError') {
        // Browser interrupted play() because new play() was called — this is expected during fast chapter switching
        console.debug('[Audio] AbortError (expected on fast switching)');
      } else {
        console.error(`[Audio] play() rejected: ${e.name}: ${e.message}`);
        toast.error(`播放被阻止: ${e.message.slice(0, 30)}`);
      }
    });
  }, [speed, voice, autoContinue]);

  // ── Controls ──

  const togglePause = useCallback(() => {
    if (!audioRef.current) return;
    if (paused) {
      // Auto-rewind if paused for >2 minutes
      const pausedDuration = Date.now() - lastPauseTime.current;
      if (pausedDuration > 120000) {
        const rewind = Math.min(15, audioRef.current.currentTime);
        audioRef.current.currentTime -= rewind;
        toast.info(`⏪ 自动回退 ${Math.round(rewind)} 秒`, { duration: 2000 });
      }
      audioRef.current.play();
      setPaused(false);
    } else {
      audioRef.current.pause();
      setPaused(true);
      lastPauseTime.current = Date.now();
      if (currentRef.current) {
        const pos = audioRef.current.currentTime;
        saveResume(currentRef.current, pos);
        markListened(currentRef.current, 'partial', pos);
        if (pos > 30) {
          addBookmark('⏸ 暂停位置');
        }
      }
    }
  }, [paused]);

  const stop = useCallback(() => {
    if (audioRef.current) { audioRef.current.pause(); audioRef.current = null; }
    if (preloadRef.current) { preloadRef.current.src = ''; preloadRef.current = null; }
    setPlaying(false);
    setPaused(false);
    setLoading(false);
    setProgress(0);
    setPositionSec(0);
    cancelSleepTimer();
  }, []);

  const skipChapter = useCallback((dir: 1 | -1) => {
    const cur = currentRef.current;
    if (!cur) return;
    // Save current position for undo
    if (audioRef.current) {
      lastSkipPos.current = { item: { ...cur }, position: audioRef.current.currentTime };
    }
    const pl = loadPlaylist();
    const idx = pl.findIndex(p => p.novelId === cur.novelId && p.chapterNum === cur.chapterNum);
    const target = pl[idx + dir];
    if (target) playChapter(target);
  }, [playChapter]);

  function undoSkip() {
    const prev = lastSkipPos.current;
    if (!prev) { toast.info('没有可返回的位置'); return; }
    lastSkipPos.current = null;
    playChapter(prev.item, prev.position);
    toast.info('↩️ 已回到之前位置');
  }

  const playRandom = useCallback(() => {
    const pl = loadPlaylist();
    if (pl.length === 0) return;
    playChapter(pl[Math.floor(Math.random() * pl.length)]);
  }, [playChapter]);

  const addToPlaylist = useCallback((item: PlaylistItem) => {
    setPlaylist(prev => {
      if (prev.find(p => p.novelId === item.novelId && p.chapterNum === item.chapterNum)) return prev;
      const next = [...prev, item];
      savePlaylist(next);
      return next;
    });
    toast.success('已加入播放列表');
  }, []);

  const removeFromPlaylist = useCallback((idx: number) => {
    setPlaylist(prev => {
      const next = prev.filter((_, i) => i !== idx);
      savePlaylist(next);
      return next;
    });
  }, []);

  const clearPlaylist = useCallback(() => {
    setPlaylist([]);
    localStorage.removeItem('audio-playlist');
  }, []);

  const changeVoice = useCallback((v: string) => {
    setVoice(v);
    localStorage.setItem('tts-voice', v);
    if (currentRef.current && audioRef.current) {
      const pos = audioRef.current.currentTime;
      playChapter(currentRef.current, pos);
    }
  }, [playChapter]);

  const changeSpeed = useCallback((s: number) => {
    setSpeed(s);
    if (currentRef.current && audioRef.current) {
      const pos = audioRef.current.currentTime;
      playChapter(currentRef.current, pos);
    }
  }, [playChapter]);

  function toggleAutoContinue() {
    const next = !autoContinue;
    setAutoContinue(next);
    localStorage.setItem('audio-autocontinue', String(next));
    toast.info(next ? '自动连播已开启' : '自动连播已关闭');
  }

  function seekTo(pct: number) {
    const audio = audioRef.current;
    if (audio && audio.duration) {
      audio.currentTime = (pct / 100) * audio.duration;
      setProgress(pct);
      setPositionSec(audio.currentTime);
    }
  }

  function setVolumeFn(v: number) {
    const vol = Math.max(0, Math.min(1, v));
    setVolumeState(vol);
    localStorage.setItem('audio-volume', String(vol));
    if (audioRef.current) audioRef.current.volume = vol;
  }

  function skip15s(dir: 1 | -1) {
    const audio = audioRef.current;
    if (!audio) return;
    const newTime = audio.currentTime + dir * skipSeconds;
    audio.currentTime = Math.max(0, Math.min(audio.duration || 0, newTime));
    setPositionSec(audio.currentTime);
  }

  function cycleSkip() {
    const opts = [10, 15, 20, 30];
    const idx = opts.indexOf(skipSeconds);
    const next = opts[(idx + 1) % opts.length];
    setSkipSeconds(next);
    toast.info(`快进/快退: ±${next}秒`);
  }

  function rewind30s() {
    const audio = audioRef.current;
    if (!audio) return;
    audio.currentTime = Math.max(0, audio.currentTime - 30);
    setPositionSec(audio.currentTime);
    toast.info('⏪ 回退 30 秒');
  }

  function cyclePlayMode() {
    const modes: Array<'sequential' | 'shuffle' | 'repeat-one'> = ['sequential', 'shuffle', 'repeat-one'];
    const idx = modes.indexOf(playMode);
    const next = modes[(idx + 1) % modes.length];
    setPlayMode(next);
    localStorage.setItem('audio-playmode', next);
    const labels: Record<string, string> = { sequential: '顺序播放', shuffle: '随机播放', 'repeat-one': '单曲循环' };
    toast.info(labels[next]);
  }

  function toggleTimeDisplay() {
    setShowRemaining(prev => !prev);
  }

  // ── Ambient sound generator ──
  function setAmbient(a: string | null) {
    setAmbientState(a);
    if (a) startAmbient(a as any, ambientVolume);
    else stopAmbient();
  }


  function setMusic(m: string | null) {
    setMusicState(m);
    if (m) startMusic(m as any, musicVolume);
    else stopMusic();
  }
  function setAmbientVolumeFn(v: number) {
    const vol = Math.max(0, Math.min(1, v));
    setAmbientVolumeState(vol);
    seSetAmbVol(vol);
  }
  function setMusicVolumeFn(v: number) {
    const vol = Math.max(0, Math.min(1, v));
    setMusicVolumeState(vol);
    seSetMusVol(vol);
  }


  // ── Achievement system ──
  function getAchievements(): Achievement[] {
    try {
      const stats = JSON.parse(localStorage.getItem('audio-stats') || '{"chapters":0,"seconds":0,"days":[],"voices":[],"novels":[]}');
      const chapters = stats.chapters || 0;
      const hours = (stats.seconds || 0) / 3600;
      const days = new Set(stats.days || []).size;
      const voiceCount = new Set(stats.voices || []).size;
      const novelCount = new Set(stats.novels || []).size;

      return [
        { id: 'first', title: '初次聆听', desc: '听完第一章', icon: '🎧', unlocked: chapters >= 1, progress: Math.min(chapters, 1), target: 1 },
        { id: 'ch10', title: '渐入佳境', desc: '累计收听 10 章', icon: '📚', unlocked: chapters >= 10, progress: Math.min(chapters, 10), target: 10 },
        { id: 'ch50', title: '书虫', desc: '累计收听 50 章', icon: '🐛', unlocked: chapters >= 50, progress: Math.min(chapters, 50), target: 50 },
        { id: 'ch100', title: '听书达人', desc: '累计收听 100 章', icon: '🏆', unlocked: chapters >= 100, progress: Math.min(chapters, 100), target: 100 },
        { id: 'hours5', title: '五小时', desc: '累计收听 5 小时', icon: '⏱️', unlocked: hours >= 5, progress: Math.min(hours, 5), target: 5 },
        { id: 'hours20', title: '马拉松', desc: '累计收听 20 小时', icon: '🏃', unlocked: hours >= 20, progress: Math.min(hours, 20), target: 20 },
        { id: 'streak3', title: '三日连播', desc: '连续 3 天收听', icon: '🔥', unlocked: days >= 3, progress: Math.min(days, 3), target: 3 },
        { id: 'streak7', title: '周更听众', desc: '连续 7 天收听', icon: '📅', unlocked: days >= 7, progress: Math.min(days, 7), target: 7 },
        { id: 'voices3', title: '声优探索者', desc: '使用过 3 种不同语音', icon: '🎭', unlocked: voiceCount >= 3, progress: Math.min(voiceCount, 3), target: 3 },
        { id: 'novels3', title: '博览群书', desc: '听过 3 部不同小说', icon: '📖', unlocked: novelCount >= 3, progress: Math.min(novelCount, 3), target: 3 },
      ];
    } catch { return []; }
  }

  function updateStats(item: PlaylistItem, seconds: number) {
    try {
      const stats = JSON.parse(localStorage.getItem('audio-stats') || '{"chapters":0,"seconds":0,"days":[],"voices":[],"novels":[]}');
      stats.chapters = (stats.chapters || 0) + 1;
      stats.seconds = (stats.seconds || 0) + Math.round(seconds);
      const today = new Date().toISOString().slice(0, 10);
      if (!(stats.days || []).includes(today)) (stats.days || []).push(today);
      if (!(stats.voices || []).includes(voice)) (stats.voices || []).push(voice);
      if (!(stats.novels || []).includes(item.novelId)) (stats.novels || []).push(item.novelId);
      stats.topSpeed = Math.max(stats.topSpeed || 1.0, speed);
      localStorage.setItem('audio-stats', JSON.stringify(stats));

      // Check for newly unlocked achievements
      const newAchievements = getAchievements();
      const oldUnlocked = JSON.parse(localStorage.getItem('audio-achievements-unlocked') || '[]');
      newAchievements.forEach(a => {
        if (a.unlocked && !oldUnlocked.includes(a.id)) {
          toast.success(`${a.icon} 成就解锁: ${a.title}`, { duration: 3000 });
          oldUnlocked.push(a.id);
        }
      });
      localStorage.setItem('audio-achievements-unlocked', JSON.stringify(oldUnlocked));
    } catch {}
  }

  // ── Sleep story mode (auto-fade speed + volume) ──
  function toggleSleepStory() {
    const next = !sleepStory;
    setSleepStoryState(next);
    if (next) {
      toast.info('🌙 睡前模式：语速将逐渐减慢，音量渐弱');
      // Auto-set 30-min timer if none active
      if (sleepTimer === 0) startSleepTimer(30);
    }
  }

  // ── Speed training (auto-increment speed per chapter) ──
  function toggleSpeedTrain() {
    const next = !speedTrain;
    setSpeedTrainState(next);
    if (next) {
      setSpeedTrainLevel(0);
      toast.info('🏃 语速训练：每章自动加速 0.05x');
    } else {
      setSpeedTrainLevel(0);
    }
  }

  // ── Radio mode: cross-novel random continuous play ──
  function toggleRadioMode() {
    const next = !radioMode;
    setRadioMode(next);
    if (next) {
      setAutoContinue(true);
      localStorage.setItem('audio-autocontinue', 'true');
      toast.info('📻 电台模式：跨书随机连播');
    }
  }

  function toggleDramaticMode() {
    const next = !dramaticMode;
    setDramaticMode(next);
    toast.info(next ? '🎭 角色扮演：单人多声线' : '普通朗读模式');
    // Restart current chapter with new mode
    if (currentRef.current && audioRef.current) {
      const pos = audioRef.current.currentTime;
      playChapter(currentRef.current, pos);
    }
  }

  function pickRandomChapter(): Promise<PlaylistItem | null> {
    return fetch('/api/novels')
      .then(r => r.json())
      .then((novels: Array<{id: string; title: string; total_chapters: number}>) => {
        const withChapters = novels.filter(n => n.total_chapters > 0);
        if (withChapters.length === 0) return null;
        const novel = withChapters[Math.floor(Math.random() * withChapters.length)];
        const chNum = 1 + Math.floor(Math.random() * novel.total_chapters);
        return fetch(`/api/novels/${novel.id}/chapters/${chNum}`)
          .then(r => r.json())
          .then((ch: {title: string}) => ({
            novelId: novel.id,
            novelTitle: novel.title,
            chapterNum: chNum,
            chapterTitle: ch.title || '',
          }));
      })
      .catch(() => null);
  }

  // Apply speed training on chapter end
  // This is called from onEnd — we need to track it
  // Actually done in the onEnd handler below

  // Apply sleep story slow-down in onTime
  // Also done in the onTime handler

  // Apply volume on audio creation
  // This needs to happen inside playChapter, so let me add it there directly.

  function getResume(): ResumeData | null {
    return loadResume();
  }

  // ── Web Audio EQ ──
  function applyEQ(audio: HTMLAudioElement) {
    try {
      eqCtxRef.current?.close();
    } catch {}
    try {
      const ctx = new (window.AudioContext || (window as any).webkitAudioContext)();
      eqCtxRef.current = ctx;
      const source = ctx.createMediaElementSource(audio);
      let lastNode: AudioNode = source;

      if (eqPreset === 'voice') {
        const peak = ctx.createBiquadFilter();
        peak.type = 'peaking'; peak.frequency.value = 2500; peak.Q.value = 0.5; peak.gain.value = 6;
        lastNode.connect(peak); lastNode = peak;
        const shelf = ctx.createBiquadFilter();
        shelf.type = 'highshelf'; shelf.frequency.value = 6000; shelf.gain.value = 3;
        lastNode.connect(shelf); lastNode = shelf;
      } else if (eqPreset === 'bass') {
        const low = ctx.createBiquadFilter();
        low.type = 'lowshelf'; low.frequency.value = 200; low.gain.value = 6;
        lastNode.connect(low); lastNode = low;
      }
      lastNode.connect(ctx.destination);
    } catch {
      // Media element already connected
    }
  }

  function cycleEQ() {
    const presets: Array<'flat' | 'voice' | 'bass'> = ['flat', 'voice', 'bass'];
    const idx = presets.indexOf(eqPreset);
    const next = presets[(idx + 1) % presets.length];
    setEqPreset(next);
    localStorage.setItem('audio-eq', next);
    const labels = { flat: '原声', voice: '语音增强', bass: '低音增强' };
    toast.info(`🎛 ${labels[next]}`);
    if (currentRef.current && audioRef.current) {
      const pos = audioRef.current.currentTime;
      playChapter(currentRef.current, pos);
    }
  }

  // ── Global keyboard shortcuts ──
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement).tagName;
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return;
      if (e.code === 'Space' && currentRef.current) {
        e.preventDefault();
        if (audioRef.current) {
          if (audioRef.current.paused) { audioRef.current.play(); setPaused(false); }
          else { audioRef.current.pause(); setPaused(true); }
        }
      }
      if (e.code === 'ArrowLeft') { e.preventDefault(); skip15s(-1); }
      if (e.code === 'ArrowRight') { e.preventDefault(); skip15s(1); }
      if (e.code === 'ArrowUp') { e.preventDefault(); setVolumeFn(Math.min(1, volumeRef.current + 0.05)); }
      if (e.code === 'ArrowDown') { e.preventDefault(); setVolumeFn(Math.max(0, volumeRef.current - 0.05)); }
      if (e.code === 'KeyN') { e.preventDefault(); skipChapter(1); }
      if (e.code === 'KeyP') { e.preventDefault(); skipChapter(-1); }
      if (e.code === 'KeyM') { e.preventDefault(); setVolumeFn(volumeRef.current > 0.01 ? 0 : 0.8); }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, []);

  // ── Media Session API (OS media center / lock screen / media keys) ──
  useEffect(() => {
    if (!('mediaSession' in navigator)) return;
    if (!current || !playing) {
      navigator.mediaSession.metadata = null;
      return;
    }
    navigator.mediaSession.metadata = new (window as any).MediaMetadata({
      title: `${current.novelTitle} · 第${current.chapterNum}章`,
      artist: current.chapterTitle || current.novelTitle,
      album: '灵墨',
    });
    navigator.mediaSession.setActionHandler('play', () => {
      if (audioRef.current?.paused) { audioRef.current.play(); setPaused(false); }
    });
    navigator.mediaSession.setActionHandler('pause', () => {
      if (audioRef.current && !audioRef.current.paused) { audioRef.current.pause(); setPaused(true); }
    });
    navigator.mediaSession.setActionHandler('previoustrack', () => skipChapter(-1));
    navigator.mediaSession.setActionHandler('nexttrack', () => skipChapter(1));
    navigator.mediaSession.setActionHandler('seekto', (details) => {
      if (details.seekTime != null && audioRef.current) {
        audioRef.current.currentTime = details.seekTime;
        setPositionSec(details.seekTime);
      }
    });
    navigator.mediaSession.playbackState = paused ? 'paused' : 'playing';
    return () => {
      navigator.mediaSession.setActionHandler('play', null);
      navigator.mediaSession.setActionHandler('pause', null);
      navigator.mediaSession.setActionHandler('previoustrack', null);
      navigator.mediaSession.setActionHandler('nexttrack', null);
      navigator.mediaSession.setActionHandler('seekto', null);
    };
  }, [current, playing, paused]);

  // ── Sleep fade-out ──
  function startSleepTimer(mins: number) {
    if (sleepTimerRef.current) clearTimeout(sleepTimerRef.current);
    if (sleepCountdownRef.current) { clearInterval(sleepCountdownRef.current); sleepCountdownRef.current = undefined; }
    setSleepTimer(mins);
    sleepEndRef.current = Date.now() + mins * 60000;
    setSleepRemaining(mins * 60);

    sleepCountdownRef.current = setInterval(() => {
      const remaining = Math.max(0, Math.round((sleepEndRef.current - Date.now()) / 1000));
      setSleepRemaining(remaining);
      // Fade out last 30 seconds
      if (remaining <= 30 && remaining > 0 && audioRef.current) {
        const fadeVol = volumeRef.current * (remaining / 30);
        audioRef.current.volume = Math.max(0.01, fadeVol);
      }
      if (remaining <= 0 && sleepCountdownRef.current) {
        clearInterval(sleepCountdownRef.current);
        sleepCountdownRef.current = undefined;
      }
    }, 1000);

    sleepTimerRef.current = setTimeout(() => {
      if (sleepCountdownRef.current) { clearInterval(sleepCountdownRef.current); sleepCountdownRef.current = undefined; }
      toast.info('⏰ 定时结束，已暂停');
      if (audioRef.current) { audioRef.current.pause(); audioRef.current.volume = volumeRef.current; }
      setPaused(true);
      setSleepTimer(0);
      setSleepRemaining(0);
    }, mins * 60000);
  }

  function cancelSleepTimer() {
    if (sleepTimerRef.current) { clearTimeout(sleepTimerRef.current); sleepTimerRef.current = undefined; }
    if (sleepCountdownRef.current) { clearInterval(sleepCountdownRef.current); sleepCountdownRef.current = undefined; }
    setSleepTimer(0);
    setSleepRemaining(0);
    // Restore volume
    if (audioRef.current) audioRef.current.volume = volumeRef.current;
  }

  return (
    <AudioCtx.Provider value={{
      playing, paused, loading, current, progress, positionSec, speed, voice, playlist, sleepTimer,
      voices: VOICES, autoContinue,
      playChapter, togglePause, stop, skipChapter, playRandom,
      addToPlaylist, removeFromPlaylist, clearPlaylist,
      changeVoice, changeSpeed, startSleepTimer, cancelSleepTimer, sleepAtChapterEnd, setSleepAtChapterEnd,
      getResume, getListened, isListened,
      addBookmark, removeBookmark, getBookmarks, getHistory,
      toggleAutoContinue, seekTo, skip15s, cycleSkip, skipSeconds, rewind30s, undoSkip, volume: volumeState, setVolume: setVolumeFn,
      playMode, cyclePlayMode, sleepRemaining, showRemaining, toggleTimeDisplay,
      ambient, setAmbient, ambientVolume, setAmbientVolume: setAmbientVolumeFn,
      music, setMusic, musicVolume, setMusicVolume: setMusicVolumeFn,
      sleepStory, toggleSleepStory, speedTrain, toggleSpeedTrain, speedTrainLevel,
      achievements: getAchievements(),
      radioMode, toggleRadioMode,
      dramaticMode, toggleDramaticMode,
      eqPreset, cycleEQ,
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
