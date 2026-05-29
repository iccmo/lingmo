import { Palette, Check } from 'lucide-react';
import { useTheme } from 'src/hooks/useTheme';

interface Props {
  compact?: boolean;
}

export function ThemeSwitcher({ compact = false }: Props) {
  const { currentTheme, themes, setTheme } = useTheme();

  if (compact) {
    return (
      <div className="flex items-center gap-1">
        {themes.map(theme => (
          <button
            key={theme.id}
            onClick={() => setTheme(theme)}
            className={`
              w-6 h-6 rounded-full border-2 transition-all
              ${currentTheme.id === theme.id
                ? 'border-brand-primary scale-110'
                : 'border-border-default hover:border-border-strong'}
            `}
            style={{ background: theme.colors.brand.primary }}
            title={theme.name}
          />
        ))}
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 text-text-primary">
        <Palette size={16} />
        <span className="font-medium">主题</span>
      </div>

      <div className="grid grid-cols-1 gap-2">
        {themes.map(theme => (
          <button
            key={theme.id}
            onClick={() => setTheme(theme)}
            className={`
              flex items-center gap-3 p-3 rounded-lg border-2 transition-all text-left
              ${currentTheme.id === theme.id
                ? 'border-brand-primary bg-brand-accent/10'
                : 'border-border-default hover:border-border-strong hover:bg-bg-surface'}
            `}
          >
            <div className="flex gap-1 shrink-0">
              <div
                className="w-5 h-5 rounded"
                style={{ background: theme.colors.bg.base }}
              />
              <div
                className="w-5 h-5 rounded"
                style={{ background: theme.colors.bg.surface }}
              />
              <div
                className="w-5 h-5 rounded"
                style={{ background: theme.colors.brand.primary }}
              />
            </div>

            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-text-primary">
                {theme.name}
              </p>
              <p className="text-xs text-text-muted truncate">
                {theme.description}
              </p>
            </div>

            {currentTheme.id === theme.id && (
              <Check size={16} className="text-brand-primary shrink-0" />
            )}
          </button>
        ))}
      </div>
    </div>
  );
}
