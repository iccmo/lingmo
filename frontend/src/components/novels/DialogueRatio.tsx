import { useMemo } from 'react';
import type { ChapterMeta } from 'src/types';

interface ChapterDialogueStats {
  chapter: number;
  title: string;
  dialogueChars: number;
  narrationChars: number;
  totalChars: number;
  dialoguePct: number;
  narrationPct: number;
  risk: 'info-dump' | 'talking-heads' | null;
}

interface Props {
  chapters: ChapterMeta[];
  contentMap?: Record<number, string>;
}

/** Count characters inside 「」, "", "", and lines near dialogue markers as dialogue content */
function countDialogue(text: string): number {
  let dialogueChars = 0;

  // Chinese quotation pairs: 「...」
  const cnQuotes = text.match(/「[^」]*」/g);
  if (cnQuotes) {
    for (const m of cnQuotes) {
      dialogueChars += m.length;
    }
  }

  // English double-quote pairs: "..."
  const enQuotes = text.match(/"[^"]*"/g);
  if (enQuotes) {
    for (const m of enQuotes) {
      dialogueChars += m.length;
    }
  }

  // English single-quote pairs: '...'
  const enSingleQuotes = text.match(/'[^']*'/g);
  if (enSingleQuotes) {
    for (const m of enSingleQuotes) {
      dialogueChars += m.length;
    }
  }

  // Chinese double quotes: "..."
  const cnDoubleQuotes = text.match(/“[^”]*”/g);
  if (cnDoubleQuotes) {
    for (const m of cnDoubleQuotes) {
      dialogueChars += m.length;
    }
  }

  // Lines containing dialogue markers (说, 道, 问, 答, 讲, 喊, 叫, 骂, 叹, 喝, 嚷, 呼)
  // Count the surrounding text as potential dialogue
  const dialogueMarkers = /[说问道答讲喊叫骂叹喝嚷呼]/g;
  const lines = text.split('\n');
  for (const line of lines) {
    const markers = line.match(dialogueMarkers);
    if (markers && markers.length > 0) {
      // Count the full line minus 20% (overlap with already-counted quotes)
      dialogueChars += Math.round(line.length * 0.8);
    }
  }

  return Math.min(dialogueChars, text.length);
}

function analyzeChapter(text: string): ChapterDialogueStats['risk'] {
  const dialogueChars = countDialogue(text);
  const total = text.length || 1;
  const dialoguePct = Math.round((dialogueChars / total) * 100);

  if (dialoguePct > 70) return 'talking-heads';
  if (dialoguePct < 20) return 'info-dump';
  return null;
}

function computeStats(
  chapters: ChapterMeta[],
  contentMap?: Record<number, string>,
): ChapterDialogueStats[] {
  return chapters
    .filter((c) => c.word_count > 0)
    .map((ch) => {
      const text = contentMap?.[ch.number] || ch.summary || '';
      const total = text.length || 1;
      const dialogueChars = countDialogue(text);
      const narrationChars = total - dialogueChars;
      const dialoguePct = Math.round((dialogueChars / total) * 100);
      const narrationPct = 100 - dialoguePct;
      const risk = analyzeChapter(text);

      return {
        chapter: ch.number,
        title: ch.title,
        dialogueChars,
        narrationChars,
        totalChars: total,
        dialoguePct,
        narrationPct,
        risk,
      };
    });
}

function riskBadge(risk: ChapterDialogueStats['risk']): {
  text: string;
  color: string;
} | null {
  if (risk === 'info-dump') return { text: '信息倾泻', color: 'text-red-500 dark:text-red-400' };
  if (risk === 'talking-heads')
    return { text: '对话过多', color: 'text-amber-500 dark:text-amber-400' };
  return null;
}

