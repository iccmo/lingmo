import type { AppMode } from 'src/types';
import { Cpu, PenTool } from 'lucide-react';

interface Props {
  mode: AppMode;
  onChange: (mode: AppMode) => void;
}

export function ModeToggle({ mode, onChange }: Props) {
  return (
    <div className="flex items-center bg-surface rounded-full p-0.5 gap-0.5 border border-border">
      <button
        onClick={() => onChange('auto')}
        className={`px-3 py-1.5 rounded-full text-xs font-medium transition-all duration-200 flex items-center gap-1.5 min-h-[32px] ${
          mode === 'auto'
            ? 'bg-accent text-white shadow-sm shadow-accent/25'
            : 'text-ink-muted hover:text-ink hover:bg-surface-hover'
        }`}
      >
        <Cpu size={13} />
        <span className="hidden sm:inline">全自动</span>
      </button>
      <button
        onClick={() => onChange('creator')}
        className={`px-3 py-1.5 rounded-full text-xs font-medium transition-all duration-200 flex items-center gap-1.5 min-h-[32px] ${
          mode === 'creator'
            ? 'bg-accent text-white shadow-sm shadow-accent/25'
            : 'text-ink-muted hover:text-ink hover:bg-surface-hover'
        }`}
      >
        <PenTool size={13} />
        <span className="hidden sm:inline">创作者</span>
      </button>
    </div>
  );
}
