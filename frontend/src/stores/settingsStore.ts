/** 音频设置 — 不触发音频重新加载的偏好项 */
import { create } from 'zustand';

export interface SettingsState {
  // Sleep
  sleepTimer: number;
  sleepAtChapterEnd: boolean;
  sleepRemaining: number;
  showRemaining: boolean;

  // Ambient / Music
  ambient: string | null;
  ambientVolume: number;
  music: string | null;
  musicVolume: number;

  // Modes
  autoContinue: boolean;
  sleepStory: boolean;
  speedTrain: boolean;
  speedTrainLevel: number;
  radioMode: boolean;
  dramaticMode: boolean;
  eqPreset: 'flat' | 'voice' | 'bass';

  // Actions
  setSleepTimer: (mins: number) => void;
  setSleepRemaining: (s: number) => void;
  setSleepAtChapterEnd: (v: boolean) => void;
  toggleTimeDisplay: () => void;
  toggleAutoContinue: () => void;
  toggleSleepStory: () => void;
  toggleSpeedTrain: () => void;
  toggleRadioMode: () => void;
  toggleDramaticMode: () => void;
  setSpeedTrainLevel: (lvl: number) => void;
  cycleEQ: () => void;
  setAmbient: (a: string | null) => void;
  setAmbientVolume: (v: number) => void;
  setMusic: (m: string | null) => void;
  setMusicVolume: (v: number) => void;
}

const EQ_PRESETS: SettingsState['eqPreset'][] = ['flat', 'voice', 'bass'];

export const useSettingsStore = create<SettingsState>((set) => ({
  sleepTimer: 0,
  sleepAtChapterEnd: false,
  sleepRemaining: 0,
  showRemaining: false,

  ambient: null,
  ambientVolume: 0.3,
  music: null,
  musicVolume: 0.3,

  autoContinue: true,
  sleepStory: false,
  speedTrain: false,
  speedTrainLevel: 0,
  radioMode: false,
  dramaticMode: false,
  eqPreset: 'flat' as const,

  setSleepTimer: (mins) => set({ sleepTimer: mins }),
  setSleepRemaining: (s) => set({ sleepRemaining: s }),
  setSleepAtChapterEnd: (v) => set({ sleepAtChapterEnd: v }),
  toggleTimeDisplay: () => set((s) => ({ showRemaining: !s.showRemaining })),
  toggleAutoContinue: () => set((s) => ({ autoContinue: !s.autoContinue })),
  toggleSleepStory: () => set((s) => ({ sleepStory: !s.sleepStory })),
  toggleSpeedTrain: () => set((s) => ({ speedTrain: !s.speedTrain })),
  toggleRadioMode: () => set((s) => ({ radioMode: !s.radioMode })),
  toggleDramaticMode: () => set((s) => ({ dramaticMode: !s.dramaticMode })),
  setSpeedTrainLevel: (lvl) => set({ speedTrainLevel: lvl }),
  cycleEQ: () => set((s) => {
    const idx = EQ_PRESETS.indexOf(s.eqPreset);
    return { eqPreset: EQ_PRESETS[(idx + 1) % EQ_PRESETS.length] };
  }),
  setAmbient: (a) => set({ ambient: a }),
  setAmbientVolume: (v) => set({ ambientVolume: v }),
  setMusic: (m) => set({ music: m }),
  setMusicVolume: (v) => set({ musicVolume: v }),
}));
