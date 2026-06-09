/** 音频 — useAudio() 直接从 Zustand stores 读写。无需 Provider 包裹。 */
import { useEffect } from 'react';
import { useAudioStore, usePlaylistStore, useSettingsStore } from 'src/stores';
import type { PlaylistItem } from 'src/stores/playlistStore';
import type { ListenRecord } from 'src/stores/audioStore';

export type { PlaylistItem, ListenRecord };

export interface Bookmark {
  id: string; novelId: string; novelTitle: string;
  chapterNum: number; chapterTitle: string;
  position: number; note: string; tag: string; createdAt: number;
}

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

export interface AudioContextShape {
  playing: boolean; paused: boolean; loading: boolean;
  current: any; progress: number; positionSec: number;
  speed: number; voice: string; volume: number; skipSeconds: number; duration: number;
  voices: readonly any[]; playlist: any[]; playMode: string; cyclePlayMode: () => void;
  history: any[]; sleepTimer: number; sleepAtChapterEnd: boolean;
  sleepRemaining: number; showRemaining: boolean; autoContinue: boolean;
  ambient: string | null; ambientVolume: number; music: string | null;
  musicVolume: number; sleepStory: boolean; speedTrain: boolean;
  speedTrainLevel: number; radioMode: boolean; dramaticMode: boolean;
  eqPreset: string;
  playChapter: (item: any, seekTo?: number) => void;
  togglePause: () => void; stop: () => void;
  skipChapter: (dir: 1 | -1) => void; playRandom: () => void;
  changeVoice: (v: string) => void; changeSpeed: (s: number) => void;
  seekTo: (pct: number) => void; skip15s: (dir: 1 | -1) => void;
  cycleSkip: () => void; rewind30s: () => void; undoSkip: () => void;
  setVolume: (v: number) => void;
  addToPlaylist: (item: any) => void; removeFromPlaylist: (idx: number) => void;
  clearPlaylist: () => void; addToHistory: (item: any) => void;
  setSleepTimer: (mins: number) => void; setSleepRemaining: (s: number) => void;
  setSleepAtChapterEnd: (v: boolean) => void; toggleTimeDisplay: () => void;
  toggleAutoContinue: () => void; toggleSleepStory: () => void;
  toggleSpeedTrain: () => void; toggleRadioMode: () => void;
  toggleDramaticMode: () => void; setSpeedTrainLevel: (lvl: number) => void;
  cycleEQ: () => void; setAmbient: (a: string | null) => void;
  setAmbientVolume: (v: number) => void; setMusic: (m: string | null) => void;
  setMusicVolume: (v: number) => void;
  getResume: () => any; getListened: (novelId: string) => any[];
  isListened: (novelId: string, chapterNum: number) => any;
  addListenRecord: (novelId: string, chapterNum: number, status: 'done' | 'partial', position: number) => void;
  addBookmark: (note?: string) => void; removeBookmark: (id: string) => void;
  getBookmarks: () => any[]; getHistory: () => any[];
  achievements: any[]; startSleepTimer: (mins: number) => void;
  cancelSleepTimer: () => void;
}

// ── Server sync (once per app mount, via App.tsx) ──
let _syncInitialized = false;

function useServerSync() {
  const playlist = usePlaylistStore();
  useEffect(() => {
    if (_syncInitialized) return;
    _syncInitialized = true;

    fetch('/api/audio/data').then(r => r.json()).then(data => {
      if (data.playlist?.length && playlist.playlist.length === 0) {
        data.playlist.forEach((item: PlaylistItem) => playlist.addToPlaylist(item));
      }
    }).catch(() => {});

    const interval = setInterval(() => {
      fetch('/api/audio/sync', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ playlist: playlist.playlist, settings: {} }),
      }).catch(() => {});
    }, 30000);
    return () => clearInterval(interval);
  }, []);
}

/** useAudio — 直接从 Zustand stores 读取，无需 Provider 包裹。 */
export function useAudio(): AudioContextShape {
  const audio = useAudioStore();
  const playlist = usePlaylistStore();
  const settings = useSettingsStore();
  useServerSync();

  return {
    playing: audio.playing, paused: audio.paused, loading: audio.loading,
    current: audio.current, progress: audio.progress, positionSec: audio.positionSec,
    speed: audio.speed, voice: audio.voice, volume: audio.volume,
    skipSeconds: audio.skipSeconds, duration: audio.duration,
    voices: VOICES,
    playlist: playlist.playlist, playMode: playlist.playMode,
    cyclePlayMode: playlist.cyclePlayMode, history: playlist.history,
    sleepTimer: settings.sleepTimer, sleepAtChapterEnd: settings.sleepAtChapterEnd,
    sleepRemaining: settings.sleepRemaining, showRemaining: settings.showRemaining,
    autoContinue: settings.autoContinue, ambient: settings.ambient,
    ambientVolume: settings.ambientVolume, music: settings.music,
    musicVolume: settings.musicVolume, sleepStory: settings.sleepStory,
    speedTrain: settings.speedTrain, speedTrainLevel: settings.speedTrainLevel,
    radioMode: settings.radioMode, dramaticMode: settings.dramaticMode,
    eqPreset: settings.eqPreset,
    playChapter: audio.playChapter, togglePause: audio.togglePause,
    stop: audio.stop, skipChapter: audio.skipChapter, playRandom: audio.playRandom,
    changeVoice: audio.changeVoice, changeSpeed: audio.changeSpeed,
    seekTo: audio.seekTo, skip15s: audio.skip15s, cycleSkip: audio.cycleSkip,
    rewind30s: audio.rewind30s, undoSkip: audio.undoSkip, setVolume: audio.setVolume,
    addToPlaylist: playlist.addToPlaylist, removeFromPlaylist: playlist.removeFromPlaylist,
    clearPlaylist: playlist.clearPlaylist, addToHistory: playlist.addToHistory,
    setSleepTimer: settings.setSleepTimer, setSleepRemaining: settings.setSleepRemaining,
    setSleepAtChapterEnd: settings.setSleepAtChapterEnd, toggleTimeDisplay: settings.toggleTimeDisplay,
    toggleAutoContinue: settings.toggleAutoContinue, toggleSleepStory: settings.toggleSleepStory,
    toggleSpeedTrain: settings.toggleSpeedTrain, toggleRadioMode: settings.toggleRadioMode,
    toggleDramaticMode: settings.toggleDramaticMode, setSpeedTrainLevel: settings.setSpeedTrainLevel,
    cycleEQ: settings.cycleEQ, setAmbient: settings.setAmbient,
    setAmbientVolume: settings.setAmbientVolume, setMusic: settings.setMusic,
    setMusicVolume: settings.setMusicVolume,
    getResume: audio.getResume, getListened: audio.getListenRecords,
    isListened: audio.isListened, addListenRecord: audio.addListenRecord,
    addBookmark: () => {}, removeBookmark: () => {}, getBookmarks: () => [],
    getHistory: () => playlist.history.map((item, i) => ({ ...item, idx: i })),
    achievements: [], startSleepTimer: settings.setSleepTimer,
    cancelSleepTimer: () => { settings.setSleepTimer(0); settings.setSleepRemaining(0); },
  };
}

// ── Backward compat: keep Provider as no-op (App.tsx still imports it) ──
export function AudioProvider({ children }: { children: React.ReactNode }) {
  return children as any;
}
