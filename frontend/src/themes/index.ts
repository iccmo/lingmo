import type { Theme } from './types';
import { warmBrownTheme } from './warm-brown';

export const themes: Theme[] = [
  warmBrownTheme,
];

export const defaultTheme = warmBrownTheme;

export function getThemeById(id: string): Theme | undefined {
  return themes.find(t => t.id === id);
}

export type { Theme } from './types';
