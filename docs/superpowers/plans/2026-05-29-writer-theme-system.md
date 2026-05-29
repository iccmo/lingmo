# Writer Theme System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a modular theme system with warm brown color scheme and writing efficiency tools for web novel authors.

**Architecture:** CSS variables driven by TypeScript theme objects. Theme values injected into `:root` via `applyTheme()`. Tailwind v4 uses `@theme` to reference CSS variables. New components: WritingStatsBar, FocusTimer, ThemeSwitcher, useFocusMode hook.

**Tech Stack:** React 18, TypeScript, Tailwind CSS v4, Lucide icons, class-variance-authority

---

## File Structure

```
frontend/src/
  themes/
    types.ts            # Theme interface definition
    index.ts            # Theme registry and exports
    apply.ts            # applyTheme() - injects CSS variables
    warm-brown.ts       # Deep warm brown theme (default)
  hooks/
    useTheme.ts         # Theme state management hook
    useFocusMode.ts     # Immersive focus mode hook
    useWritingStats.ts  # Writing statistics hook
  components/
    writing/
      WritingStatsBar.tsx   # Floating word count / speed / target
      FocusTimer.tsx        # Pomodoro timer component
      ThemeSwitcher.tsx     # Theme picker with color preview
    layout/
      Sidebar.tsx           # Modify: use theme colors
      Header.tsx            # Modify: add FocusTimer + ThemeSwitcher
```

---

### Task 1: Create Theme Types

**Files:**
- Create: `frontend/src/themes/types.ts`

- [ ] **Step 1: Create theme type definitions**

```typescript
// frontend/src/themes/types.ts

export interface ThemeColors {
  bg: {
    base: string;
    surface: string;
    raised: string;
    overlay: string;
  };
  text: {
    primary: string;
    secondary: string;
    muted: string;
    inverse: string;
  };
  brand: {
    primary: string;
    primaryHover: string;
    secondary: string;
    accent: string;
  };
  semantic: {
    success: string;
    warning: string;
    error: string;
    info: string;
  };
  border: {
    default: string;
    strong: string;
    subtle: string;
  };
}

export interface ThemeTypography {
  heading: string;
  body: string;
  mono: string;
  editor: {
    fontFamily: string;
    fontSize: string;
    lineHeight: string;
    letterSpacing: string;
  };
}

export interface ThemeSpacing {
  radius: {
    sm: string;
    md: string;
    lg: string;
  };
}

export interface ThemeEffects {
  shadow: string;
  glass: string;
  glow: string;
}

export interface Theme {
  id: string;
  name: string;
  description: string;
  colors: ThemeColors;
  typography: ThemeTypography;
  spacing: ThemeSpacing;
  effects: ThemeEffects;
}
```

- [ ] **Step 2: Verify file compiles**

Run: `cd /Users/z/CodeBuddy/wechat/frontend && npx tsc --noEmit src/themes/types.ts`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/themes/types.ts
git commit -m "feat(theme): add theme type definitions"
```

---

### Task 2: Create Warm Brown Theme

**Files:**
- Create: `frontend/src/themes/warm-brown.ts`

- [ ] **Step 1: Define warm brown theme values**

```typescript
// frontend/src/themes/warm-brown.ts
import type { Theme } from './types';

