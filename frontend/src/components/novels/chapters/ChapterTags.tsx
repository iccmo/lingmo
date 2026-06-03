/** 章节标签选择器 — 从 ChapterList.tsx 提取 */
import { Tag } from 'lucide-react';

interface TagOption {
  key: string;
  Icon?: React.ComponentType<{ size?: number }>;
  emoji?: string;
  label: string;
  color: string;
}

interface Props {
  chapter: number;
  selectedTags: string[];
  options: TagOption[];
  onToggle: (tag: string) => void;
  onClear: () => void;
  onClose: () => void;
}

export function ChapterTags({ chapter, selectedTags, options, onToggle, onClear, onClose }: Props) {
  return (
    <div
      className="fixed inset-0 z-[95] flex items-center justify-center"
      onClick={(e) => { e.stopPropagation(); onClose(); }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="bg-card border border-border rounded-xl shadow-xl p-4 w-[260px] animate-[fadeSlideIn_0.15s_ease-out]"
      >
        <div className="flex items-center justify-between mb-3">
          <h4 className="text-xs font-semibold text-ink">
            <Tag size={12} className="mr-1" /> 第{chapter}章 · 标签
          </h4>
          <button onClick={onClose} className="text-xs text-ink-muted hover:text-ink">
            ✕
          </button>
        </div>
        <div className="space-y-1">
          {options.map((tag) => {
            const selected = selectedTags.includes(tag.key);
            const Icon = tag.Icon;
            return (
              <button
                key={tag.key}
                onClick={() => onToggle(tag.key)}
                className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-xs text-left transition-colors ${
                  selected
                    ? 'bg-accent-soft/50 border border-accent/20'
                    : 'hover:bg-paper border border-transparent'
                }`}
              >
                {tag.emoji ? (
                  <span className="text-base">{tag.emoji}</span>
                ) : Icon ? (
                  <Icon size={14} />
                ) : null}
                <span className={`flex-1 ${selected ? 'text-accent font-medium' : 'text-ink'}`}>
                  {tag.label}
                </span>
                {selected && <span className="text-accent text-[10px]">✓</span>}
              </button>
            );
          })}
        </div>
        {selectedTags.length > 0 && (
          <button
            onClick={onClear}
            className="w-full mt-3 text-[10px] text-ink-muted hover:text-destructive transition-colors py-1.5"
          >
            清除所有标签
          </button>
        )}
      </div>
    </div>
  );
}
