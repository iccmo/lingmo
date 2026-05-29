import type { Theme } from './types';

export const bambooInkTheme: Theme = {
  id: 'bamboo-ink',
  name: '竹林翠墨',
  description: '东方水墨，古朴典雅，书卷气息',

  colors: {
    bg: {
      base: '#1A1C18',
      surface: '#242722',
      raised: '#2E3228',
      overlay: '#383D32',
    },
    text: {
      primary: '#E8EDE4',
      secondary: '#B4BEA8',
      muted: '#7A846E',
      inverse: '#1A1C18',
    },
    brand: {
      primary: '#8BA870',
      primaryHover: '#9EBC83',
      secondary: '#6B8A55',
      accent: '#B4D09A',
    },
    semantic: {
      success: '#8BA870',
      warning: '#C4A860',
      error: '#B87868',
      info: '#7094A8',
    },
    border: {
      default: 'rgba(232, 237, 228, 0.08)',
      strong: 'rgba(232, 237, 228, 0.15)',
      subtle: 'rgba(232, 237, 228, 0.04)',
    },
  },

  typography: {
    heading: "'Noto Serif SC', 'KaiTi', 'STKaiti', serif",
    body: "'Noto Sans SC', 'PingFang SC', sans-serif",
    mono: "'JetBrains Mono', monospace",
    editor: {
      fontFamily: "'Noto Serif SC', 'KaiTi', serif",
      fontSize: '17px',
      lineHeight: '1.85',
      letterSpacing: '0.04em',
    },
  },

  spacing: {
    radius: { sm: '4px', md: '6px', lg: '8px' },
  },

  effects: {
    shadow: '0 4px 12px rgba(0, 0, 0, 0.25)',
    glass: 'rgba(36, 39, 34, 0.85) backdrop-blur(16px)',
    glow: '0 0 16px rgba(139, 168, 112, 0.12)',
  },
};
