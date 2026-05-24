import { useMemo } from 'react';
import type { ChapterMeta } from 'src/types';

interface PacingPoint {
  chapter: number;
  title: string;
  score: number; // 0-100, 0=slow/descriptive, 100=fast/action
  wordCount: number;
  avgParagraphLen: number;
  actionDensity: number;
  descriptionDensity: number;
  dialogueRatio: number;
  color: 'green' | 'blue' | 'red';
  abruptChange: boolean; // >30 point swing from previous
}

interface Props {
  chapters: ChapterMeta[];
  contentMap?: Record<number, string>;
}

const ACTION_WORDS = /[打杀冲跑战飞破爆斩刺劈砍击射轰震裂碎崩穿跃扑挥撞掀撕]|动手|出手|爆发|冲刺|疾驰/g;
const DESCRIPTION_WORDS = /[慢静思想忆看望顾观瞧瞅瞥凝注沉默久徘徊踌躇悠缓]|缓缓|慢慢|静静|默默|良久|许久/g;

function countMatches(text: string, pattern: RegExp): number {
  const matches = text.match(pattern);
  return matches ? matches.length : 0;
}

function countDialogueChars(text: string): number {
  let chars = 0;
  const cnQuotes = text.match(/「[^」]*」/g);
  if (cnQuotes) for (const m of cnQuotes) chars += m.length;
  const enQuotes = text.match(/"[^"]*"/g);
  if (enQuotes) for (const m of enQuotes) chars += m.length;
  const enSingleQuotes = text.match(/'[^']*'/g);
  if (enSingleQuotes) for (const m of enSingleQuotes) chars += m.length;
  const cnDoubleQuotes = text.match(/"[^"]*"/g);
  if (cnDoubleQuotes) for (const m of cnDoubleQuotes) chars += m.length;
  return Math.min(chars, text.length);
}

function avgParagraphLen(text: string): number {
  const paragraphs = text.split(/\n+/).filter((p) => p.trim().length > 0);
  if (paragraphs.length === 0) return 0;
  return paragraphs.reduce((s, p) => s + p.length, 0) / paragraphs.length;
}

function calculatePacingScore(
  text: string,
  wordCount: number,
): {
  score: number;
  actionDensity: number;
  descriptionDensity: number;
  avgParaLen: number;
  dialogueRatio: number;
} {
  const len = text.length || 1;

  // 1. Word count factor: shorter chapters = faster pace (normalized around 3000 chars)
  const wordFactor = Math.max(0, Math.min(1, 1 - (wordCount - 1000) / 8000));

  // 2. Dialogue ratio: more dialogue = faster pace
  const dialogueChars = countDialogueChars(text);
  const dialogueRatio = Math.round((dialogueChars / len) * 100);
  const dialogueFactor = Math.min(1, dialogueRatio / 60);

  // 3. Paragraph length: shorter = faster (normalized around 100 chars per para)
  const avgParaLen = avgParagraphLen(text);
  const paraLenFactor = avgParaLen > 0
    ? Math.max(0, Math.min(1, 1 - (avgParaLen - 30) / 300))
    : 0.5;

  // 4. Action words density (per 100 chars)
  const actionCount = countMatches(text, ACTION_WORDS);
  const actionDensity = (actionCount / len) * 100;

  // Cap action density and normalize to 0-1
  const actionFactor = Math.min(1, actionDensity / 3); // 3 action words per 100 chars = max

  // 5. Description words density (per 100 chars)
  const descCount = countMatches(text, DESCRIPTION_WORDS);
  const descriptionDensity = (descCount / len) * 100;
  const descFactor = Math.min(1, descriptionDensity / 2); // 2 desc words per 100 chars = max

  // Composite score: weighted blend
  // Action and dialogue speed things up; description and long paragraphs slow things down
  const rawScore =
    wordFactor * 0.15 +
    dialogueFactor * 0.25 +
    paraLenFactor * 0.20 +
    actionFactor * 0.30 -
    descFactor * 0.10;

  // Convert to 0-100 range
  const score = Math.max(0, Math.min(100, Math.round(rawScore * 100)));

  return {
    score,
    actionDensity: Math.round(actionDensity * 10) / 10,
    descriptionDensity: Math.round(descriptionDensity * 10) / 10,
    avgParaLen: Math.round(avgParaLen),
    dialogueRatio,
  };
}