export const warmBrownTheme: Theme = {
  id: 'warm-brown',
  name: '墨韵暖棕',
  description: '深夜书房，护眼柔和，文学氛围',

  colors: {
    bg: {
      base: '#1E1B18',
      surface: '#2A2520',
      raised: '#332E28',
      overlay: '#3D3730',
    },
    text: {
      primary: '#F5F0E8',
      secondary: '#C4B8A8',
      muted: '#8A7E70',
      inverse: '#1E1B18',
    },
    brand: {
      primary: '#D4A574',
      primaryHover: '#E0B88A',
      secondary: '#8B7355',
      accent: '#E8C49A',
    },
    semantic: {
      success: '#7C9A6B',
      warning: '#D4A574',
      error: '#C47A6B',
      info: '#7A8B9A',
    },
    border: {
      default: 'rgba(245, 240, 232, 0.1)',
      strong: 'rgba(245, 240, 232, 0.2)',
      subtle: 'rgba(245, 240, 232, 0.05)',
    },
  },

  typography: {
    heading: "'Noto Serif SC', Georgia, serif",
    body: "'Inter', 'Noto Sans SC', sans-serif",
    mono: "'JetBrains Mono', monospace",
    editor: {
      fontFamily: "'Noto Serif SC', serif",
      fontSize: '16px',
      lineHeight: '1.8',
      letterSpacing: '0.02em',
    },
  },

  spacing: {
    radius: { sm: '6px', md: '8px', lg: '12px' },
  },

  effects: {
    shadow: '0 4px 12px rgba(0, 0, 0, 0.3)',
    glass: 'rgba(42, 37, 32, 0.8) backdrop-blur(20px)',
    glow: '0 0 20px rgba(212, 165, 116, 0.15)',
  },
};
```

- [ ] **Step 2: Verify file compiles**

Run: `cd /Users/z/CodeBuddy/wechat/frontend && npx tsc --noEmit src/themes/warm-brown.ts`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/themes/warm-brown.ts
git commit -m "feat(theme): add warm brown theme values"
```

---

### Task 3: Create Theme Registry and Apply Function

**Files:**
- Create: `frontend/src/themes/apply.ts`
- Create: `frontend/src/themes/index.ts`

- [ ] **Step 1: Create applyTheme function**

```typescript
// frontend/src/themes/apply.ts
import type { Theme } from './types';

export function applyTheme(theme: Theme): void {
  const root = document.documentElement;

  // Background colors
  root.style.setProperty('--bg-base', theme.colors.bg.base);
  root.style.setProperty('--bg-surface', theme.colors.bg.surface);
  root.style.setProperty('--bg-raised', theme.colors.bg.raised);
  root.style.setProperty('--bg-overlay', theme.colors.bg.overlay);

  // Text colors
  root.style.setProperty('--text-primary', theme.colors.text.primary);
  root.style.setProperty('--text-secondary', theme.colors.text.secondary);
  root.style.setProperty('--text-muted', theme.colors.text.muted);
  root.style.setProperty('--text-inverse', theme.colors.text.inverse);

  // Brand colors
  root.style.setProperty('--brand-primary', theme.colors.brand.primary);
  root.style.setProperty('--brand-primary-hover', theme.colors.brand.primaryHover);
  root.style.setProperty('--brand-secondary', theme.colors.brand.secondary);
  root.style.setProperty('--brand-accent', theme.colors.brand.accent);

  // Semantic colors
  root.style.setProperty('--semantic-success', theme.colors.semantic.success);
  root.style.setProperty('--semantic-warning', theme.colors.semantic.warning);
  root.style.setProperty('--semantic-error', theme.colors.semantic.error);
  root.style.setProperty('--semantic-info', theme.colors.semantic.info);

  // Border colors
  root.style.setProperty('--border-default', theme.colors.border.default);
  root.style.setProperty('--border-strong', theme.colors.border.strong);
  root.style.setProperty('--border-subtle', theme.colors.border.subtle);

  // Typography
  root.style.setProperty('--font-heading', theme.typography.heading);
  root.style.setProperty('--font-body', theme.typography.body);
  root.style.setProperty('--font-mono', theme.typography.mono);
  root.style.setProperty('--font-editor', theme.typography.editor.fontFamily);
  root.style.setProperty('--font-editor-size', theme.typography.editor.fontSize);
  root.style.setProperty('--font-editor-line-height', theme.typography.editor.lineHeight);

  // Spacing
  root.style.setProperty('--radius-sm', theme.spacing.radius.sm);
  root.style.setProperty('--radius-md', theme.spacing.radius.md);
  root.style.setProperty('--radius-lg', theme.spacing.radius.lg);

  // Effects
  root.style.setProperty('--shadow', theme.effects.shadow);
  root.style.setProperty('--glow', theme.effects.glow);

  // Save preference
  localStorage.setItem('lingmo-theme', theme.id);
}
```

- [ ] **Step 2: Create theme registry**

