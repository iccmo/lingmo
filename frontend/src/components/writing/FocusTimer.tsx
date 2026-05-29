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
          const isBreak = !prev.isBreak;
          const duration = isBreak ? POMODORO_BREAK : POMODORO_WORK;

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

      <span className="text-xs text-text-muted">
        {state.isBreak ? '休息中' : '专注中'}
      </span>

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
