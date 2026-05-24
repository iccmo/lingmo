import type { ChapterMeta } from 'src/types';

interface Props {
  chapters: ChapterMeta[];
}

export function QualityTrend({ chapters }: Props) {
  const gen = chapters.filter(c => c.word_count && c.word_count > 0);
  if (gen.length < 3) return null;

  const avgQ = gen.reduce((s, c) => s + (c.quality_score || 0), 0) / gen.length;
  const grades = gen.map(c => c.quality_score || 0);
  const minQ = Math.min(...grades);
  const maxQ = Math.max(...grades);

  // Word count trend
  const wordsList = gen.map(c => c.word_count);
  const firstHalf = wordsList.slice(0, Math.floor(wordsList.length / 2));
  const secondHalf = wordsList.slice(Math.floor(wordsList.length / 2));
  const firstAvg = firstHalf.length > 0 ? firstHalf.reduce((a, b) => a + b, 0) / firstHalf.length : 0;
  const secondAvg = secondHalf.length > 0 ? secondHalf.reduce((a, b) => a + b, 0) / secondHalf.length : 0;
  const wordTrend = firstAvg > 0 ? ((secondAvg - firstAvg) / firstAvg) * 100 : 0;

  return (
    <div className="mb-6 p-4 bg-paper border border-border rounded-lg">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-xs font-semibold text-ink-muted uppercase tracking-wide">质量趋势</h3>
        <div className="flex gap-3 text-[10px] text-ink-subtle tabular-nums flex-wrap">
          <span>均质 {avgQ.toFixed(2)}</span>
          <span>最低 {minQ.toFixed(2)}</span>
          <span>最高 {maxQ.toFixed(2)}</span>
          {gen.length >= 4 && (
            <span className={wordTrend > 10 ? 'text-emerald-500' : wordTrend < -10 ? 'text-amber-500' : ''}>
              字数{wordTrend > 5 ? '↑' : wordTrend < -5 ? '↓' : '→'}
              {Math.abs(wordTrend).toFixed(0)}%
            </span>
          )}
        </div>
      </div>
      <div className="flex items-end gap-1 h-14">
        {gen.map(c => {
          const q = c.quality_score || 0;
          const h = Math.max(8, q * 52);
          const grade = q >= 0.8 ? 'A' : q >= 0.6 ? 'B' : q >= 0.4 ? 'C' : 'D';
          const gradeColor = grade === 'A' ? 'text-emerald-500' : grade === 'B' ? 'text-sky-500' : grade === 'C' ? 'text-amber-500' : 'text-red-500';
          return (
            <div key={c.number} className="flex flex-col items-center gap-1 flex-1 group relative">
              {/* Hover tooltip */}
              <div className="absolute -top-10 left-1/2 -translate-x-1/2 bg-ink text-white text-[10px] rounded-md px-2 py-1
                opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap pointer-events-none z-10 shadow-lg">
                <span className="font-semibold">Ch{c.number}</span>
                <span className="mx-1">·</span>
                <span className={gradeColor}>{q.toFixed(2)}</span>
                <span className="mx-1">{grade}级</span>
                <div className="absolute -bottom-1 left-1/2 -translate-x-1/2 w-2 h-2 bg-ink rotate-45" />
              </div>
              <div
                className={`quality-bar-${grade} w-full rounded-t-sm opacity-80 hover:opacity-100 transition-opacity cursor-default`}
                style={{ height: `${h}px` }}
              />
              <span className="text-[8px] text-ink-subtle tabular-nums">{c.number}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
