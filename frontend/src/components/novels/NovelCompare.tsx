import { useState, useEffect, useMemo } from 'react';
import { api } from 'src/lib/api';
import { toast } from 'sonner';
import type { NovelSummary, NovelDetail } from 'src/types';

interface CompareData {
  novel: NovelDetail;
  avgQuality: number;
  chapterWordCounts: { number: number; words: number }[];
}

function formatTime(dateStr: string | undefined): string {
  if (!dateStr) return '--';
  try {
    const d = new Date(dateStr + 'Z');
    return d.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
  } catch {
    return dateStr.slice(0, 16);
  }
}

/* ─── Simple SVG bar chart comparing chapter word counts ─── */
function ChapterCountBars({ a, b, titleA, titleB }: {
  a: { number: number; words: number }[];
  b: { number: number; words: number }[];
  titleA: string;
  titleB: string;
}) {
  const allNumbers = [...new Set([...a.map(c => c.number), ...b.map(c => c.number)])].sort((x, y) => x - y);
  if (allNumbers.length === 0) return <p className="text-xs text-ink-subtle">暂无章节数据</p>;

  const maxWords = Math.max(
    ...a.map(c => c.words),
    ...b.map(c => c.words),
    1
  );

  // Show up to 30 chapters to avoid overcrowding
  const displayChapters = allNumbers.slice(0, 30);
  const barWidth = Math.max(4, Math.floor(600 / displayChapters.length) - 2);
  const chartWidth = Math.max(300, displayChapters.length * (barWidth + 2) + 60);
  const chartHeight = 180;

  return (
    <div className="overflow-x-auto">
      <svg width={chartWidth} height={chartHeight} className="text-[10px]">
        {/* Y-axis labels */}
        <text x={0} y={14} fill="currentColor" className="text-ink-subtle" fontSize="9">{maxWords.toLocaleString()}</text>
        <text x={0} y={chartHeight - 8} fill="currentColor" className="text-ink-subtle" fontSize="9">0</text>

        {/* Bars for novel A */}
        {displayChapters.map((num, i) => {
          const entryA = a.find(c => c.number === num);
          const hA = entryA ? (entryA.words / maxWords) * (chartHeight - 40) : 0;
          const x = 40 + i * (barWidth + 2);
          return (
            <g key={`a-${num}`}>
              <rect
                x={x} y={chartHeight - 20 - hA}
                width={barWidth} height={Math.max(hA, 0.5)}
                fill="var(--color-accent)" rx="1"
                opacity={0.85}
              >
                <title>{titleA} 第{num}章: {entryA?.words || 0} 字</title>
              </rect>
            </g>
          );
        })}

        {/* Bars for novel B */}
        {displayChapters.map((num, i) => {
          const entryB = b.find(c => c.number === num);
          const hB = entryB ? (entryB.words / maxWords) * (chartHeight - 40) : 0;
          const x = 40 + i * (barWidth + 2);
          return (
            <g key={`b-${num}`}>
              <rect
                x={x + barWidth / 2 + 0.5} y={chartHeight - 20 - hB}
                width={Math.max(barWidth / 2 - 0.5, 1)} height={Math.max(hB, 0.5)}
                fill="var(--color-emerald-500, #10b981)" rx="1"
                opacity={0.75}
              >
                <title>{titleB} 第{num}章: {entryB?.words || 0} 字</title>
              </rect>
            </g>
          );
        })}

        {/* X-axis chapter labels (every 5th) */}
        {displayChapters.map((num, i) => {
          if (i % 5 !== 0 && i !== displayChapters.length - 1) return null;
          const x = 40 + i * (barWidth + 2) + barWidth / 2;
          return (
            <text key={`label-${num}`} x={x} y={chartHeight - 2} fill="currentColor"
              className="text-ink-subtle" fontSize="8" textAnchor="middle">{num}</text>
          );
        })}

        {/* Legend */}
        <rect x={40} y={chartHeight - 18} width={8} height={8} fill="var(--color-accent)" rx="1" opacity={0.85} />
        <text x={52} y={chartHeight - 10} fill="currentColor" className="text-ink-subtle" fontSize="8">{titleA.slice(0, 8)}</text>
        <rect x={40 + (titleA.slice(0, 8).length * 5 + 40)} y={chartHeight - 18} width={8} height={8} fill="var(--color-emerald-500, #10b981)" rx="1" opacity={0.75} />
        <text x={40 + (titleA.slice(0, 8).length * 5 + 52)} y={chartHeight - 10} fill="currentColor" className="text-ink-subtle" fontSize="8">{titleB.slice(0, 8)}</text>
      </svg>
    </div>
  );
}

