export type LayoutMode = 'classic' | 'immersive' | 'compact' | 'zen';

export interface LayoutConfig {
  id: LayoutMode;
  name: string;
  description: string;
  sidebar: 'visible' | 'collapsed' | 'hidden';
  rightPanel: 'visible' | 'collapsed' | 'hidden';
  maxWidth: string;
  showHeader: boolean;
  showStats: boolean;
}

export const layouts: LayoutConfig[] = [
  {
    id: 'classic',
    name: '经典三栏',
    description: '章节列表 + 编辑器 + 上下文面板',
    sidebar: 'visible',
    rightPanel: 'visible',
    maxWidth: '100%',
    showHeader: true,
    showStats: true,
  },
  {
    id: 'immersive',
    name: '沉浸双栏',
    description: '章节列表 + 编辑器，专注写作',
    sidebar: 'visible',
    rightPanel: 'hidden',
    maxWidth: '100%',
    showHeader: true,
    showStats: true,
  },
  {
    id: 'compact',
    name: '紧凑单栏',
    description: '纯编辑器，最大化写作空间',
    sidebar: 'collapsed',
    rightPanel: 'hidden',
    maxWidth: '900px',
    showHeader: true,
    showStats: true,
  },
  {
    id: 'zen',
    name: '禅模式',
    description: '全屏沉浸，零干扰',
    sidebar: 'hidden',
    rightPanel: 'hidden',
    maxWidth: '800px',
    showHeader: false,
    showStats: false,
  },
];

export function getLayoutById(id: LayoutMode): LayoutConfig {
  return layouts.find(l => l.id === id) || layouts[0];
}