function computePacingPoints(
  chapters: ChapterMeta[],
  contentMap?: Record<number, string>,
): PacingPoint[] {
  const withContent = chapters.filter((c) => c.word_count > 0);
  if (withContent.length < 2) return [];

  const points: PacingPoint[] = [];

  for (let i = 0; i < withContent.length; i++) {
    const ch = withContent[i];
    const text = contentMap?.[ch.number] || ch.summary || '';

    const pacing = text.length > 0
      ? calculatePacingScore(text, ch.word_count)
      : {
          score: 50,
          actionDensity: 0,
          descriptionDensity: 0,
          avgParaLen: 0,
          dialogueRatio: 0,
        };

    let color: PacingPoint['color'] = 'green';
    if (pacing.score < 30) color = 'blue';
    else if (pacing.score > 70) color = 'red';

    let abruptChange = false;
    if (i > 0) {
      const prev = points[i - 1];
      if (Math.abs(pacing.score - prev.score) > 30) {
        abruptChange = true;
      }
    }

    points.push({
      chapter: ch.number,
      title: ch.title,
      score: pacing.score,
      wordCount: ch.word_count,
      avgParagraphLen: pacing.avgParaLen,
      actionDensity: pacing.actionDensity,
      descriptionDensity: pacing.descriptionDensity,
      dialogueRatio: pacing.dialogueRatio,
      color,
      abruptChange,
    });
  }

  return points;
}

function paceLabel(score: number): { label: string; color: string } {
  if (score < 30) return { label: '慢节奏', color: 'text-sky-500 dark:text-sky-400' };
  if (score > 70) return { label: '快节奏', color: 'text-red-500 dark:text-red-400' };
  return { label: '适中', color: 'text-emerald-500 dark:text-emerald-400' };
}

