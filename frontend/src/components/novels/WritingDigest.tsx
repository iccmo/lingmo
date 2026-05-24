import { useMemo, useEffect } from 'react';
import type { ChapterMeta } from 'src/types';

interface DigestStats {
  totalWords: number;
  totalChapters: number;
  avgQuality: number;
  bestChapter: { num: number; score: number };
  weakestChapter: { num: number; score: number };
  chaptersToday: number;
  wordsToday: number;
  streak: number;
  readerConfusions: { chapter: number; text: string; reason: string }[];
}

function computeDigest(chapters: ChapterMeta[]): DigestStats {
  const gen = chapters.filter(c => c.word_count > 0);
  const scores = gen.filter(c => c.quality_score !== undefined).map(c => c.quality_score!);
  const avgQ = scores.length > 0 ? scores.reduce((a, b) => a + b, 0) / scores.length : 0;

  let best = { num: 0, score: 0 };
  let weakest = { num: 0, score: 1 };
  for (const c of gen) {
    const q = c.quality_score || 0;
    if (q > best.score) best = { num: c.number, score: q };
    if (q < weakest.score && q > 0) weakest = { num: c.number, score: q };
  }

  // Today's stats
  const today = new Date().toISOString().slice(0, 10);
  const todayChapters = gen.filter(c => {
    try { return c.generated_at?.startsWith(today); } catch { return false; }
  });
  const chaptersToday = todayChapters.length;
  const wordsToday = todayChapters.reduce((s, c) => s + (c.word_count || 0), 0);

  // Streak from localStorage
  let streak = 0;
  try {
    const log = JSON.parse(localStorage.getItem('writing-daily-log') || '{}');
    const dates = Object.keys(log).sort().reverse();
    const now = new Date();
    for (let i = 0; i < dates.length; i++) {
      const d = new Date(dates[i]);
      const expected = new Date(now);
      expected.setDate(expected.getDate() - i);
      if (d.toISOString().slice(0, 10) === expected.toISOString().slice(0, 10)) {
        if (log[dates[i]] > 0) streak++;
        else break;
      } else break;
    }
  } catch { /* ignore */ }

  // Reader confusion markers (heuristic)
  const confusions: DigestStats['readerConfusions'] = [];
  for (const c of gen.slice(-5)) {
    const s = c.summary || '';
    // New character introduction without explanation
    if (/出现.*神秘|陌生.*人|不知名/.test(s)) {
      confusions.push({ chapter: c.number, text: s.slice(0, 40), reason: '新角色未充分介绍' });
    }
    // Sudden power jump
    if (/突然.*突破|瞬间.*升级|莫名.*变强/.test(s)) {
      confusions.push({ chapter: c.number, text: s.slice(0, 40), reason: '实力跳跃缺乏铺垫' });
    }
  }

  return {
    totalWords: gen.reduce((s, c) => s + (c.word_count || 0), 0),
    totalChapters: gen.length,
    avgQuality: avgQ,
    bestChapter: best,
    weakestChapter: weakest,
    chaptersToday,
    wordsToday,
    streak,
    readerConfusions: confusions.slice(0, 3),
  };
}

