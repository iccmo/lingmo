import { useMemo } from 'react';
import type { ChapterMeta } from 'src/types';

interface ArcPoint {
  chapter: number;
  tension: number;    // 0-100
  hook: number;       // 0-100 (ending strength)
  quality?: number;   // 0-1 raw
  label: string;
}

function computeArcPoints(chapters: ChapterMeta[]): ArcPoint[] {
  const withContent = chapters.filter(c => c.word_count > 0);
  if (withContent.length < 2) return [];

  return withContent.map((ch, i) => {
    // Tension composite: quality score (60%) + position factor (25%) + word count factor (15%)
    const qualityNorm = ch.quality_score ? ch.quality_score * 100 : 50;
    const positionFactor = withContent.length > 1 ? (i / (withContent.length - 1)) * 35 : 0; // Later chapters get higher base
    const wordFactor = Math.min(25, (ch.word_count / 5000) * 25);
    const tension = Math.min(100, Math.round(qualityNorm * 0.6 + positionFactor + wordFactor));

    // Hook strength from ending_hook field
    let hook = 50;
    if (ch.ending_hook) {
      const h = ch.ending_hook.toLowerCase();
      if (h.includes('悬念') || h.includes('反转') || h.includes('危机')) hook = 85;
      else if (h.includes('冲突') || h.includes('伏笔') || h.includes('秘密')) hook = 70;
      else if (h.includes('期待') || h.includes('疑问') || h.includes('抉择')) hook = 60;
      else hook = 45;
    }

    // Label for peaks/valleys
    let label = '';
    if (i > 0) {
      const prev = withContent[i - 1];
      const prevT = computeSingleTension(prev, i - 1, withContent.length);
      if (tension - prevT > 20) label = '↗ 高潮';
      else if (prevT - tension > 20) label = '↘ 过渡';
    }

    return { chapter: ch.number, tension, hook, quality: ch.quality_score, label };
  });
}

function computeSingleTension(ch: ChapterMeta, i: number, total: number): number {
  const qualityNorm = ch.quality_score ? ch.quality_score * 100 : 50;
  const positionFactor = total > 1 ? (i / (total - 1)) * 35 : 0;
  const wordFactor = Math.min(25, (ch.word_count / 5000) * 25);
  return Math.min(100, Math.round(qualityNorm * 0.6 + positionFactor + wordFactor));
}

function hookLabel(strength: number): { emoji: string; text: string; color: string } {
  if (strength >= 80) return { emoji: '🎣', text: '强力钩子', color: 'text-emerald-500' };
  if (strength >= 60) return { emoji: '🔗', text: '中等钩子', color: 'text-sky-500' };
  if (strength >= 40) return { emoji: '📌', text: '弱钩子', color: 'text-amber-500' };
  return { emoji: '⚠️', text: '无钩子', color: 'text-red-500' };
}

