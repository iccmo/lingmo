import type { Theme } from './types';

export const sageGreenTheme: Theme = {
  id: 'sage-green',
  name: '雅致灰绿',
  description: '自然清新，护眼舒适，森林氛围',

  colors: {
    bg: {
      base: '#1A1F1A',
      surface: '#242B24',
      raised: '#2E362E',
      overlay: '#384238',
    },
    text: {
      primary: '#E8F0E8',
      secondary: '#A8B8A8',
      muted: '#6B7B6B',
      inverse: '#1A1F1A',
    },
    brand: {
      primary: '#7B9E6B',
      primaryHover: '#8FB87F',
      secondary: '#5A7A4B',
      accent: '#A8C49A',
    },
    semantic: {
      success: '#7B9E6B',
      warning: '#C4A35A',
      error: '#B87070',
      info: '#6B8E9E',
    },
    border: {
      default: 'rgba(232, 240, 232, 0.08)',
      strong: 'rgba(232, 240, 232, 0.15)',
      subtle: 'rgba(232, 240, 232, 0.04)',
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
    glass: 'rgba(36, 43, 36, 0.8) backdrop-blur(20px)',
    glow: '0 0 20px rgba(123, 158, 107, 0.15)',
  },
};
