import { useState, useEffect, useCallback } from 'react';
import type { Theme } from 'src/themes/types';
import { themes } from 'src/themes';

interface TimeThemeConfig {
  enabled: boolean;
  lightThemeId: string;
  darkThemeId: string;
  lightHour: number;
  darkHour: number;
}

const defaultConfig: TimeThemeConfig = {
  enabled: false,
  lightThemeId: 'light-warm',
  darkThemeId: 'warm-brown',
  lightHour: 6,
  darkHour: 18,
};

export function useTimeTheme(onThemeChange: (theme: Theme) => void) {
  const [config, setConfig] = useState<TimeThemeConfig>(() => {
    const saved = localStorage.getItem('lingmo-time-theme');
    if (saved) {
      try { return { ...defaultConfig, ...JSON.parse(saved) }; }
      catch { /* ignore */ }
    }
    return defaultConfig;
  });

  const updateConfig = useCallback((patch: Partial<TimeThemeConfig>) => {
    const next = { ...config, ...patch };
    setConfig(next);
    localStorage.setItem('lingmo-time-theme', JSON.stringify(next));
  }, [config]);

  // Check time and apply theme
  useEffect(() => {
    if (!config.enabled) return;

    const check = () => {
      const hour = new Date().getHours();
      const isDark = hour >= config.darkHour || hour < config.lightHour;
      const themeId = isDark ? config.darkThemeId : config.lightThemeId;
      const theme = themes.find(t => t.id === themeId);
      if (theme) onThemeChange(theme);
    };

    check();
    const interval = setInterval(check, 60000); // Check every minute
    return () => clearInterval(interval);
  }, [config, onThemeChange]);

  return { config, updateConfig };
}
