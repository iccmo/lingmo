import type { ChapterMeta } from 'src/types';

function gradeForScore(s?: number): string {
  if (!s && s !== 0) return '?';
  if (s >= 0.85) return 'S';
  if (s >= 0.75) return 'A';
  if (s >= 0.65) return 'B';
  if (s >= 0.55) return 'C';
  return 'D';
}

const DOT_COLOR: Record<string, string> = {
  S: 'bg-emerald-400',
  A: 'bg-emerald-400',
  B: 'bg-sky-400',
  C: 'bg-amber-400',
  D: 'bg-red-400',
};

interface Props {
  chapters: ChapterMeta[];
  activeChapter: number | null;
  onSelect: (num: number) => void;
}

export function WriterChapterList({ chapters, activeChapter, onSelect }: Props) {
  const writableChapters = chapters.filter((c) => c.word_count > 0);

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="px-3 py-3 border-b border-border">
        <span className="text-[10px] font-semibold text-ink-muted uppercase tracking-widest">
          目录
        </span>
      </div>

      {/* Chapter list */}
      <div className="flex-1 overflow-y-auto">
        {writableChapters.length === 0 ? (
          <div className="flex items-center justify-center h-full text-sm text-ink-muted">
            暂无章节
          </div>
        ) : (
          writableChapters.map((ch) => {
            const grade = gradeForScore(ch.quality_score);
            const isActive = ch.number === activeChapter;

            return (
              <button
                key={ch.number}
                onClick={() => onSelect(ch.number)}
                className={`flex items-center gap-2 w-full px-3 py-2 text-left transition-colors border-l-[3px] ${
                  isActive
                    ? 'bg-accent-soft border-l-accent font-medium text-ink'
                    : 'border-l-transparent text-ink-muted hover:bg-paper'
                }`}
              >
                {/* Quality dot — 2px circle */}
                <span
                  className={`inline-block w-0.5 h-0.5 rounded-full shrink-0 ${
                    DOT_COLOR[grade] || 'bg-ink-subtle'
                  }`}
                />
                {/* Chapter number */}
                <span className="text-xs tabular-nums shrink-0">
                  {ch.number}
                </span>
                {/* Chapter title */}
                <span className="text-xs truncate">{ch.title}</span>
              </button>
            );
          })
        )}
      </div>
    </div>
  );
}
