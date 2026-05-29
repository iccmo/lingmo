import type { Theme } from './types';

export const warmBrownTheme: Theme = {
  id: 'warm-brown',
  name: '墨韵暖棕',
  description: '深夜书房，护眼柔和，文学氛围',

  colors: {
    bg: {
      base: '#1E1B18',
      surface: '#2A2520',
      raised: '#332E28',
      overlay: '#3D3730',
    },
    text: {
      primary: '#F5F0E8',
      secondary: '#C4B8A8',
      muted: '#8A7E70',
      inverse: '#1E1B18',
    },
    brand: {
      primary: '#D4A574',
      primaryHover: '#E0B88A',
      secondary: '#8B7355',
      accent: '#E8C49A',
    },
    semantic: {
      success: '#7C9A6B',
      warning: '#D4A574',
      error: '#C47A6B',
      info: '#7A8B9A',
    },
    border: {
      default: 'rgba(245, 240, 232, 0.1)',
      strong: 'rgba(245, 240, 232, 0.2)',
      subtle: 'rgba(245, 240, 232, 0.05)',
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
    glass: 'rgba(42, 37, 32, 0.8) backdrop-blur(20px)',
    glow: '0 0 20px rgba(212, 165, 116, 0.15)',
  },
};
