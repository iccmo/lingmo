import { useState, useCallback } from 'react';
import type { LayoutMode, LayoutConfig } from 'src/themes/layouts';
import { layouts, getLayoutById } from 'src/themes/layouts';

export function useLayout() {
  const [currentLayout, setCurrentLayout] = useState<LayoutConfig>(() => {
    const saved = localStorage.getItem('lingmo-layout');
    if (saved) {
      return getLayoutById(saved as LayoutMode);
    }
    return layouts[0];
  });

  const setLayout = useCallback((mode: LayoutMode) => {
    const layout = getLayoutById(mode);
    setCurrentLayout(layout);
    localStorage.setItem('lingmo-layout', mode);
  }, []);

  const cycleLayout = useCallback(() => {
    const idx = layouts.findIndex(l => l.id === currentLayout.id);
    const next = layouts[(idx + 1) % layouts.length];
    setCurrentLayout(next);
    localStorage.setItem('lingmo-layout', next.id);
  }, [currentLayout]);

  return {
    currentLayout,
    layouts,
    setLayout,
    cycleLayout,
  };
}
