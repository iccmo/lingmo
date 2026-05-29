import { useState } from 'react';
import { Pipette, Save, RotateCcw } from 'lucide-react';
import type { Theme } from 'src/themes/types';
import { warmBrownTheme } from 'src/themes/warm-brown';
import { useTheme } from 'src/hooks/useTheme';

function hslToHex(h: number, s: number, l: number): string {
  s /= 100;
  l /= 100;
  const a = s * Math.min(l, 1 - l);
  const f = (n: number) => {
    const k = (n + h / 30) % 12;
    const color = l - a * Math.max(Math.min(k - 3, 9 - k, 1), -1);
    return Math.round(255 * color).toString(16).padStart(2, '0');
  };
  return `#${f(0)}${f(8)}${f(4)}`;
}

function generateThemeFromHue(hue: number, isDark: boolean): Theme {
  const base = isDark ? 12 : 96;
  const surface = isDark ? 18 : 100;
  const textPrimary = isDark ? 95 : 10;
  const textSecondary = isDark ? 70 : 40;

  return {
    ...warmBrownTheme,
    id: 'custom',
    name: '自定义主题',
    description: `HSL ${hue}°`,
    colors: {
      bg: {
        base: hslToHex(hue, 15, base),
        surface: hslToHex(hue, 12, surface),
        raised: hslToHex(hue, 10, base + 5),
        overlay: hslToHex(hue, 8, base + 10),
      },
      text: {
        primary: hslToHex(hue, 10, textPrimary),
        secondary: hslToHex(hue, 8, textSecondary),
        muted: hslToHex(hue, 6, textSecondary - 15),
        inverse: hslToHex(hue, 15, base),
      },
      brand: {
        primary: hslToHex(hue, 60, 55),
        primaryHover: hslToHex(hue, 60, 65),
        secondary: hslToHex(hue, 40, 45),
        accent: hslToHex(hue, 50, 70),
      },
      semantic: {
        success: hslToHex(140, 40, 50),
        warning: hslToHex(40, 70, 55),
        error: hslToHex(0, 60, 55),
        info: hslToHex(210, 50, 55),
      },
      border: {
        default: `rgba(${isDark ? '255,255,255' : '0,0,0'}, 0.08)`,
        strong: `rgba(${isDark ? '255,255,255' : '0,0,0'}, 0.15)`,
        subtle: `rgba(${isDark ? '255,255,255' : '0,0,0'}, 0.04)`,
      },
    },
  };
}

export function CustomThemeEditor() {
  const { setTheme } = useTheme();
  const [hue, setHue] = useState(30);
  const [isDark, setIsDark] = useState(true);
  const [open, setOpen] = useState(false);

  const previewTheme = generateThemeFromHue(hue, isDark);

  const apply = () => {
    setTheme(previewTheme);
    localStorage.setItem('lingmo-custom-hue', String(hue));
    localStorage.setItem('lingmo-custom-dark', String(isDark));
    setOpen(false);
  };

  return (
    <div className="relative">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1.5 px-2 py-1.5 text-sm
                   text-text-muted hover:text-text-primary
                   hover:bg-bg-surface rounded-md transition-colors"
        title="自定义主题"
      >
        <Pipette size={14} />
      </button>

      {open && (
        <div className="absolute right-0 top-full mt-1 w-72 p-4
                        bg-bg-surface border border-border-default
                        rounded-lg shadow-default z-50">
          <p className="text-sm font-medium text-text-primary mb-3">自定义主题</p>

          {/* Hue slider */}
          <div className="space-y-2 mb-4">
            <div className="flex items-center justify-between">
              <label className="text-xs text-text-muted">主色调</label>
              <span className="text-xs font-mono text-text-secondary">{hue}°</span>
            </div>
            <input
              type="range"
              min={0}
              max={360}
              value={hue}
              onChange={e => setHue(Number(e.target.value))}
              className="w-full h-2 rounded-full appearance-none cursor-pointer"
              style={{
                background: `linear-gradient(to right,
                  hsl(0,60%,55%), hsl(60,60%,55%), hsl(120,60%,55%),
                  hsl(180,60%,55%), hsl(240,60%,55%), hsl(300,60%,55%),
                  hsl(360,60%,55%))`,
              }}
            />
          </div>

          {/* Dark/Light toggle */}
          <div className="flex items-center gap-2 mb-4">
            <button
              onClick={() => setIsDark(true)}
              className={`flex-1 py-1.5 text-xs rounded-md transition-colors ${
                isDark ? 'bg-brand-primary text-text-inverse' : 'bg-bg-raised text-text-muted'
              }`}
            >
              深色
            </button>
            <button
              onClick={() => setIsDark(false)}
              className={`flex-1 py-1.5 text-xs rounded-md transition-colors ${
                !isDark ? 'bg-brand-primary text-text-inverse' : 'bg-bg-raised text-text-muted'
              }`}
            >
              浅色
            </button>
          </div>

          {/* Color preview */}
          <div className="flex gap-2 mb-4">
            <div className="flex-1 h-8 rounded" style={{ background: previewTheme.colors.bg.base }} />
            <div className="flex-1 h-8 rounded" style={{ background: previewTheme.colors.bg.surface }} />
            <div className="flex-1 h-8 rounded" style={{ background: previewTheme.colors.brand.primary }} />
            <div className="flex-1 h-8 rounded" style={{ background: previewTheme.colors.brand.accent }} />
          </div>

          {/* Actions */}
          <div className="flex gap-2">
            <button
              onClick={apply}
              className="flex-1 flex items-center justify-center gap-1.5 py-2 text-sm
                         bg-brand-primary text-text-inverse rounded-md
                         hover:bg-brand-primary-hover transition-colors"
            >
              <Save size={14} />
              应用
            </button>
            <button
              onClick={() => { setHue(30); setIsDark(true); }}
              className="px-3 py-2 text-sm text-text-muted hover:text-text-primary
                         bg-bg-raised rounded-md transition-colors"
            >
              <RotateCcw size={14} />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