```typescript
// frontend/src/themes/index.ts
import type { Theme } from './types';
import { warmBrownTheme } from './warm-brown';

export const themes: Theme[] = [
  warmBrownTheme,
];

export const defaultTheme = warmBrownTheme;

export function getThemeById(id: string): Theme | undefined {
  return themes.find(t => t.id === id);
}

export type { Theme } from './types';
```

- [ ] **Step 3: Verify files compile**

Run: `cd /Users/z/CodeBuddy/wechat/frontend && npx tsc --noEmit src/themes/`
Expected: No errors

- [ ] **Step 4: Commit**

```bash
git add frontend/src/themes/
git commit -m "feat(theme): add theme registry and apply function"
```

---

### Task 4: Create useTheme Hook

**Files:**
- Create: `frontend/src/hooks/useTheme.ts`

- [ ] **Step 1: Create theme hook**

```typescript
// frontend/src/hooks/useTheme.ts
import { useState, useEffect, useCallback } from 'react';
import type { Theme } from 'src/themes/types';
import { themes, defaultTheme, getThemeById } from 'src/themes';
import { applyTheme } from 'src/themes/apply';

export function useTheme() {
  const [currentTheme, setCurrentTheme] = useState<Theme>(() => {
    const saved = localStorage.getItem('lingmo-theme');
    if (saved) {
      const found = getThemeById(saved);
      if (found) return found;
    }
    return defaultTheme;
  });

  useEffect(() => {
    applyTheme(currentTheme);
  }, [currentTheme]);

  const setTheme = useCallback((theme: Theme) => {
    setCurrentTheme(theme);
  }, []);

  return {
    currentTheme,
    themes,
    setTheme,
  };
}
```

- [ ] **Step 2: Verify file compiles**