export function DialogueRatio({ chapters, contentMap }: Props) {
  const stats = useMemo(() => computeStats(chapters, contentMap), [chapters, contentMap]);
  const hasContent = contentMap && Object.keys(contentMap).length > 0;

  if (stats.length < 2) return null;

  const avgDialogue = Math.round(
    stats.reduce((s, st) => s + st.dialoguePct, 0) / stats.length,
  );
  const inGoldenRange = avgDialogue >= 30 && avgDialogue <= 50;

  const infoDumps = stats.filter((s) => s.risk === 'info-dump');
  const talkingHeads = stats.filter((s) => s.risk === 'talking-heads');

  const width = 640;
  const height = 160;
  const padL = 44;
  const padR = 16;
  const padT = 12;
  const padB = 28;
  const plotW = width - padL - padR;
  const plotH = height - padT - padB;
  const barGap = 2;

  const barWidth = Math.max(4, (plotW - barGap * (stats.length - 1)) / stats.length);

  return (
    <div className="mb-6 p-4 bg-card border border-border rounded-xl">
      <div className="flex items-center justify-between mb-3">
        <div>
          <h3 className="font-heading text-base font-semibold text-ink">对话/叙述比</h3>
          <p className="text-[11px] text-ink-muted">
            分析每章对话与叙述的比例
          </p>
        </div>
        {!hasContent && (
          <span className="text-[10px] text-ink-subtle bg-paper px-2 py-0.5 rounded border border-border">
            基于章节摘要 — 加载正文以获取精确分析
          </span>
        )}
      </div>

      {/* Golden ratio benchmark */}
      <div
        className={`mb-3 px-3 py-2 rounded-lg text-[11px] border ${
          inGoldenRange
            ? 'bg-emerald-50 dark:bg-emerald-950/20 border-emerald-200 dark:border-emerald-800 text-emerald-700 dark:text-emerald-400'
            : 'bg-amber-50 dark:bg-amber-950/20 border-amber-200 dark:border-amber-800 text-amber-700 dark:text-amber-400'
        }`}
      >
        <span className="font-semibold">黄金对话比：30-50%</span>
        <span className="mx-2">|</span>
        当前平均：<span className="font-semibold tabular-nums">{avgDialogue}%</span>
        {inGoldenRange ? (
          <span className="ml-1">-- 在推荐范围内</span>
        ) : (
          <span className="ml-1">
            -- {avgDialogue < 30 ? '叙述偏多，建议增加对话' : '对话偏多，建议增加叙述'}
          </span>
        )}
      </div>

      {/* Stacked bar chart */}
      <svg width={width} height={height} className="w-full" viewBox={`0 0 ${width} ${height}`}>
        {/* Grid lines */}
        {[0, 25, 50, 75, 100].map((v) => {
          const y = padT + plotH - (v / 100) * plotH;
          return (
            <g key={v}>
              <line
                x1={padL}
                y1={y}
                x2={padL + plotW}
                y2={y}
                stroke="var(--color-border)"
                strokeWidth="0.5"
                strokeDasharray="3,3"
              />
              <text
                x={padL - 5}
                y={y + 3}
                textAnchor="end"
                fill="var(--color-ink-subtle)"
                fontSize="8"
              >
                {v}%
              </text>
            </g>
          );
        })}

        {/* Golden range highlight (30%-50%) */}
        <rect
          x={padL}
          y={padT + plotH - (50 / 100) * plotH}
          width={plotW}
          height={((50 - 30) / 100) * plotH}
          fill="#34D399"
          fillOpacity="0.06"
          rx="2"
        />

        {stats.map((st, i) => {
          const x = padL + i * (barWidth + barGap);
          const dialogueH = (st.dialoguePct / 100) * plotH;
          const narrationH = (st.narrationPct / 100) * plotH;
          const dialogueY = padT + plotH - dialogueH - narrationH;
          const narrationY = padT + plotH - narrationH;

          const badge = riskBadge(st.risk);

          return (
            <g key={st.chapter}>
              {/* Narration bar (bottom) */}
              <rect
                x={x}
                y={narrationY}
                width={barWidth}
                height={Math.max(1, narrationH)}
                fill={st.narrationPct > 80 ? '#F59E0B' : 'var(--color-ink-subtle)'}
                fillOpacity={st.narrationPct > 80 ? 0.7 : 0.35}
                rx="1"
              >
                <title>
                  第{st.chapter}章 叙述 {st.narrationPct}%
                </title>
              </rect>

              {/* Dialogue bar (top) */}
              <rect
                x={x}
                y={dialogueY}
                width={barWidth}
                height={Math.max(1, dialogueH)}
                fill={st.dialoguePct > 70 ? '#EF4444' : 'var(--color-accent)'}
                fillOpacity={st.dialoguePct > 70 ? 0.8 : 0.7}
                rx="1"
              >
                <title>
                  第{st.chapter}章 对话 {st.dialoguePct}%
                </title>
              </rect>

              {/* Risk indicator */}
              {badge && (
                <circle
                  cx={x + barWidth / 2}
                  cy={padT + plotH + 14}
                  r="3"
                  fill={
                    st.risk === 'info-dump'
                      ? '#F59E0B'
                      : '#EF4444'
                  }
                />
              )}

              {/* Chapter label (every ~5th) */}
              {(i % Math.max(1, Math.floor(stats.length / 10)) === 0 ||
                i === stats.length - 1) && (
                <text
                  x={x + barWidth / 2}
                  y={padT + plotH + 20}
                  textAnchor="middle"
                  fill="var(--color-ink-subtle)"
                  fontSize="8"
                >
                  {st.chapter}
                </text>
              )}
            </g>
          );
        })}
      </svg>

      {/* Legend */}
      <div className="flex items-center gap-4 mt-2 text-[10px]">
        <div className="flex items-center gap-1.5">
          <span className="w-3 h-2.5 rounded-sm inline-block bg-accent opacity-70" />
          <span className="text-ink-muted">对话</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span
            className="w-3 h-2.5 rounded-sm inline-block"
            style={{ backgroundColor: 'var(--color-ink-subtle)', opacity: 0.35 }}
          />
          <span className="text-ink-muted">叙述</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="w-2 h-2 rounded-full inline-block bg-amber-500" />
          <span className="text-ink-muted">信息倾泻风险 (&gt;80% 叙述)</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="w-2 h-2 rounded-full inline-block bg-red-500" />
          <span className="text-ink-muted">对话过多 (&gt;70% 对话)</span>
        </div>
      </div>

      {/* Warnings */}
      {(infoDumps.length > 0 || talkingHeads.length > 0) && (
        <div className="mt-3 space-y-1.5">
          {infoDumps.length > 0 && (
            <div className="text-[11px] text-amber-600 dark:text-amber-400 bg-amber-50/50 dark:bg-amber-950/20 border border-amber-200 dark:border-amber-800 rounded-lg px-3 py-2">
              <span className="font-semibold">信息倾泻风险：</span>
              {infoDumps.length} 章叙述超过80%
              <span className="text-ink-subtle ml-1">
                ({infoDumps.map((s) => `Ch${s.chapter}`).join(', ')})
              </span>
              <span className="block text-[10px] mt-0.5 text-ink-muted">
                建议在信息密集章节中加入对话或场景切换，避免连续大段说明
              </span>
            </div>
          )}
          {talkingHeads.length > 0 && (
            <div className="text-[11px] text-red-600 dark:text-red-400 bg-red-50/50 dark:bg-red-950/20 border border-red-200 dark:border-red-800 rounded-lg px-3 py-2">
              <span className="font-semibold">对话过多风险：</span>
              {talkingHeads.length} 章对话超过70%
              <span className="text-ink-subtle ml-1">
                ({talkingHeads.map((s) => `Ch${s.chapter}`).join(', ')})
              </span>
              <span className="block text-[10px] mt-0.5 text-ink-muted">
                建议在对话密集章节中加入环境描写、心理活动，避免&quot;说话头&quot;现象
              </span>
            </div>
          )}
        </div>
      )}

      {/* Per-chapter detail table (collapsible summary) */}
      <details className="mt-3 group">
        <summary className="text-[10px] text-ink-muted cursor-pointer hover:text-ink transition-colors select-none">
          查看各章详情 ({stats.length} 章)
        </summary>
        <div className="mt-2 max-h-40 overflow-y-auto">
          <table className="w-full text-[10px]">
            <thead>
              <tr className="text-ink-subtle border-b border-border">
                <th className="text-left py-1 font-medium">章节</th>
                <th className="text-right py-1 font-medium tabular-nums">对话%</th>
                <th className="text-right py-1 font-medium tabular-nums">叙述%</th>
                <th className="text-center py-1 font-medium">风险</th>
              </tr>
            </thead>
            <tbody>
              {stats.map((st) => {
                const badge = riskBadge(st.risk);
                return (
                  <tr
                    key={st.chapter}
                    className="border-b border-border/50 hover:bg-paper/50 transition-colors"
                  >
                    <td className="py-1 text-ink-subtle">
                      Ch{st.chapter} {st.title}
                    </td>
                    <td
                      className={`py-1 text-right tabular-nums ${
                        st.dialoguePct > 70
                          ? 'text-red-500 font-semibold'
                          : st.dialoguePct >= 30
                            ? 'text-accent'
                            : 'text-ink-muted'
                      }`}
                    >
                      {st.dialoguePct}%
                    </td>
                    <td
                      className={`py-1 text-right tabular-nums ${
                        st.narrationPct > 80
                          ? 'text-amber-500 font-semibold'
                          : 'text-ink-muted'
                      }`}
                    >
                      {st.narrationPct}%
                    </td>
                    <td className="py-1 text-center">
                      {badge ? (
                        <span className={badge.color}>{badge.text}</span>
                      ) : (
                        <span className="text-emerald-500">正常</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </details>
    </div>
  );
}