export function NovelCompare({ novels, onClose }: {
  novels: NovelSummary[];
  onClose: () => void;
}) {
  const [leftId, setLeftId] = useState('');
  const [rightId, setRightId] = useState('');
  const [leftData, setLeftData] = useState<CompareData | null>(null);
  const [rightData, setRightData] = useState<CompareData | null>(null);
  const [loading, setLoading] = useState(false);

  // Auto-select first two novels if available
  useEffect(() => {
    if (novels.length >= 2 && !leftId && !rightId) {
      setLeftId(novels[0].id);
      setRightId(novels[1].id);
    }
  }, [novels]);

  useEffect(() => {
    if (!leftId || !rightId) return;
    setLoading(true);
    Promise.all([
      api.novels.get(leftId).catch(() => null),
      api.novels.get(rightId).catch(() => null),
    ]).then(([l, r]) => {
      if (l) {
        const genChs = l.chapters?.filter(c => c.word_count > 0) || [];
        const scores = genChs.map(c => c.quality_score || 0).filter(s => s > 0);
        setLeftData({
          novel: l,
          avgQuality: scores.length ? +(scores.reduce((a, b) => a + b, 0) / scores.length).toFixed(2) : 0,
          chapterWordCounts: genChs.map(c => ({ number: c.number, words: c.word_count })),
        });
      }
      if (r) {
        const genChs = r.chapters?.filter(c => c.word_count > 0) || [];
        const scores = genChs.map(c => c.quality_score || 0).filter(s => s > 0);
        setRightData({
          novel: r,
          avgQuality: scores.length ? +(scores.reduce((a, b) => a + b, 0) / scores.length).toFixed(2) : 0,
          chapterWordCounts: genChs.map(c => ({ number: c.number, words: c.word_count })),
        });
      }
      setLoading(false);
    }).catch(() => {
      toast.error('加载对比数据失败');
      setLoading(false);
    });
  }, [leftId, rightId]);

  const statRows = useMemo(() => {
    if (!leftData && !rightData) return [];
    const rows: { label: string; left: string; right: string; highlight?: 'left' | 'right' }[] = [];

    // Total chapters
    const la = leftData?.novel;
    const ra = rightData?.novel;
    const lCh = la?.total_chapters || 0;
    const rCh = ra?.total_chapters || 0;
    rows.push({
      label: '总章节数',
      left: String(lCh),
      right: String(rCh),
      highlight: lCh > rCh ? 'left' : rCh > lCh ? 'right' : undefined,
    });

    // Total words
    const lW = la?.total_words || 0;
    const rW = ra?.total_words || 0;
    rows.push({
      label: '总字数',
      left: lW.toLocaleString(),
      right: rW.toLocaleString(),
      highlight: lW > rW ? 'left' : rW > lW ? 'right' : undefined,
    });

    // Average quality score
    const lQ = leftData?.avgQuality || 0;
    const rQ = rightData?.avgQuality || 0;
    rows.push({
      label: '平均质量分',
      left: lQ ? lQ.toFixed(2) : '--',
      right: rQ ? rQ.toFixed(2) : '--',
      highlight: lQ > rQ ? 'left' : rQ > lQ ? 'right' : undefined,
    });

    // Genre
    rows.push({
      label: '题材',
      left: la?.genre || '--',
      right: ra?.genre || '--',
    });

    // Latest update time
    const lLatest = la?.chapters?.filter(c => c.word_count > 0).pop();
    const rLatest = ra?.chapters?.filter(c => c.word_count > 0).pop();
    rows.push({
      label: '最新更新',
      left: formatTime(lLatest?.generated_at),
      right: formatTime(rLatest?.generated_at),
    });

    return rows;
  }, [leftData, rightData]);

  // Prevent background scroll
  useEffect(() => {
    document.body.style.overflow = 'hidden';
    return () => { document.body.style.overflow = ''; };
  }, []);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={onClose}>
      <div
        className="bg-card border border-border rounded-2xl shadow-2xl w-[90vw] max-w-4xl max-h-[85vh] overflow-y-auto p-6"
        onClick={e => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between mb-5">
          <h2 className="font-heading text-xl font-semibold text-ink">小说对比</h2>
          <button
            onClick={onClose}
            className="text-ink-muted hover:text-ink text-lg leading-none px-2 py-1 rounded hover:bg-paper transition-colors"
          >
            ✕
          </button>
        </div>

        {/* Selectors */}
        <div className="grid grid-cols-2 gap-4 mb-5">
          <div>
            <label className="text-[11px] font-semibold text-ink-muted uppercase tracking-wide block mb-1">小说 A</label>
            <select
              value={leftId}
              onChange={e => setLeftId(e.target.value)}
              className="w-full rounded-md border border-input bg-paper text-ink text-sm px-3 py-2"
            >
              <option value="">-- 选择 --</option>
              {novels.map(n => (
                <option key={n.id} value={n.id} disabled={n.id === rightId}>
                  {n.title}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="text-[11px] font-semibold text-ink-muted uppercase tracking-wide block mb-1">小说 B</label>
            <select
              value={rightId}
              onChange={e => setRightId(e.target.value)}
              className="w-full rounded-md border border-input bg-paper text-ink text-sm px-3 py-2"
            >
              <option value="">-- 选择 --</option>
              {novels.map(n => (
                <option key={n.id} value={n.id} disabled={n.id === leftId}>
                  {n.title}
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Loading */}
        {loading && (
          <div className="text-center py-12">
            <div className="skeleton h-6 w-32 mx-auto rounded" />
            <p className="text-xs text-ink-muted mt-2">加载对比数据...</p>
          </div>
        )}

        {/* Comparison content */}
        {!loading && (leftData || rightData) && (
          <div>
            {/* Titles */}
            <div className="grid grid-cols-2 gap-4 mb-4">
              <div className="text-center">
                <h3 className="font-heading text-base font-semibold text-ink">{leftData?.novel.title || '--'}</h3>
                <p className="text-[10px] text-ink-subtle">{leftData?.novel.synopsis?.slice(0, 60)}{(leftData?.novel.synopsis?.length || 0) > 60 ? '...' : ''}</p>
              </div>
              <div className="text-center">
                <h3 className="font-heading text-base font-semibold text-ink">{rightData?.novel.title || '--'}</h3>
                <p className="text-[10px] text-ink-subtle">{rightData?.novel.synopsis?.slice(0, 60)}{(rightData?.novel.synopsis?.length || 0) > 60 ? '...' : ''}</p>
              </div>
            </div>

            {/* Stat table */}
            <div className="border border-border rounded-xl overflow-hidden mb-5">
              <table className="w-full text-xs">
                <thead>
                  <tr className="bg-paper border-b border-border">
                    <th className="text-left px-4 py-2 text-ink-muted font-medium">指标</th>
                    <th className="text-center px-4 py-2 text-ink-muted font-medium">小说 A</th>
                    <th className="text-center px-4 py-2 text-ink-muted font-medium">小说 B</th>
                  </tr>
                </thead>
                <tbody>
                  {statRows.map((row, i) => (
                    <tr key={i} className={i % 2 === 0 ? 'bg-card' : 'bg-paper/30'}>
                      <td className="px-4 py-2 text-ink-subtle font-medium">{row.label}</td>
                      <td className={`text-center px-4 py-2 tabular-nums ${
                        row.highlight === 'left' ? 'text-accent font-semibold' : 'text-ink'
                      }`}>{row.left}</td>
                      <td className={`text-center px-4 py-2 tabular-nums ${
                        row.highlight === 'right' ? 'text-accent font-semibold' : 'text-ink'
                      }`}>{row.right}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Chapter count trend chart */}
            <div>
              <h4 className="text-xs font-semibold text-ink-muted uppercase tracking-wide mb-3">每章字数趋势</h4>
              <div className="bg-paper border border-border rounded-xl p-4">
                <ChapterCountBars
                  a={leftData?.chapterWordCounts || []}
                  b={rightData?.chapterWordCounts || []}
                  titleA={leftData?.novel.title || 'A'}
                  titleB={rightData?.novel.title || 'B'}
                />
              </div>
            </div>
          </div>
        )}

        {/* Empty state */}
        {!loading && !leftData && !rightData && leftId && rightId && (
          <div className="text-center py-16 text-ink-subtle text-sm">
            选择两部小说后自动加载对比数据
          </div>
        )}

        {!loading && !leftId && !rightId && (
          <div className="text-center py-16 text-ink-subtle text-sm">
            请选择两部小说进行对比
          </div>
        )}
      </div>
    </div>
  );
}
