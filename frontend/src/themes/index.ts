import type { Theme } from './types';
import { warmBrownTheme } from './warm-brown';
import { lightWarmTheme } from './light-warm';
import { coolBlueTheme } from './cool-blue';

export const themes: Theme[] = [
  warmBrownTheme,
  lightWarmTheme,
  coolBlueTheme,
];

export const defaultTheme = warmBrownTheme;

export function getThemeById(id: string): Theme | undefined {
  return themes.find(t => t.id === id);
}

export type { Theme } from './types';
