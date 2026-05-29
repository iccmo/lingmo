import { useState, useRef, useEffect } from 'react';
import { Palette, Check, ChevronDown } from 'lucide-react';
import { useTheme } from 'src/hooks/useTheme';

interface Props {
  compact?: boolean;
}

export function ThemeSwitcher({ compact = false }: Props) {
  const { currentTheme, themes, setTheme } = useTheme();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  // 点击外部关闭
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  // compact 模式：点击直接切换
  if (compact) {
    const nextTheme = () => {
      const idx = themes.findIndex(t => t.id === currentTheme.id);
      const next = themes[(idx + 1) % themes.length];
      setTheme(next);
    };

    return (
      <button
        onClick={nextTheme}
        className="flex items-center gap-1.5 px-2 py-1.5 text-sm
                   text-text-muted hover:text-text-primary
                   hover:bg-bg-surface rounded-md transition-colors"
        title={`当前: ${currentTheme.name} · 点击切换`}
      >
        <Palette size={14} />
        <div
          className="w-4 h-4 rounded-full border border-border-default"
          style={{ background: currentTheme.colors.brand.primary }}
        />
      </button>
    );
  }

  // 完整模式：设置页用
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
