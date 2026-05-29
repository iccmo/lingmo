import { useState, useRef, useEffect } from 'react';
import { Sparkles, Check } from 'lucide-react';
import { usePreset } from 'src/hooks/usePreset';

export function PresetSwitcher() {
  const { currentPreset, presets, applyPreset, cyclePreset } = usePreset();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1.5 px-2 py-1.5 text-sm
                   text-text-muted hover:text-text-primary
                   hover:bg-bg-surface rounded-md transition-colors"
        title={currentPreset ? `场景: ${currentPreset.name}` : '选择写作场景'}
      >
        <Sparkles size={14} />
        {currentPreset && (
          <span className="text-xs">{currentPreset.icon}</span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 top-full mt-1 w-64 py-1
                        bg-bg-surface border border-border-default
                        rounded-lg shadow-default z-50 max-h-96 overflow-y-auto">
          <div className="px-3 py-2 border-b border-border-default">
            <p className="text-xs font-medium text-text-muted">写作场景</p>
          </div>
          {presets.map(preset => (
            <button
              key={preset.id}
              onClick={() => { applyPreset(preset); setOpen(false); }}
              className={`
                flex items-center gap-3 w-full px-3 py-2.5 text-left transition-colors
                ${currentPreset?.id === preset.id
                  ? 'bg-brand-accent/10 text-text-primary'
                  : 'text-text-secondary hover:bg-bg-raised hover:text-text-primary'}
              `}
            >
              <span className="text-lg shrink-0">{preset.icon}</span>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium">{preset.name}</p>
                <p className="text-xs text-text-muted truncate">{preset.description}</p>
              </div>
              {currentPreset?.id === preset.id && (
                <Check size={14} className="text-brand-primary shrink-0" />
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
