import type { Theme } from './types';
import type { LayoutMode } from './layouts';

export interface WritingPreset {
  id: string;
  name: string;
  description: string;
  themeId: string;
  layoutMode: LayoutMode;
  editorFont: string;
  editorSize: string;
  editorLineHeight: string;
  typewriterMode: boolean;
  paperTexture: boolean;
  icon: string;
}

export const presets: WritingPreset[] = [
  {
    id: 'late-night',
    name: '深夜赶稿',
    description: '暖棕紧凑，专注码字',
    themeId: 'warm-brown',
    layoutMode: 'compact',
    editorFont: "'Noto Serif SC', serif",
    editorSize: '16px',
    editorLineHeight: '1.8',
    typewriterMode: false,
    paperTexture: true,
    icon: '🌙',
  },
  {
    id: 'inspiration',
    name: '灵感迸发',
    description: '紫罗兰沉浸，创意流动',
    themeId: 'twilight-violet',
    layoutMode: 'immersive',
    editorFont: "'Noto Serif SC', serif",
    editorSize: '17px',
    editorLineHeight: '1.85',
    typewriterMode: true,
    paperTexture: true,
    icon: '✨',
  },
  {
    id: 'precise',
    name: '严谨推敲',
    description: '靛蓝三栏，细致打磨',
    themeId: 'cool-blue',
    layoutMode: 'classic',
    editorFont: "'JetBrains Mono', monospace",
    editorSize: '15px',
    editorLineHeight: '1.7',
    typewriterMode: false,
    paperTexture: false,
    icon: '🔍',
  },
  {
    id: 'morning',
    name: '晨间创作',
    description: '素笺明亮，清新开始',
    themeId: 'light-warm',
    layoutMode: 'immersive',
    editorFont: "'Noto Serif SC', 'KaiTi', serif",
    editorSize: '16px',
    editorLineHeight: '1.8',
    typewriterMode: false,
    paperTexture: true,
    icon: '☀️',
  },
  {
    id: 'zen',
    name: '发呆放空',
    description: '灰绿禅境，随心书写',
    themeId: 'sage-green',
    layoutMode: 'zen',
    editorFont: "'Noto Serif SC', serif",
    editorSize: '18px',
    editorLineHeight: '2.0',
    typewriterMode: true,
    paperTexture: true,
    icon: '🍃',
  },
  {
    id: 'ink-painting',
    name: '水墨意境',
    description: '翠墨东方，古韵流淌',
    themeId: 'bamboo-ink',
    layoutMode: 'compact',
    editorFont: "'Noto Serif SC', 'KaiTi', 'STKaiti', serif",
    editorSize: '17px',
    editorLineHeight: '1.9',
    typewriterMode: true,
    paperTexture: true,
    icon: '🎋',
  },
  {
    id: 'sprint',
    name: '极速冲刺',
    description: '无干扰全屏，速度至上',
    themeId: 'warm-brown',
    layoutMode: 'zen',
    editorFont: "'Noto Sans SC', sans-serif",
    editorSize: '18px',
    editorLineHeight: '1.6',
    typewriterMode: true,
    paperTexture: false,
    icon: '⚡',
  },
];

export function getPresetById(id: string): WritingPreset | undefined {
  return presets.find(p => p.id === id);
}