Run: `cd /Users/z/CodeBuddy/wechat/frontend && npx tsc --noEmit src/hooks/useTheme.ts`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/hooks/useTheme.ts
git commit -m "feat(theme): add useTheme hook"
```

---

### Task 5: Update CSS Variables for Warm Brown Theme

**Files:**
- Modify: `frontend/src/index.css`

- [ ] **Step 1: Update @theme section with warm brown variables**

Replace the `@theme` section in `index.css`:

```css
@theme {
  --font-heading: "Noto Serif SC", Georgia, serif;
  --font-editor: "Noto Serif SC", "KaiTi", "STKaiti", serif;
  --font-ui: Inter, "Noto Sans SC", -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;

  /* Brand — warm brown / bronze */
  --color-accent: #D4A574;
  --color-accent-hover: #E0B88A;
  --color-accent-soft: rgba(212, 165, 116, 0.12);
  --color-secondary: #8B7355;
  --color-secondary-soft: rgba(139, 115, 85, 0.12);

  /* Surface (dark default) */
  --color-paper: #1E1B18;
  --color-surface: #2A2520;
  --color-surface-hover: #332E28;
  --color-surface-raised: #3D3730;

  /* Card */
  --color-card: #2A2520;

  /* Text */
  --color-ink: #F5F0E8;
  --color-ink-muted: #C4B8A8;
  --color-ink-subtle: #8A7E70;

  /* Semantic */
  --color-success: #7C9A6B;
  --color-success-soft: rgba(124, 154, 107, 0.12);
  --color-warn: #D4A574;
  --color-warn-soft: rgba(212, 165, 116, 0.12);
  --color-destructive: #C47A6B;
  --color-destructive-soft: rgba(196, 122, 107, 0.12);
  --color-info: #7A8B9A;
  --color-info-soft: rgba(122, 139, 154, 0.12);
}
```

- [ ] **Step 2: Update dark theme variables**

Update the `html.dark` section:

```css
html.dark {
  --background: #1E1B18; --foreground: #F5F0E8;
  --card: #2A2520; --card-foreground: #F5F0E8;
  --radius: 12px;
  --primary: #D4A574; --primary-foreground: #1E1B18;
  --secondary: #3D3730; --secondary-foreground: #E8C49A;
  --muted: #2A2520; --muted-foreground: #C4B8A8;
  --accent: #D4A574; --accent-foreground: #1E1B18;
  --border: rgba(245, 240, 232, 0.1); --input: rgba(245, 240, 232, 0.1); --ring: #D4A574;
  --color-paper: #1E1B18;
  --color-card: #2A2520;
  --color-surface: #2A2520;
  --color-surface-hover: #332E28;
  --color-ink: #F5F0E8;
  --color-ink-muted: #C4B8A8;
  --color-ink-subtle: #8A7E70;
  --color-accent: #D4A574;
  --color-accent-soft: rgba(212, 165, 116, 0.12);
  --color-accent-hover: #E0B88A;
  --color-success: #7C9A6B;
  --color-success-soft: rgba(124, 154, 107, 0.12);
  --color-warn: #D4A574;
  --color-warn-soft: rgba(212, 165, 116, 0.12);
}
```

- [ ] **Step 3: Update light theme variables**

Update the `:root` section:

```css
:root {
  --background: #FFFBF5; --foreground: #1E1B18;
  --card: #FFFFFF; --card-foreground: #1E1B18;
  --primary: #8B7355; --primary-foreground: #FFFFFF;
  --secondary: #F5F0E8; --secondary-foreground: #1E1B18;
  --muted: #F5F0E8; --muted-foreground: #8A7E70;
  --accent: #D4A574; --accent-foreground: #FFFFFF;
  --border: #E7D9C8; --input: #E7D9C8; --ring: #D4A574;
  --color-paper: #FFFBF5;
  --color-card: #FFFFFF;
  --color-ink: #1E1B18;
  --color-ink-muted: #8A7E70;
  --color-ink-subtle: #C4B8A8;
  --color-accent: #D4A574;
  --color-accent-hover: #8B7355;
  --color-accent-soft: rgba(212, 165, 116, 0.1);
  --color-success: #5A7A4B;
  --color-success-soft: #ECFDF5;
  --color-warn: #B45309;
  --color-warn-soft: #FFFBEB;
  color-scheme: light;
}
```

- [ ] **Step 4: Verify CSS is valid**

Run: `cd /Users/z/CodeBuddy/wechat/frontend && npx vite build --mode development 2>&1 | head -20`
Expected: No CSS errors

- [ ] **Step 5: Commit**

```bash
git add frontend/src/index.css
git commit -m "style(theme): update CSS variables to warm brown palette"
```

---

### Task 6: Create useWritingStats Hook

**Files:**
- Create: `frontend/src/hooks/useWritingStats.ts`

- [ ] **Step 1: Create writing stats hook**

```typescript
// frontend/src/hooks/useWritingStats.ts
import { useState, useEffect, useRef, useCallback } from 'react';

export interface WritingStats {
  currentWords: number;
  wordsPerHour: number;
  dailyTarget: number;
  dailyProgress: number;
  sessionDuration: number; // minutes
}

export function useWritingStats(target: number = 5000) {
  const [stats, setStats] = useState<WritingStats>({
    currentWords: 0,
    wordsPerHour: 0,
    dailyTarget: target,
    dailyProgress: 0,
    sessionDuration: 0,
  });

  const sessionStart = useRef<number>(Date.now());
  const wordHistory = useRef<{ time: number; words: number }[]>([]);

  const updateWords = useCallback((words: number) => {
    const now = Date.now();
    wordHistory.current.push({ time: now, words });

    // Keep only last hour of data
    const oneHourAgo = now - 3600000;
    wordHistory.current = wordHistory.current.filter(h => h.time > oneHourAgo);

    // Calculate words per hour
    let wordsPerHour = 0;
    if (wordHistory.current.length >= 2) {
      const first = wordHistory.current[0];
      const last = wordHistory.current[wordHistory.current.length - 1];
      const timeDiffHours = (last.time - first.time) / 3600000;
      if (timeDiffHours > 0) {
        wordsPerHour = Math.round((last.words - first.words) / timeDiffHours);
      }
    }

    // Calculate session duration
    const sessionDuration = Math.round((now - sessionStart.current) / 60000);

    // Load daily progress from localStorage
    const today = new Date().toISOString().split('T')[0];
    const savedProgress = localStorage.getItem(`writing-progress-${today}`);
    const dailyProgress = savedProgress ? parseInt(savedProgress, 10) : words;

    setStats({
      currentWords: words,
      wordsPerHour: Math.max(0, wordsPerHour),
      dailyTarget: target,
      dailyProgress,
      sessionDuration,
    });
  }, [target]);

  const setDailyTarget = useCallback((newTarget: number) => {
    setStats(prev => ({ ...prev, dailyTarget: newTarget }));
    localStorage.setItem('writing-target', String(newTarget));
  }, []);

  // Load saved target on mount
  useEffect(() => {
    const savedTarget = localStorage.getItem('writing-target');
    if (savedTarget) {
      setStats(prev => ({ ...prev, dailyTarget: parseInt(savedTarget, 10) }));
    }
  }, []);

  return { stats, updateWords, setDailyTarget };
}
```

- [ ] **Step 2: Verify file compiles**

Run: `cd /Users/z/CodeBuddy/wechat/frontend && npx tsc --noEmit src/hooks/useWritingStats.ts`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/hooks/useWritingStats.ts
git commit -m "feat(writing): add useWritingStats hook"
```

