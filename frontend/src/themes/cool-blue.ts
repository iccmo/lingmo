import type { Theme } from './types';

export const coolBlueTheme: Theme = {
  id: 'cool-blue',
  name: '深海靛蓝',
  description: '冷静专注，科技感，代码风格',

  colors: {
    bg: {
      base: '#0F172A',
      surface: '#1E293B',
      raised: '#283548',
      overlay: '#334155',
    },
    text: {
      primary: '#F1F5F9',
      secondary: '#94A3B8',
      muted: '#64748B',
      inverse: '#0F172A',
    },
    brand: {
      primary: '#6366F1',
      primaryHover: '#818CF8',
      secondary: '#8B5CF6',
      accent: '#A78BFA',
    },
    semantic: {
      success: '#34D399',
      warning: '#FBBF24',
      error: '#F87171',
      info: '#60A5FA',
    },
    border: {
      default: 'rgba(241, 245, 249, 0.08)',
      strong: 'rgba(241, 245, 249, 0.15)',
      subtle: 'rgba(241, 245, 249, 0.04)',
    },
  },

  typography: {
    heading: "'Inter', 'Noto Sans SC', sans-serif",
    body: "'Inter', 'Noto Sans SC', sans-serif",
    mono: "'JetBrains Mono', monospace",
    editor: {
      fontFamily: "'JetBrains Mono', monospace",
      fontSize: '15px',
      lineHeight: '1.7',
      letterSpacing: '0',
    },
  },

  spacing: {
    radius: { sm: '4px', md: '6px', lg: '8px' },
  },

  effects: {
    shadow: '0 4px 12px rgba(0, 0, 0, 0.4)',
    glass: 'rgba(30, 41, 59, 0.8) backdrop-blur(20px)',
    glow: '0 0 20px rgba(99, 102, 241, 0.2)',
  },
};