export function EmotionalArc({ chapters }: { chapters?: ChapterMeta[] }) {
  const points = useMemo(() => chapters ? computeArcPoints(chapters) : [], [chapters]);

  if (points.length < 2) return null;

  const width = 640;
  const height = 200;
  const padL = 40;
  const padR = 20;
  const padT = 15;
  const padB = 30;
  const plotW = width - padL - padR;
  const plotH = height - padT - padB;

  const maxTension = Math.max(...points.map(p => p.tension), 100);

  // Build SVG paths
  const tensionPoints = points.map((p, i) => {
    const x = padL + (i / (points.length - 1)) * plotW;
    const y = padT + plotH - (p.tension / maxTension) * plotH;
    return `${x},${y}`;
  });

  const hookPoints = points.map((p, i) => {
    const x = padL + (i / (points.length - 1)) * plotW;
    const y = padT + plotH - (p.hook / 100) * plotH;
    return `${x},${y}`;
  });

  const tensionPath = tensionPoints.join(' ');
  const hookPath = hookPoints.join(' ');

  // Area fill under tension curve
  const areaPath = `${padL},${padT + plotH} ${tensionPoints.join(' ')} ${padL + plotW},${padT + plotH}`;

  // Average stats
  const avgTension = Math.round(points.reduce((s, p) => s + p.tension, 0) / points.length);
  const avgHook = Math.round(points.reduce((s, p) => s + p.hook, 0) / points.length);
  const weakHooks = points.filter(p => p.hook < 40);

  return (
    <div className="mb-6 p-4 bg-card border border-border rounded-xl">
      <div className="flex items-center justify-between mb-3">
        <div>
          <h3 className="font-heading text-base font-semibold text-ink">情感弧线</h3>
          <p className="text-[11px] text-ink-muted">章节张力与结尾钩子强度</p>
        </div>
        <div className="flex gap-3 text-[10px]">
          <div className="flex items-center gap-1">
            <span className="w-3 h-0.5 rounded-full bg-accent inline-block" />
            <span className="text-ink-muted">张力</span>
          </div>
          <div className="flex items-center gap-1">
            <span className="w-3 h-0.5 rounded-full bg-emerald-400 inline-block" style={{ borderTop: '2px dotted #34D399' }} />
            <span className="text-ink-muted">钩子</span>
          </div>
        </div>
      </div>

      {/* SVG Chart */}
      <svg width={width} height={height} className="w-full" viewBox={`0 0 ${width} ${height}`}>
        {/* Grid lines */}
        {[0, 25, 50, 75, 100].map(v => {
          const y = padT + plotH - (v / 100) * plotH;
          return (
            <g key={v}>
              <line x1={padL} y1={y} x2={padL + plotW} y2={y}
                stroke="var(--color-border)" strokeWidth="0.5" strokeDasharray="3,3" />
              <text x={padL - 5} y={y + 3} textAnchor="end"
                fill="var(--color-ink-subtle)" fontSize="8">{v}</text>
            </g>
          );
        })}

        {/* Area fill */}
        <path d={areaPath} fill="var(--color-accent)" fillOpacity="0.06" />

        {/* Tension line */}
        <polyline points={tensionPath} fill="none"
          stroke="var(--color-accent)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />

        {/* Hook line — dotted */}
        <polyline points={hookPath} fill="none"
          stroke="#34D399" strokeWidth="1.5" strokeDasharray="4,3" strokeLinecap="round" strokeLinejoin="round" />

        {/* Data points */}
        {points.map((p, i) => {
          const x = padL + (i / (points.length - 1)) * plotW;
          const y = padT + plotH - (p.tension / maxTension) * plotH;
          const isPeak = p.label.includes('高潮');
          const isValley = p.label.includes('过渡');
          return (
            <g key={i}>
              {/* Tension dot */}
              <circle cx={x} cy={y} r={isPeak ? 4 : isValley ? 3 : 2.5}
                fill={isPeak ? 'var(--color-accent)' : isValley ? 'var(--color-ink-subtle)' : 'var(--color-accent)'}
                stroke="var(--color-card)" strokeWidth="1.5" />

              {/* Weak hook indicator */}
              {p.hook < 40 && (
                <circle cx={x} cy={padT + plotH - (p.hook / 100) * plotH} r="4"
                  fill="none" stroke="#F59E0B" strokeWidth="1.5" opacity="0.8" />
              )}

              {/* Chapter label (every ~5th) */}
              {(i % Math.max(1, Math.floor(points.length / 8)) === 0 || i === points.length - 1) && (
                <text x={x} y={padT + plotH + 16} textAnchor="middle"
                  fill="var(--color-ink-subtle)" fontSize="9">Ch{p.chapter}</text>
              )}

              {/* Peak/valley label */}
              {p.label && isPeak && (
                <text x={x} y={y - 10} textAnchor="middle"
                  fill="var(--color-accent)" fontSize="8" fontWeight="600">{p.label}</text>
              )}
            </g>
          );
        })}
      </svg>

      {/* Stats row */}
      <div className="flex gap-5 mt-2 pt-3 border-t border-border text-[11px]">
        <span className="text-ink-muted">
          平均张力 <span className="text-ink font-semibold">{avgTension}</span>
        </span>
        <span className="text-ink-muted">
          平均钩子 <span className="text-ink font-semibold">{avgHook}</span>
        </span>
        {weakHooks.length > 0 && (
          <span className="text-amber-500">
            ⚠️ {weakHooks.length} 章钩子偏弱
            <span className="text-ink-subtle ml-1">
              ({weakHooks.map(p => `Ch${p.chapter}`).join(', ')})
            </span>
          </span>
        )}
      </div>

      {/* Hook detail list */}
      <div className="mt-3 grid grid-cols-2 gap-1.5">
        {points.slice(-6).map(p => {
          const h = hookLabel(p.hook);
          return (
            <div key={p.chapter} className="flex items-center gap-2 text-[10px]">
              <span className="text-ink-subtle tabular-nums w-10">Ch{p.chapter}</span>
              <span className={h.color}>{h.emoji} {h.text}</span>
              {p.hook < 40 && (
                <span className="text-ink-subtle">— 读者可能流失</span>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
