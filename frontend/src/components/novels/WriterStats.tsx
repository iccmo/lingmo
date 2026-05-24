import { useState, useEffect, useMemo } from 'react';
import type { ChapterMeta } from 'src/types';

const INSPIRATIONS = [
  '好的故事不是写出来的，是改出来的。',
  '读者不会记得你写了多少字，只会记得你让他们感受到了什么。',
  '每章结尾问自己：读者会点下一章吗？',
  '最好的伏笔是读者读第二遍时才发现的。',
  '不要解释。展示。让读者自己发现。',
  '一个让人记住的角色，胜过十个功能性的配角。',
];

let sparkId = 0;

function Sparkline({ data, width, height }: { data: number[]; width: number; height: number }) {
  const id = useMemo(() => `spark-fill-${sparkId++}`, []);
  if (data.length < 2) return null;
  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;
  const padX = 0;
  const padY = 2;
  const w = width - padX * 2;
  const h = height - padY * 2;
  const points = data.map((v, i) => {
    const x = padX + (i / (data.length - 1)) * w;
    const y = padY + h - ((v - min) / range) * h;
    return `${x},${y}`;
  });
  const areaDown = `${points[0].split(',')[0]},${height} ${points.map(p => p).join(' ')} ${points[points.length-1].split(',')[0]},${height}`;
  return (
    <svg width={width} height={height} className="overflow-visible">
      <defs>
        <linearGradient id={id} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="var(--color-accent)" stopOpacity="0.25" />
          <stop offset="100%" stopColor="var(--color-accent)" stopOpacity="0.02" />
        </linearGradient>
      </defs>
      <polygon points={areaDown} fill={`url(#${id})`} />
      <polyline points={points.join(' ')} fill="none" stroke="var(--color-accent)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function WriterStats({ novelId, totalChapters, totalWords, chapters }: {
  novelId: string; totalChapters: number; totalWords: number;
  chapters?: ChapterMeta[];
}) {
  const [goal, setGoal] = useState(() => Number(localStorage.getItem(`goal-${novelId}`)) || 50000);
  const [, ] = useState(() => Number(localStorage.getItem(`day-${novelId}`)) || 0);
  const [inspiration, setInspiration] = useState(INSPIRATIONS[0]);

  useEffect(() => {
    setInspiration(INSPIRATIONS[Math.floor(Math.random() * INSPIRATIONS.length)]);
  }, [novelId]);

  useEffect(() => {
    localStorage.setItem(`goal-${novelId}`, String(goal));
  }, [goal, novelId]);

  const pct = Math.min(100, Math.round((totalWords / goal) * 100));

  // Velocity sparkline data from chapter word counts
  const velocityData = useMemo(() => {
    if (!chapters || chapters.length < 2) return null;
    return chapters.slice(-20).map(c => c.word_count);
  }, [chapters]);

  // Average words per chapter
  const avgWordsPerChapter = totalChapters > 0 ? Math.round(totalWords / totalChapters) : 0;

  // Estimated chapters to goal
  const remainingChapters = avgWordsPerChapter > 0
    ? Math.max(0, Math.ceil((goal - totalWords) / avgWordsPerChapter))
    : Math.max(0, Math.ceil((goal - totalWords) / 2500));

  // Estimated completion date based on writing velocity
  const estimatedCompletion = useMemo(() => {
    if (!velocityData || velocityData.length < 3 || remainingChapters <= 0) return null;
    const dailyAvg = velocityData.reduce((a, b) => a + b, 0) / velocityData.length;
    if (dailyAvg < 100) return null;
    const wordsRemaining = Math.max(0, goal - totalWords);
    const daysNeeded = Math.ceil(wordsRemaining / dailyAvg);
    const estimated = new Date();
    estimated.setDate(estimated.getDate() + daysNeeded);
    return estimated.toLocaleDateString('zh-CN', { month: 'long', day: 'numeric' });
  }, [velocityData, remainingChapters, goal, totalWords]);

  // Writing velocity trend
  const velocityTrend = useMemo(() => {
    if (!velocityData || velocityData.length < 4) return null;
    const half = Math.floor(velocityData.length / 2);
    const recent = velocityData.slice(-half);
    const older = velocityData.slice(0, half);
    const recentAvg = recent.reduce((a, b) => a + b, 0) / recent.length;
    const olderAvg = older.reduce((a, b) => a + b, 0) / older.length;
    if (olderAvg === 0) return null;
    const change = ((recentAvg - olderAvg) / olderAvg) * 100;
    if (change > 10) return { emoji: '🚀', label: '加速', color: 'text-emerald-500' };
    if (change < -10) return { emoji: '🐢', label: '放缓', color: 'text-amber-500' };
    return { emoji: '➡️', label: '稳定', color: 'text-ink-muted' };
  }, [velocityData]);

  return (
    <div className="mb-6 p-4 bg-gradient-to-br from-accent-soft via-card to-paper border border-border rounded-xl">
      {/* Inspiration */}
      <p className="text-xs text-ink-muted italic mb-3 leading-relaxed">
        「{inspiration}」
      </p>

      {/* Goal tracker */}
      <div className="space-y-2">
        <div className="flex justify-between text-[11px]">
          <span className="text-ink-muted">全书进度</span>
          <span className="text-ink tabular-nums font-medium">
            {totalWords.toLocaleString()} / {goal.toLocaleString()} 字
          </span>
        </div>
        <div className="relative h-2.5 bg-border rounded-full overflow-hidden">
          {/* Milestone markers */}
          {[25, 50, 75, 100].map(m => {
            const crossed = pct >= m;
            return (
              <div key={m}
                className={`absolute top-0 w-0.5 h-full transition-all duration-500 ${
                  crossed ? 'bg-white/60' : 'bg-ink/10'
                }`}
                style={{ left: `${m}%` }}
              />
            );
          })}
          <div className={`h-full rounded-full transition-all duration-700 ${
            pct >= 100
              ? 'bg-gradient-to-r from-emerald-400 via-emerald-500 to-emerald-600 animate-[pulse-glow_2s_infinite]'
              : 'bg-accent'
          }`}
            style={{width: `${Math.max(2, pct)}%`}} />
        </div>
        <div className="flex justify-between text-[10px] text-ink-subtle">
          <span className={pct >= 100 ? 'text-emerald-500 font-semibold' : ''}>
            {pct >= 100 ? '🎉 ' : ''}{pct}%
          </span>
          <button onClick={() => setGoal(p => p + 50000)}
            className="hover:text-accent transition-colors">目标 +5万字</button>
        </div>
        {pct >= 100 && (
          <p className="text-[11px] text-emerald-500 font-medium text-center animate-[fadeSlideIn_0.3s_ease-out]">
            🏆 恭喜！已完成目标字数！
          </p>
        )}
      </div>

      {/* Stats row */}
      <div className="flex gap-3 mt-3 pt-3 border-t border-border text-[11px] text-ink-muted flex-wrap">
        <span>{totalChapters} 章</span>
        {totalChapters > 0 && (
          <span>均 {avgWordsPerChapter.toLocaleString()} 字/章</span>
        )}
        <span className="text-ink-subtle">
          还需 {remainingChapters} 章完成
        </span>
        {estimatedCompletion && remainingChapters > 0 && (
          <span className="ml-auto text-emerald-500 font-medium">
            🎯 预计 {estimatedCompletion} 完本
          </span>
        )}
      </div>

      {/* Achievement badges */}
      <div className="flex gap-1 mt-3 pt-3 border-t border-border flex-wrap">
        {[
          { emoji: '🌱', label: '开写', earned: totalWords > 0 },
          { emoji: '📝', label: '1万字', earned: totalWords >= 10000 },
          { emoji: '📖', label: '5万字', earned: totalWords >= 50000 },
          { emoji: '📚', label: '10万字', earned: totalWords >= 100000 },
          { emoji: '🔥', label: '高产', earned: totalChapters >= 20 },
          { emoji: '🏆', label: '达成', earned: pct >= 100 },
        ].map(b => (
          <span key={b.label}
            className={`text-[10px] px-1.5 py-0.5 rounded-full border transition-all ${
              b.earned
                ? 'bg-accent-soft text-accent border-accent/30'
                : 'border-border text-ink-subtle opacity-40'
            }`}
            title={b.earned ? `已解锁: ${b.label}` : `未解锁: ${b.label}`}>
            {b.emoji} {b.label}
          </span>
        ))}
      </div>

      {/* Velocity sparkline + trend */}
      {velocityData && (
        <div className="mt-3 pt-3 border-t border-border">
          <div className="flex items-center justify-between mb-1">
            <span className="text-[10px] text-ink-muted uppercase tracking-wide">写作速率</span>
            {velocityTrend && (
              <span className={`text-[10px] font-medium ${velocityTrend.color}`}>
                {velocityTrend.emoji} {velocityTrend.label}
              </span>
            )}
          </div>
          <div className="flex items-end gap-2">
            <Sparkline data={velocityData} width={180} height={32} />
            <div className="flex-1 text-right">
              <div className="text-[10px] text-ink-subtle">最近{velocityData.length}章</div>
              <div className="text-xs text-ink tabular-nums font-medium">
                {(velocityData.reduce((a, b) => a + b, 0) / velocityData.length).toFixed(0)} 字/章
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
