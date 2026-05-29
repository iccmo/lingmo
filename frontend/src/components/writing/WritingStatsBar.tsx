import { BarChart3, Target, Clock } from 'lucide-react';
import type { WritingStats } from 'src/hooks/useWritingStats';

interface Props {
  stats: WritingStats;
  className?: string;
}

export function WritingStatsBar({ stats, className = '' }: Props) {
  const progress = stats.dailyTarget > 0
    ? Math.min((stats.dailyProgress / stats.dailyTarget) * 100, 100)
    : 0;

  return (
    <div className={`
      fixed bottom-4 left-1/2 -translate-x-1/2 z-50
      bg-bg-surface/80 backdrop-blur-sm
      border border-border-default rounded-lg
      px-6 py-3 shadow-default
      ${className}
    `}>
      <div className="flex items-center gap-6 text-sm">
        <div className="flex items-center gap-2">
          <BarChart3 size={14} className="text-text-muted" />
          <span className="text-text-muted">字数</span>
          <span className="text-text-primary font-mono">
            {stats.currentWords.toLocaleString()}
          </span>
        </div>

        <div className="flex items-center gap-2">
          <Target size={14} className="text-text-muted" />
          <span className="text-text-muted">速度</span>
          <span className="text-text-primary font-mono">
            {stats.wordsPerHour.toLocaleString()}字/时
          </span>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-text-muted">目标</span>
          <div className="w-24 h-2 bg-bg-raised rounded-full overflow-hidden">
            <div
              className="h-full bg-brand-primary transition-all duration-300"
              style={{ width: `${progress}%` }}
            />
          </div>
          <span className="text-text-primary font-mono text-xs">
            {Math.round(progress)}%
          </span>
        </div>

        {stats.sessionDuration > 0 && (
          <div className="flex items-center gap-2">
            <Clock size={14} className="text-text-muted" />
            <span className="text-text-muted">时长</span>
            <span className="text-text-primary font-mono">
              {stats.sessionDuration}分钟
            </span>
          </div>
        )}
      </div>
    </div>
  );
}
