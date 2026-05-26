import { useState, useEffect } from 'react';

interface Dimension {
  score: number;
  max: number;
  detail: string;
  issues: string[];
}

interface ConsistencyData {
  score: number;
  max_score: number;
  pct: number;
  grade: string;
  trend: string;
  dimensions: Record<string, Dimension>;
  weakest_dimension: string;
  recommendation: string;
}

const DIM_LABELS: Record<string, string> = {
  character_arc: '角色弧光',
  foreshadowing_health: '伏笔健康',
  plot_continuity: '情节连续',
  world_integrity: '世界完整',
  structural_balance: '结构平衡',
};

const GRADE_COLORS: Record<string, string> = {
  S: 'text-emerald-500 border-emerald-200 bg-emerald-50 dark:bg-emerald-950/20',
  A: 'text-sky-500 border-sky-200 bg-sky-50 dark:bg-sky-950/20',
  B: 'text-amber-500 border-amber-200 bg-amber-50 dark:bg-amber-950/20',
  C: 'text-orange-500 border-orange-200 bg-orange-50 dark:bg-orange-950/20',
  D: 'text-red-500 border-red-200 bg-red-50 dark:bg-red-950/20',
};

const TREND_ICONS: Record<string, string> = {
  improving: '📈',
  declining: '📉',
  stable: '➡️',
  insufficient_data: '…',
};

interface Props { novelId: string }

export function ConsistencyScoreView({ novelId }: Props) {
  const [data, setData] = useState<ConsistencyData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`/api/novels/${novelId}/consistency-score`)
      .then(r => r.json())
      .then(setData)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [novelId]);

  if (loading) return <div className="skeleton h-16 rounded-lg" />;
  if (!data) return <p className="text-xs text-ink-subtle py-2">暂无一致性数据</p>;

  return (
    <div className="space-y-3">
      {/* Overall Grade */}
      <div className={`flex items-center justify-between p-2 rounded-lg border ${GRADE_COLORS[data.grade] || GRADE_COLORS.B}`}>
        <div className="flex items-center gap-2">
          <span className="text-2xl font-bold">{data.grade}</span>
          <div>
            <div className="text-xs font-medium text-ink">
              {data.score}/{data.max_score} ({Math.round(data.pct * 100)}%)
            </div>
            <div className="text-[10px] text-ink-subtle">
              {TREND_ICONS[data.trend] || ''} {data.trend}
            </div>
          </div>
        </div>
        <div className="text-[10px] text-ink-subtle text-right max-w-[180px]">
          {data.recommendation}
        </div>
      </div>

      {/* Dimension Bars */}
      <div className="space-y-1.5">
        {Object.entries(data.dimensions).map(([key, dim]) => {
          const pct = dim.max > 0 ? (dim.score / dim.max) * 100 : 0;
          const barColor =
            pct >= 80 ? 'bg-emerald-500' :
            pct >= 60 ? 'bg-sky-500' :
            pct >= 40 ? 'bg-amber-500' : 'bg-red-500';
          const isWeakest = key === data.weakest_dimension;

          return (
            <div key={key}>
              <div className="flex items-center justify-between text-[10px] mb-0.5">
                <span className={`text-ink-subtle ${isWeakest ? 'font-semibold text-amber-500' : ''}`}>
                  {DIM_LABELS[key] || key}
                  {isWeakest && ' ⚠️'}
                </span>
                <span className="text-ink-muted font-mono">
                  {dim.score}/{dim.max}
                </span>
              </div>
              <div className="h-1.5 bg-paper rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all ${barColor}`}
                  style={{ width: `${Math.max(2, pct)}%` }}
                />
              </div>
              {dim.issues.length > 0 && (
                <div className="mt-0.5 space-y-0.5">
                  {dim.issues.map((issue, i) => (
                    <p key={i} className="text-[9px] text-ink-subtle pl-1 border-l-2 border-amber-300 dark:border-amber-700">
                      {issue}
                    </p>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