---

### Task 7: Create WritingStatsBar Component

**Files:**
- Create: `frontend/src/components/writing/WritingStatsBar.tsx`

- [ ] **Step 1: Create WritingStatsBar component**

```typescript
// frontend/src/components/writing/WritingStatsBar.tsx
import { BarChart3, Target, Clock } from 'lucide-react';
import type { WritingStats } from 'src/hooks/useWritingStats';

interface Props {
  stats: WritingStats;
  className?: string;
}

export function WritingStatsBar({ stats, className = '' }: Props) {
  const progress = stats.dailyTarget > 0
    ? Math.min((stats.dailyProgress / stats.dailyTarget) * 100, 100)
    : 0;

  return (
    <div className={`
      fixed bottom-4 left-1/2 -translate-x-1/2 z-50
      bg-bg-surface/80 backdrop-blur-sm
      border border-border-default rounded-lg
      px-6 py-3 shadow-default
      ${className}
    `}>
      <div className="flex items-center gap-6 text-sm">
        <div className="flex items-center gap-2">
          <BarChart3 size={14} className="text-text-muted" />
          <span className="text-text-muted">字数</span>
          <span className="text-text-primary font-mono">
            {stats.currentWords.toLocaleString()}
          </span>
        </div>

        <div className="flex items-center gap-2">
          <Target size={14} className="text-text-muted" />
          <span className="text-text-muted">速度</span>
          <span className="text-text-primary font-mono">
            {stats.wordsPerHour.toLocaleString()}字/时
          </span>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-text-muted">目标</span>
          <div className="w-24 h-2 bg-bg-raised rounded-full overflow-hidden">
            <div
              className="h-full bg-brand-primary transition-all duration-300"
              style={{ width: `${progress}%` }}
            />
          </div>
          <span className="text-text-primary font-mono text-xs">
            {Math.round(progress)}%
          </span>
        </div>

        {stats.sessionDuration > 0 && (
          <div className="flex items-center gap-2">
            <Clock size={14} className="text-text-muted" />
            <span className="text-text-muted">时长</span>
            <span className="text-text-primary font-mono">
              {stats.sessionDuration}分钟
            </span>
          </div>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verify file compiles**

Run: `cd /Users/z/CodeBuddy/wechat/frontend && npx tsc --noEmit src/components/writing/WritingStatsBar.tsx`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/writing/WritingStatsBar.tsx
git commit -m "feat(writing): add WritingStatsBar component"
```

---

### Task 8: Create FocusTimer Component

**Files:**
- Create: `frontend/src/components/writing/FocusTimer.tsx`

- [ ] **Step 1: Create FocusTimer component**