export function WritingDigest({ chapters, novelId }: { chapters?: ChapterMeta[]; novelId?: string }) {
  const digest = useMemo(() => chapters ? computeDigest(chapters) : null, [chapters]);

  // Quality trend memory
  const qualityTrends = useMemo(() => {
    if (!chapters || !novelId) return null;
    try {
      const history: Record<string, number[]> = JSON.parse(localStorage.getItem(`quality-history-${novelId}`) || '{}');
      const gen = chapters.filter(c => c.word_count > 0 && c.quality_score);
      const last5 = gen.slice(-5);
      if (last5.length < 3) return null;

      const avgScores = last5.map(c => c.quality_score || 0);
      const trend = avgScores[avgScores.length - 1] - avgScores[0];

      // Find weakest dimension from stored details
      const detailHistory: Record<string, number[]> = {};
      try {
        const details = JSON.parse(localStorage.getItem(`quality-details-${novelId}`) || '{}');
        for (const [ch, dims] of Object.entries(details) as [string, Record<string, number>][]) {
          for (const [dim, score] of Object.entries(dims)) {
            if (!detailHistory[dim]) detailHistory[dim] = [];
            detailHistory[dim].push(score);
          }
        }
      } catch {}

      const weakDims = Object.entries(detailHistory)
        .map(([dim, scores]) => ({ dim, avg: scores.reduce((a,b) => a+b, 0) / scores.length }))
        .sort((a, b) => a.avg - b.avg)
        .slice(0, 2);

      return { trend, weakDims, last5Avg: avgScores.reduce((a,b)=>a+b,0)/avgScores.length };
    } catch { return null; }
  }, [chapters, novelId]);

  // Save quality details when chapters change
  useEffect(() => {
    if (!novelId || !chapters) return;
    try {
      const details: Record<string, Record<string, number>> = JSON.parse(localStorage.getItem(`quality-details-${novelId}`) || '{}');
      for (const ch of chapters) {
        if (ch.quality_score && !details[String(ch.number)]) {
          details[String(ch.number)] = { overall: ch.quality_score };
        }
      }
      localStorage.setItem(`quality-details-${novelId}`, JSON.stringify(details));
    } catch {}
  }, [chapters, novelId]);

  if (!digest || digest.totalChapters < 1) return null;

  return (
    <div className="p-4 bg-card border border-border rounded-xl">
      <h3 className="font-heading text-base font-semibold text-ink mb-3">📋 写作日报</h3>

      {/* Key metrics */}
      <div className="grid grid-cols-3 gap-3 mb-4">
        <div className="text-center p-2 bg-paper rounded-lg">
          <div className="font-heading text-xl font-semibold text-ink">{digest.totalChapters}</div>
          <div className="text-[10px] text-ink-muted">总章节</div>
        </div>
        <div className="text-center p-2 bg-paper rounded-lg">
          <div className="font-heading text-xl font-semibold text-accent">{digest.avgQuality.toFixed(2)}</div>
          <div className="text-[10px] text-ink-muted">均质量</div>
        </div>
        <div className="text-center p-2 bg-paper rounded-lg">
          <div className="font-heading text-xl font-semibold text-ink">{digest.streak}</div>
          <div className="text-[10px] text-ink-muted">连续天</div>
        </div>
      </div>

      {/* Today */}
      <div className="flex gap-4 text-[11px] text-ink-muted mb-3 pb-3 border-b border-border">
        <span>今日: {digest.chaptersToday}章</span>
        <span>{digest.wordsToday.toLocaleString()}字</span>
        {digest.chaptersToday === 0 && <span className="text-amber-500">今天还没写哦</span>}
      </div>

      {/* Best & weakest */}
      {digest.bestChapter.num > 0 && (
        <div className="flex gap-4 text-[11px] mb-3">
          <span className="text-emerald-500">🏆 最佳: Ch{digest.bestChapter.num} ({digest.bestChapter.score.toFixed(2)})</span>
          {digest.weakestChapter.num > 0 && (
            <span className="text-amber-500">⚠️ 最弱: Ch{digest.weakestChapter.num} ({digest.weakestChapter.score.toFixed(2)})</span>
          )}
        </div>
      )}

      {/* Quality trend insight */}
      {qualityTrends && (
        <div className="mb-3 p-3 rounded-lg bg-accent-soft/10 border border-accent/10 text-[11px]">
          <div className="flex items-center gap-2 mb-1">
            <span className={qualityTrends.trend > 0.03 ? 'text-emerald-500' : qualityTrends.trend < -0.03 ? 'text-amber-500' : 'text-ink-subtle'}>
              {qualityTrends.trend > 0.03 ? '📈' : qualityTrends.trend < -0.03 ? '📉' : '➡️'}
            </span>
            <span className="text-ink font-medium">质量趋势</span>
            <span className="text-ink-muted">近5章均分 {qualityTrends.last5Avg.toFixed(2)}</span>
          </div>
          {qualityTrends.weakDims.length > 0 && (
            <p className="text-ink-muted text-[10px]">
              💡 建议重点提升：
              {qualityTrends.weakDims.map((d, i) => (
                <span key={d.dim} className="text-amber-500 font-medium">{d.dim}({d.avg.toFixed(1)}){i < qualityTrends.weakDims.length - 1 ? '、' : ''}</span>
              ))}
            </p>
          )}
        </div>
      )}

      {/* Reader confusions */}
      {digest.readerConfusions.length > 0 && (
        <div className="pt-3 border-t border-border">
          <p className="text-[11px] font-medium text-ink mb-2">🧠 读者可能困惑</p>
          {digest.readerConfusions.map((c, i) => (
            <div key={i} className="flex items-start gap-2 text-[10px] mb-1.5">
              <span className="text-ink-subtle shrink-0 mt-0.5">Ch{c.chapter}</span>
              <div>
                <span className="text-ink-muted">{c.reason}</span>
                <span className="text-ink-subtle ml-1">— {c.text}</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
