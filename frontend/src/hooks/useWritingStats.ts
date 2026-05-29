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