```typescript
// frontend/src/components/writing/FocusTimer.tsx
import { useState, useEffect, useCallback } from 'react';
import { Play, Pause, RotateCcw, Settings } from 'lucide-react';

type TimerMode = 'pomodoro' | 'custom' | 'idle';

interface TimerState {
  mode: TimerMode;
  duration: number; // seconds
  remaining: number;
  isRunning: boolean;
  isBreak: boolean;
}

const POMODORO_WORK = 25 * 60;
const POMODORO_BREAK = 5 * 60;

export function FocusTimer() {
  const [state, setState] = useState<TimerState>({
    mode: 'idle',
    duration: POMODORO_WORK,
    remaining: POMODORO_WORK,
    isRunning: false,
    isBreak: false,
  });

  const [showSettings, setShowSettings] = useState(false);
  const [customMinutes, setCustomMinutes] = useState(30);

  // Timer countdown
  useEffect(() => {
    if (!state.isRunning) return;

    const interval = setInterval(() => {
      setState(prev => {
        if (prev.remaining <= 1) {
          // Timer completed
          const isBreak = !prev.isBreak;
          const duration = isBreak ? POMODORO_BREAK : POMODORO_WORK;

          // Play notification sound or show notification
          if ('Notification' in window && Notification.permission === 'granted') {
            new Notification(isBreak ? '休息时间到！' : '专注时间到！', {
              body: isBreak ? '休息 5 分钟' : '开始新的专注',
            });
          }

          return {
            ...prev,
            remaining: duration,
            duration,
            isBreak,
            isRunning: false,
          };
        }
        return { ...prev, remaining: prev.remaining - 1 };
      });
    }, 1000);

    return () => clearInterval(interval);
  }, [state.isRunning]);

  const toggleTimer = useCallback(() => {
    setState(prev => ({ ...prev, isRunning: !prev.isRunning }));
  }, []);

  const resetTimer = useCallback(() => {
    setState({
      mode: 'idle',
      duration: POMODORO_WORK,
      remaining: POMODORO_WORK,
      isRunning: false,
      isBreak: false,
    });
  }, []);

  const startPomodoro = useCallback(() => {
    setState({
      mode: 'pomodoro',
      duration: POMODORO_WORK,
      remaining: POMODORO_WORK,
      isRunning: true,
      isBreak: false,
    });
  }, []);

  const startCustom = useCallback(() => {
    const duration = customMinutes * 60;
    setState({
      mode: 'custom',
      duration,
      remaining: duration,
      isRunning: true,
      isBreak: false,
    });
    setShowSettings(false);
  }, [customMinutes]);

  const progress = 1 - (state.remaining / state.duration);
  const minutes = Math.floor(state.remaining / 60);
  const seconds = state.remaining % 60;

  if (state.mode === 'idle') {
    return (
      <div className="flex items-center gap-2">
        <button
          onClick={startPomodoro}
          className="flex items-center gap-1.5 px-3 py-1.5 text-sm
                     bg-brand-primary text-text-inverse rounded-md
                     hover:bg-brand-primary-hover transition-colors"
        >
          <Play size={14} />
          番茄钟
        </button>

        <div className="relative">
          <button
            onClick={() => setShowSettings(!showSettings)}
            className="p-1.5 text-text-muted hover:text-text-primary
                       hover:bg-bg-surface rounded-md transition-colors"
          >
            <Settings size={14} />
          </button>

          {showSettings && (
            <div className="absolute right-0 top-full mt-2 p-3 bg-bg-surface
                            border border-border-default rounded-lg shadow-default z-50">
              <p className="text-xs text-text-muted mb-2">自定义时长（分钟）</p>
              <div className="flex items-center gap-2">
                <input
                  type="number"
                  value={customMinutes}
                  onChange={e => setCustomMinutes(Number(e.target.value))}
                  min={1}
                  max={120}
                  className="w-16 px-2 py-1 text-sm bg-bg-raised border border-border-default
                             rounded text-text-primary"
                />
                <button
                  onClick={startCustom}
                  className="px-3 py-1 text-sm bg-brand-primary text-text-inverse
                             rounded hover:bg-brand-primary-hover transition-colors"
                >
                  开始
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-3">
      {/* Progress ring */}
      <div className="relative w-10 h-10">
        <svg className="w-full h-full -rotate-90" viewBox="0 0 40 40">
          <circle
            cx="20" cy="20" r="16"
            fill="none"
            stroke="var(--bg-raised)"
            strokeWidth="3"
          />
          <circle
            cx="20" cy="20" r="16"
            fill="none"
            stroke={state.isBreak ? 'var(--semantic-success)' : 'var(--brand-primary)'}
            strokeWidth="3"
            strokeDasharray={`${progress * 100} 100`}
            strokeLinecap="round"
            className="transition-all duration-1000"
          />
        </svg>
        <span className="absolute inset-0 flex items-center justify-center
                         text-xs font-mono text-text-primary">
          {minutes}:{seconds.toString().padStart(2, '0')}
        </span>
      </div>

      {/* Status label */}
      <span className="text-xs text-text-muted">
        {state.isBreak ? '休息中' : '专注中'}
      </span>

      {/* Controls */}
      <button
        onClick={toggleTimer}
        className="p-1.5 text-text-muted hover:text-text-primary
                   hover:bg-bg-surface rounded-md transition-colors"
      >
        {state.isRunning ? <Pause size={14} /> : <Play size={14} />}
      </button>

      <button
        onClick={resetTimer}
        className="p-1.5 text-text-muted hover:text-text-primary
                   hover:bg-bg-surface rounded-md transition-colors"
      >
        <RotateCcw size={14} />
      </button>
    </div>
  );
}
```

