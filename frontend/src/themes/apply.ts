import type { Theme } from './types';

export function applyTheme(theme: Theme): void {
  const root = document.documentElement;

  // Background colors (new system)
  root.style.setProperty('--bg-base', theme.colors.bg.base);
  root.style.setProperty('--bg-surface', theme.colors.bg.surface);
  root.style.setProperty('--bg-raised', theme.colors.bg.raised);
  root.style.setProperty('--bg-overlay', theme.colors.bg.overlay);

  // Text colors (new system)
  root.style.setProperty('--text-primary', theme.colors.text.primary);
  root.style.setProperty('--text-secondary', theme.colors.text.secondary);
  root.style.setProperty('--text-muted', theme.colors.text.muted);
  root.style.setProperty('--text-inverse', theme.colors.text.inverse);

  // Brand colors (new system)
  root.style.setProperty('--brand-primary', theme.colors.brand.primary);
  root.style.setProperty('--brand-primary-hover', theme.colors.brand.primaryHover);
  root.style.setProperty('--brand-secondary', theme.colors.brand.secondary);
  root.style.setProperty('--brand-accent', theme.colors.brand.accent);

  // Semantic colors (new system)
  root.style.setProperty('--semantic-success', theme.colors.semantic.success);
  root.style.setProperty('--semantic-warning', theme.colors.semantic.warning);
  root.style.setProperty('--semantic-error', theme.colors.semantic.error);
  root.style.setProperty('--semantic-info', theme.colors.semantic.info);

  // Border colors (new system)
  root.style.setProperty('--border-default', theme.colors.border.default);
  root.style.setProperty('--border-strong', theme.colors.border.strong);
  root.style.setProperty('--border-subtle', theme.colors.border.subtle);

  // Typography (new system)
  root.style.setProperty('--font-heading', theme.typography.heading);
  root.style.setProperty('--font-body', theme.typography.body);
  root.style.setProperty('--font-mono', theme.typography.mono);
  root.style.setProperty('--font-editor', theme.typography.editor.fontFamily);
  root.style.setProperty('--font-editor-size', theme.typography.editor.fontSize);
  root.style.setProperty('--font-editor-line-height', theme.typography.editor.lineHeight);

  // Spacing (new system)
  root.style.setProperty('--radius-sm', theme.spacing.radius.sm);
  root.style.setProperty('--radius-md', theme.spacing.radius.md);
  root.style.setProperty('--radius-lg', theme.spacing.radius.lg);

  // Effects (new system)
  root.style.setProperty('--shadow', theme.effects.shadow);
  root.style.setProperty('--glow', theme.effects.glow);

  // Legacy CSS variables (for backward compatibility)
  root.style.setProperty('--color-paper', theme.colors.bg.base);
  root.style.setProperty('--color-surface', theme.colors.bg.surface);
  root.style.setProperty('--color-surface-hover', theme.colors.bg.raised);
  root.style.setProperty('--color-surface-raised', theme.colors.bg.overlay);
  root.style.setProperty('--color-card', theme.colors.bg.surface);
  root.style.setProperty('--color-ink', theme.colors.text.primary);
  root.style.setProperty('--color-ink-muted', theme.colors.text.secondary);
  root.style.setProperty('--color-ink-subtle', theme.colors.text.muted);
  root.style.setProperty('--color-accent', theme.colors.brand.primary);
  root.style.setProperty('--color-accent-hover', theme.colors.brand.primaryHover);
  root.style.setProperty('--color-accent-soft', `${theme.colors.brand.primary}1F`);
  root.style.setProperty('--color-success', theme.colors.semantic.success);
  root.style.setProperty('--color-warn', theme.colors.semantic.warning);
  root.style.setProperty('--color-destructive', theme.colors.semantic.error);
  root.style.setProperty('--color-info', theme.colors.semantic.info);

  // Save preference
  localStorage.setItem('lingmo-theme', theme.id);
}
