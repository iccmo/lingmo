/** 播放列表 + 播放模式 */
import { create } from 'zustand';

export interface PlaylistItem {
  novelId: string;
  novelTitle: string;
  chapterNum: number;
  chapterTitle: string;
}

export interface PlaylistState {
  playlist: PlaylistItem[];
  playMode: 'sequential' | 'shuffle' | 'repeat-one';
  history: PlaylistItem[];

  addToPlaylist: (item: PlaylistItem) => void;
  removeFromPlaylist: (idx: number) => void;
  clearPlaylist: () => void;
  cyclePlayMode: () => void;
  addToHistory: (item: PlaylistItem) => void;
}

const MODES: PlaylistState['playMode'][] = ['sequential', 'shuffle', 'repeat-one'];

export const usePlaylistStore = create<PlaylistState>((set) => ({
  playlist: [],
  playMode: 'sequential' as const,
  history: [],

  addToPlaylist: (item) => set((s) => {
    const exists = s.playlist.some(
      (p) => p.novelId === item.novelId && p.chapterNum === item.chapterNum);
    if (exists) return s;
    return { playlist: [...s.playlist, item] };
  }),

  removeFromPlaylist: (idx) => set((s) => ({
    playlist: s.playlist.filter((_, i) => i !== idx),
  })),

  clearPlaylist: () => set({ playlist: [] }),

  cyclePlayMode: () => set((s) => {
    const idx = MODES.indexOf(s.playMode);
    return { playMode: MODES[(idx + 1) % MODES.length] };
  }),

  addToHistory: (item) => set((s) => ({
    history: [...s.history.slice(-99), item],
  })),
}));
