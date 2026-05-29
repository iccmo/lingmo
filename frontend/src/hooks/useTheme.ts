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