- [ ] **Step 2: Verify file compiles**

Run: `cd /Users/z/CodeBuddy/wechat/frontend && npx tsc --noEmit src/components/writing/FocusTimer.tsx`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/writing/FocusTimer.tsx
git commit -m "feat(writing): add FocusTimer component"
```

---

### Task 9: Create ThemeSwitcher Component

**Files:**
- Create: `frontend/src/components/writing/ThemeSwitcher.tsx`

- [ ] **Step 1: Create ThemeSwitcher component**

```typescript
// frontend/src/components/writing/ThemeSwitcher.tsx
import { Palette, Check } from 'lucide-react';
import { useTheme } from 'src/hooks/useTheme';

interface Props {
  compact?: boolean;
}

export function ThemeSwitcher({ compact = false }: Props) {
  const { currentTheme, themes, setTheme } = useTheme();

  if (compact) {
    return (
      <div className="flex items-center gap-1">
        {themes.map(theme => (
          <button
            key={theme.id}
            onClick={() => setTheme(theme)}
            className={`
              w-6 h-6 rounded-full border-2 transition-all
              ${currentTheme.id === theme.id
                ? 'border-brand-primary scale-110'
                : 'border-border-default hover:border-border-strong'}
            `}
            style={{ background: theme.colors.brand.primary }}
            title={theme.name}
          />
        ))}
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 text-text-primary">
        <Palette size={16} />
        <span className="font-medium">主题</span>
      </div>

      <div className="grid grid-cols-1 gap-2">
        {themes.map(theme => (
          <button
            key={theme.id}
            onClick={() => setTheme(theme)}
            className={`
              flex items-center gap-3 p-3 rounded-lg border-2 transition-all text-left
              ${currentTheme.id === theme.id
                ? 'border-brand-primary bg-brand-accent/10'
                : 'border-border-default hover:border-border-strong hover:bg-bg-surface'}
            `}
          >
            {/* Color preview */}
            <div className="flex gap-1 shrink-0">
              <div
                className="w-5 h-5 rounded"
                style={{ background: theme.colors.bg.base }}
              />
              <div
                className="w-5 h-5 rounded"
                style={{ background: theme.colors.bg.surface }}
              />
              <div
                className="w-5 h-5 rounded"
                style={{ background: theme.colors.brand.primary }}
              />
            </div>

            {/* Theme info */}
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-text-primary">
                {theme.name}
              </p>
              <p className="text-xs text-text-muted truncate">
                {theme.description}
              </p>
            </div>

            {/* Selected indicator */}
            {currentTheme.id === theme.id && (
              <Check size={16} className="text-brand-primary shrink-0" />
            )}
          </button>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verify file compiles**

Run: `cd /Users/z/CodeBuddy/wechat/frontend && npx tsc --noEmit src/components/writing/ThemeSwitcher.tsx`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/writing/ThemeSwitcher.tsx
git commit -m "feat(theme): add ThemeSwitcher component"
```

---

### Task 10: Create useFocusMode Hook

**Files:**
- Create: `frontend/src/hooks/useFocusMode.ts`

- [ ] **Step 1: Create focus mode hook**

```typescript
// frontend/src/hooks/useFocusMode.ts
import { useState, useEffect, useCallback } from 'react';

export function useFocusMode() {
  const [isFocused, setIsFocused] = useState(false);

  const enterFocus = useCallback(() => {
    setIsFocused(true);
    document.body.classList.add('focus-mode');
  }, []);

  const exitFocus = useCallback(() => {
    setIsFocused(false);
    document.body.classList.remove('focus-mode');
  }, []);

  const toggleFocus = useCallback(() => {
    if (isFocused) {
      exitFocus();
    } else {
      enterFocus();
    }
  }, [isFocused, enterFocus, exitFocus]);

  // Keyboard shortcuts
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'F11') {
        e.preventDefault();
        toggleFocus();
      }
      if (e.key === 'Escape' && isFocused) {
        exitFocus();
      }
    };

    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [isFocused, toggleFocus, exitFocus]);

  return {
    isFocused,
    enterFocus,
    exitFocus,
    toggleFocus,
  };
}
```

- [ ] **Step 2: Add focus mode CSS**

Add to `frontend/src/index.css`:

```css
/* Focus mode */
body.focus-mode .sidebar,
body.focus-mode .header-nav {
  display: none;
}

body.focus-mode main {
  max-width: 900px;
  margin: 0 auto;
  padding: 2rem;
}

body.focus-mode {
  overflow: hidden;
}
```

- [ ] **Step 3: Verify file compiles**

Run: `cd /Users/z/CodeBuddy/wechat/frontend && npx tsc --noEmit src/hooks/useFocusMode.ts`
Expected: No errors

- [ ] **Step 4: Commit**

```bash
git add frontend/src/hooks/useFocusMode.ts frontend/src/index.css
git commit -m "feat(writing): add useFocusMode hook with CSS"
```

---

### Task 11: Integrate Components into Header

**Files:**
- Modify: `frontend/src/components/layout/Header.tsx`

- [ ] **Step 1: Read current Header component**

Read `frontend/src/components/layout/Header.tsx` to understand current structure.

- [ ] **Step 2: Add FocusTimer and ThemeSwitcher to Header**

Add imports and integrate components into the Header toolbar area.

- [ ] **Step 3: Verify integration**

Run: `cd /Users/z/CodeBuddy/wechat/frontend && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/layout/Header.tsx
git commit -m "feat(writing): integrate FocusTimer and ThemeSwitcher into Header"
```

---

### Task 12: Integrate WritingStatsBar into WriterView

**Files:**
- Modify: `frontend/src/pages/WriterView.tsx`

- [ ] **Step 1: Read current WriterView component**

Read `frontend/src/pages/WriterView.tsx` to understand current structure.

- [ ] **Step 2: Add WritingStatsBar integration**

Import and use `useWritingStats` and `WritingStatsBar` in the WriterView.

- [ ] **Step 3: Verify integration**

Run: `cd /Users/z/CodeBuddy/wechat/frontend && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/WriterView.tsx
git commit -m "feat(writing): integrate WritingStatsBar into WriterView"
```

---

### Task 13: Add Writing Module Index

**Files:**
- Create: `frontend/src/components/writing/index.ts`

- [ ] **Step 1: Create barrel export**

```typescript
// frontend/src/components/writing/index.ts
export { WritingStatsBar } from './WritingStatsBar';
export { FocusTimer } from './FocusTimer';
export { ThemeSwitcher } from './ThemeSwitcher';
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/writing/index.ts
git commit -m "feat(writing): add barrel export for writing components"
```

---

### Task 14: Final Verification

- [ ] **Step 1: Run full type check**

Run: `cd /Users/z/CodeBuddy/wechat/frontend && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 2: Run tests**

Run: `cd /Users/z/CodeBuddy/wechat/frontend && npm test`
Expected: All tests pass

- [ ] **Step 3: Start dev server and verify**

Run: `cd /Users/z/CodeBuddy/wechat/frontend && npm run dev`
Expected: App starts without errors, theme is applied

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "feat: complete writer theme system with warm brown palette"
```
