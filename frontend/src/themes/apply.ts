import type { Theme } from './types';

export function applyTheme(theme: Theme): void {
  const root = document.documentElement;

  // Background colors
  root.style.setProperty('--bg-base', theme.colors.bg.base);
  root.style.setProperty('--bg-surface', theme.colors.bg.surface);
  root.style.setProperty('--bg-raised', theme.colors.bg.raised);
  root.style.setProperty('--bg-overlay', theme.colors.bg.overlay);

  // Text colors
  root.style.setProperty('--text-primary', theme.colors.text.primary);
  root.style.setProperty('--text-secondary', theme.colors.text.secondary);
  root.style.setProperty('--text-muted', theme.colors.text.muted);
  root.style.setProperty('--text-inverse', theme.colors.text.inverse);

  // Brand colors
  root.style.setProperty('--brand-primary', theme.colors.brand.primary);
  root.style.setProperty('--brand-primary-hover', theme.colors.brand.primaryHover);
  root.style.setProperty('--brand-secondary', theme.colors.brand.secondary);
  root.style.setProperty('--brand-accent', theme.colors.brand.accent);

  // Semantic colors
  root.style.setProperty('--semantic-success', theme.colors.semantic.success);
  root.style.setProperty('--semantic-warning', theme.colors.semantic.warning);
  root.style.setProperty('--semantic-error', theme.colors.semantic.error);
  root.style.setProperty('--semantic-info', theme.colors.semantic.info);

  // Border colors
  root.style.setProperty('--border-default', theme.colors.border.default);
  root.style.setProperty('--border-strong', theme.colors.border.strong);
  root.style.setProperty('--border-subtle', theme.colors.border.subtle);

  // Typography
  root.style.setProperty('--font-heading', theme.typography.heading);
  root.style.setProperty('--font-body', theme.typography.body);
  root.style.setProperty('--font-mono', theme.typography.mono);
  root.style.setProperty('--font-editor', theme.typography.editor.fontFamily);
  root.style.setProperty('--font-editor-size', theme.typography.editor.fontSize);
  root.style.setProperty('--font-editor-line-height', theme.typography.editor.lineHeight);

  // Spacing
  root.style.setProperty('--radius-sm', theme.spacing.radius.sm);
  root.style.setProperty('--radius-md', theme.spacing.radius.md);
  root.style.setProperty('--radius-lg', theme.spacing.radius.lg);

  // Effects
  root.style.setProperty('--shadow', theme.effects.shadow);
  root.style.setProperty('--glow', theme.effects.glow);

  // Save preference
  localStorage.setItem('lingmo-theme', theme.id);
}
