import type { Theme } from './types';

export const lightWarmTheme: Theme = {
  id: 'light-warm',
  name: '暖光素笺',
  description: '白天写作，明亮柔和，纸张质感',

  colors: {
    bg: {
      base: '#FFFBF5',
      surface: '#FFFFFF',
      raised: '#F5F0E8',
      overlay: '#EDE8DF',
    },
    text: {
      primary: '#1E1B18',
      secondary: '#5C5347',
      muted: '#8A7E70',
      inverse: '#FFFBF5',
    },
    brand: {
      primary: '#8B7355',
      primaryHover: '#6D5A43',
      secondary: '#B49A6D',
      accent: '#D4A574',
    },
    semantic: {
      success: '#5A7A4B',
      warning: '#B45309',
      error: '#9B3A2A',
      info: '#4A6A8A',
    },
    border: {
      default: 'rgba(30, 27, 24, 0.1)',
      strong: 'rgba(30, 27, 24, 0.2)',
      subtle: 'rgba(30, 27, 24, 0.05)',
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
    shadow: '0 2px 8px rgba(0, 0, 0, 0.08)',
    glass: 'rgba(255, 251, 245, 0.9) backdrop-blur(20px)',
    glow: '0 0 20px rgba(139, 115, 85, 0.1)',
  },
};
