import { useState, useCallback } from 'react';
import type { WritingPreset } from 'src/themes/presets';
import { presets, getPresetById } from 'src/themes/presets';
import { themes } from 'src/themes';
import { useTheme } from './useTheme';
import { useLayout } from './useLayout';

export function usePreset() {
  const { setTheme } = useTheme();
  const { setLayout } = useLayout();

  const [currentPreset, setCurrentPreset] = useState<WritingPreset | null>(() => {
    const saved = localStorage.getItem('lingmo-preset');
    if (saved) {
      return getPresetById(saved) || null;
    }
    return null;
  });

  const applyPreset = useCallback((preset: WritingPreset) => {
    // Apply theme
    const theme = themes.find((t) => t.id === preset.themeId);
    if (theme) setTheme(theme);

    // Apply layout
    setLayout(preset.layoutMode);

    // Save editor preferences
    localStorage.setItem('lingmo-editor-font', preset.editorFont);
    localStorage.setItem('lingmo-editor-size', preset.editorSize);
    localStorage.setItem('lingmo-editor-line-height', preset.editorLineHeight);
    localStorage.setItem('lingmo-typewriter-mode', String(preset.typewriterMode));
    localStorage.setItem('lingmo-paper-texture', String(preset.paperTexture));

    setCurrentPreset(preset);
    localStorage.setItem('lingmo-preset', preset.id);
  }, [setTheme, setLayout]);

  const cyclePreset = useCallback(() => {
    const idx = currentPreset
      ? presets.findIndex(p => p.id === currentPreset.id)
      : -1;
    const next = presets[(idx + 1) % presets.length];
    applyPreset(next);
  }, [currentPreset, applyPreset]);

  return {
    currentPreset,
    presets,
    applyPreset,
    cyclePreset,
  };
}
