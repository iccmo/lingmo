import type { AppMode } from 'src/types';

interface Props {
  mode: AppMode;
  onChange: (mode: AppMode) => void;
}

export function ModeToggle({ mode, onChange }: Props) {
  return (
    <div className="flex items-center bg-paper rounded-full p-0.5 gap-0.5 border border-border">
      <button
        onClick={() => onChange('auto')}
        className={`px-4 py-1.5 rounded-full text-xs font-medium transition-all duration-200 ${
          mode === 'auto'
            ? 'bg-accent text-white shadow-[0_2px_8px_rgba(61,79,122,0.25)]'
            : 'text-ink-muted hover:text-ink hover:bg-ink/5 dark:hover:bg-white/5'
        }`}
      >
        全自动
      </button>
      <button
        onClick={() => onChange('creator')}
        className={`px-4 py-1.5 rounded-full text-xs font-medium transition-all duration-200 ${
          mode === 'creator'
            ? 'bg-accent text-white shadow-[0_2px_8px_rgba(61,79,122,0.25)]'
            : 'text-ink-muted hover:text-ink hover:bg-ink/5 dark:hover:bg-white/5'
        }`}
      >
        创作者
      </button>
    </div>
  );
}
