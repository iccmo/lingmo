import type { Theme } from './types';

export const twilightVioletTheme: Theme = {
  id: 'twilight-violet',
  name: '暮色紫罗兰',
  description: '浪漫神秘，灵感涌现，艺术氛围',

  colors: {
    bg: {
      base: '#1A1520',
      surface: '#241E2E',
      raised: '#2E2838',
      overlay: '#383242',
    },
    text: {
      primary: '#F0E8F5',
      secondary: '#B8A8C4',
      muted: '#7B6B8A',
      inverse: '#1A1520',
    },
    brand: {
      primary: '#A87BDB',
      primaryHover: '#BC8FEF',
      secondary: '#8B5FC4',
      accent: '#C4A0E8',
    },
    semantic: {
      success: '#7BDB9E',
      warning: '#DBB87B',
      error: '#DB7B8A',
      info: '#7BA8DB',
    },
    border: {
      default: 'rgba(240, 232, 245, 0.08)',
      strong: 'rgba(240, 232, 245, 0.15)',
      subtle: 'rgba(240, 232, 245, 0.04)',
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
    radius: { sm: '8px', md: '10px', lg: '14px' },
  },

  effects: {
    shadow: '0 4px 12px rgba(0, 0, 0, 0.3)',
    glass: 'rgba(36, 30, 46, 0.8) backdrop-blur(20px)',
    glow: '0 0 20px rgba(168, 123, 219, 0.2)',
  },
};