export function PacingCurve({ chapters, contentMap }: Props) {
  const points = useMemo(
    () => computePacingPoints(chapters, contentMap),
    [chapters, contentMap],
  );
  const hasContent = contentMap && Object.keys(contentMap).length > 0;

  if (points.length < 2) return null;

  const width = 640;
  const height = 220;
  const padL = 44;
  const padR = 16;
  const padT = 20;
  const padB = 32;
  const plotW = width - padL - padR;
  const plotH = height - padT - padB;

  const avgScore = Math.round(points.reduce((s, p) => s + p.score, 0) / points.length);
  const abruptChanges = points.filter((p) => p.abruptChange);
  const avgPaceInfo = paceLabel(avgScore);

  // Build SVG polyline points
  const linePoints = points.map((p, i) => {
    const x = padL + (i / (points.length - 1)) * plotW;
    const y = padT + plotH - (p.score / 100) * plotH;
    return `${x},${y}`;
  });

  // Area fill
  const areaPath = `${padL},${padT + plotH} ${linePoints.join(' ')} ${padL + plotW},${padT + plotH}`;

  return (
    <div className="mb-6 p-4 bg-card border border-border rounded-xl">
      <div className="flex items-center justify-between mb-3">
        <div>
          <h3 className="font-heading text-base font-semibold text-ink">节奏张力曲线</h3>
          <p className="text-[11px] text-ink-muted">
            综合词数、对话比、段落长度、动作/描写词密度
          </p>
        </div>
        <div className="flex items-center gap-2 text-[10px]">
          <span className={`font-semibold ${avgPaceInfo.color}`}>
            {avgPaceInfo.label} ({avgScore})
          </span>
          {!hasContent && (
            <span className="text-ink-subtle bg-paper px-2 py-0.5 rounded border border-border">
              基于章节摘要
            </span>
          )}
        </div>
      </div>

      {/* Color zone legend */}
      <div className="flex gap-4 mb-3 text-[10px]">
        <div className="flex items-center gap-1.5">
          <span className="w-3 h-1.5 rounded-full inline-block bg-sky-400" />
          <span className="text-ink-muted">&lt;30 偏慢</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="w-3 h-1.5 rounded-full inline-block bg-emerald-400" />
          <span className="text-ink-muted">30-70 适中</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="w-3 h-1.5 rounded-full inline-block bg-red-400" />
          <span className="text-ink-muted">&gt;70 偏快</span>
        </div>
        {abruptChanges.length > 0 && (
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full inline-block border-2 border-amber-400 dark:border-amber-500" />
            <span className="text-amber-600 dark:text-amber-400 font-medium">
              节奏突变 ×{abruptChanges.length}
            </span>
          </div>
        )}
      </div>

      {/* SVG Chart */}
      <svg width={width} height={height} className="w-full" viewBox={`0 0 ${width} ${height}`}>
        {/* Zone backgrounds */}
        {/* Red zone (>70) */}
        <rect
          x={padL}
          y={padT}
          width={plotW}
          height={(30 / 100) * plotH}
          fill="#EF4444"
          fillOpacity="0.04"
        />
        {/* Blue zone (<30) */}
        <rect
          x={padL}
          y={padT + (70 / 100) * plotH}
          width={plotW}
          height={(30 / 100) * plotH}
          fill="#38BDF8"
          fillOpacity="0.04"
        />
        {/* Green zone (30-70) */}
        <rect
          x={padL}
          y={padT + (30 / 100) * plotH}
          width={plotW}
          height={(40 / 100) * plotH}
          fill="#34D399"
          fillOpacity="0.03"
        />

        {/* Grid lines */}
        {[0, 25, 50, 75, 100].map((v) => {
          const y = padT + plotH - (v / 100) * plotH;
          const isZone = v === 30 || v === 70;
          return (
            <g key={v}>
              <line
                x1={padL}
                y1={y}
                x2={padL + plotW}
                y2={y}
                stroke={isZone ? 'var(--color-border)' : 'var(--color-border)'}
                strokeWidth={isZone ? '1' : '0.5'}
                strokeDasharray={isZone ? '6,2' : '3,3'}
                opacity={isZone ? 0.6 : 0.4}
              />
              <text
                x={padL - 5}
                y={y + 3}
                textAnchor="end"
                fill="var(--color-ink-subtle)"
                fontSize="8"
              >
                {v}
              </text>
              {isZone && (
                <text
                  x={padL + plotW + 2}
                  y={y + 3}
                  textAnchor="start"
                  fill="var(--color-ink-subtle)"
                  fontSize="7"
                >
                  {v === 30 ? '慢' : '快'}
                </text>
              )}
            </g>
          );
        })}

        {/* Area fill */}
        <path d={areaPath} fill="var(--color-accent)" fillOpacity="0.05" />

        {/* Main line */}
        <polyline
          points={linePoints.join(' ')}
          fill="none"
          stroke="var(--color-accent)"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />

        {/* Data points */}
        {points.map((p, i) => {
          const x = padL + (i / (points.length - 1)) * plotW;
          const y = padT + plotH - (p.score / 100) * plotH;

          const dotColor =
            p.color === 'red'
              ? '#EF4444'
              : p.color === 'blue'
                ? '#38BDF8'
                : '#34D399';

          return (
            <g key={i}>
              {/* Main dot */}
              <circle
                cx={x}
                cy={y}
                r={p.abruptChange ? 5 : p.score > 70 || p.score < 30 ? 3.5 : 2.5}
                fill={dotColor}
                stroke="var(--color-card)"
                strokeWidth={p.abruptChange ? 2 : 1.5}
              />

              {/* Abrupt change ring */}
              {p.abruptChange && (
                <circle
                  cx={x}
                  cy={y}
                  r="7"
                  fill="none"
                  stroke="#F59E0B"
                  strokeWidth="1.5"
                  strokeDasharray="3,2"
                >
                  <title>节奏突变 Ch{p.chapter}: {p.score}分</title>
                </circle>
              )}

              {/* Abrupt change label */}
              {p.abruptChange && (
                <text
                  x={x}
                  y={y - 10}
                  textAnchor="middle"
                  fill="#F59E0B"
                  fontSize="8"
                  fontWeight="600"
                >
                  节奏突变
                </text>
              )}

              {/* Chapter label */}
              {(i % Math.max(1, Math.floor(points.length / 10)) === 0 ||
                i === points.length - 1) && (
                <text
                  x={x}
                  y={padT + plotH + 18}
                  textAnchor="middle"
                  fill="var(--color-ink-subtle)"
                  fontSize="8"
                >
                  Ch{p.chapter}
                </text>
              )}
            </g>
          );
        })}
      </svg>

      {/* Summary stats */}
      <div className="flex gap-5 mt-2 pt-3 border-t border-border text-[11px]">
        <span className="text-ink-muted">
          平均节奏{' '}
          <span className={`font-semibold tabular-nums ${avgPaceInfo.color}`}>
            {avgScore}
          </span>
        </span>
        {abruptChanges.length > 0 && (
          <span className="text-amber-600 dark:text-amber-400 font-medium">
            节奏突变 {abruptChanges.length} 处
            <span className="text-ink-subtle ml-1 font-normal">
              ({abruptChanges.map((p) => `Ch${p.chapter}`).join(', ')})
            </span>
          </span>
        )}
      </div>

      {/* Abrupt changes detail */}
      {abruptChanges.length > 0 && (
        <div className="mt-3 p-3 rounded-lg bg-amber-50/50 dark:bg-amber-950/20 border border-amber-200 dark:border-amber-800">
          <p className="text-[11px] font-semibold text-amber-700 dark:text-amber-400 mb-2">
            节奏突变章节详情
          </p>
          <div className="grid grid-cols-2 gap-1.5">
            {abruptChanges.map((p) => (
              <div
                key={p.chapter}
                className="flex items-center gap-2 text-[10px] p-1.5 rounded bg-card/50 border border-border/50"
              >
                <span className="text-ink-subtle tabular-nums w-10">Ch{p.chapter}</span>
                <span className={`font-semibold tabular-nums ${paceLabel(p.score).color}`}>
                  {p.score}
                </span>
                <span className="text-ink-muted">
                  {p.score > 70 ? '爆发' : p.score < 30 ? '沉淀' : ''}
                </span>
                {p.wordCount > 0 && (
                  <span className="text-ink-subtle ml-auto tabular-nums">
                    {p.wordCount.toLocaleString()}字
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Per-chapter detail table */}
      <details className="mt-3 group">
        <summary className="text-[10px] text-ink-muted cursor-pointer hover:text-ink transition-colors select-none">
          查看各章节奏详情 ({points.length} 章)
        </summary>
        <div className="mt-2 max-h-40 overflow-y-auto">
          <table className="w-full text-[10px]">
            <thead>
              <tr className="text-ink-subtle border-b border-border">
                <th className="text-left py-1 font-medium">章节</th>
                <th className="text-right py-1 font-medium tabular-nums">节奏</th>
                <th className="text-right py-1 font-medium tabular-nums">动作密度</th>
                <th className="text-right py-1 font-medium tabular-nums">描写密度</th>
                <th className="text-right py-1 font-medium tabular-nums">段落均长</th>
              </tr>
            </thead>
            <tbody>
              {points.map((p) => (
                <tr
                  key={p.chapter}
                  className="border-b border-border/50 hover:bg-paper/50 transition-colors"
                >
                  <td className="py-1 text-ink-subtle">
                    Ch{p.chapter} {p.title}
                  </td>
                  <td
                    className={`py-1 text-right tabular-nums font-semibold ${
                      paceLabel(p.score).color
                    }`}
                  >
                    {p.score}
                    {p.abruptChange && (
                      <span className="ml-1 text-amber-500" title="节奏突变">
                        !
                      </span>
                    )}
                  </td>
                  <td className="py-1 text-right tabular-nums text-ink-muted">
                    {p.actionDensity > 0 ? `${p.actionDensity}/100字` : '--'}
                  </td>
                  <td className="py-1 text-right tabular-nums text-ink-muted">
                    {p.descriptionDensity > 0
                      ? `${p.descriptionDensity}/100字`
                      : '--'}
                  </td>
                  <td className="py-1 text-right tabular-nums text-ink-muted">
                    {p.avgParagraphLen > 0 ? `${p.avgParagraphLen}字` : '--'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </div>
  );
}
