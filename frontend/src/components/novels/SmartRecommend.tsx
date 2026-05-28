import { useState, useEffect } from 'react';
import type { ChapterMeta } from 'src/types';

/* ─── Genre Blend Analysis ─── */
interface GenreBlend {
  primary: string;
  secondary: string;
  confidence: number;
  reason: string;
}

function analyzeBlends(genre: string, chapters: ChapterMeta[]): GenreBlend[] {
  const blends: GenreBlend[] = [];
  const summaries = chapters.filter(c => c.summary).map(c => c.summary).join(' ');

  // Pattern-based detection
  const patterns: [string, string, string, RegExp][] = [
    ['悬疑', '含大量谜团/反转/身份不明', 'suspense', /谜|真相|隐瞒|身份|反转|秘密|失踪|调查/],
    ['感情', '人物关系复杂/情感纠葛', 'romance', /爱|情|婚|恋|心动|表白|分手|重逢/],
    ['权谋', '有权斗/算计/势力博弈', 'politics', /算计|权|势力|博弈|阴谋|架空|陷害|站队/],
    ['恐怖', '有恐怖/惊悚元素', 'horror', /诡异|恐怖|尸|鬼|阴森|尖叫|毛骨悚然/],
    ['喜剧', '有幽默/搞笑元素', 'comedy', /笑|搞笑|吐槽|逗|欢乐|囧|尴尬/],
  ];

  for (const [label, reason, , regex] of patterns) {
    if (label === genre) continue;
    const matches = summaries.match(regex);
    if (matches && matches.length >= 3) {
      const confidence = Math.min(0.9, 0.4 + matches.length * 0.1);
      blends.push({ primary: genre, secondary: label, confidence, reason });
    }
  }

  return blends.slice(0, 3);
}

/* ─── Title Optimization ─── */
interface TitleScore {
  chapter: number;
  title: string;
  score: number;
  suggestion?: string;
  issues: string[];
  altTitles: string[];
}

function scoreTitles(chapters: ChapterMeta[]): TitleScore[] {
  return chapters
    .filter(c => c.word_count > 0 && c.title)
    .slice(-10)
    .map(ch => {
      const issues: string[] = [];
      let score = 70;

      // Too short
      if (ch.title.length < 3) { score -= 20; issues.push('标题过短'); }

      // Too generic
      const genericWords = ['新的开始', '意外', '相遇', '决定', '变化', '日常'];
      for (const w of genericWords) {
        if (ch.title.includes(w)) { score -= 15; issues.push('标题太通用'); break; }
      }

      // Has conflict/question hook
      if (/[？?！!]/.test(ch.title)) score += 10;
      if (/[生死决战危机秘密真相].*/.test(ch.title)) score += 10;
      if (ch.title.length >= 4 && ch.title.length <= 12) score += 5;

      // Has number (works well on 番茄: "第三章 三重危机")
      if (/\d/.test(ch.title)) score += 5;

      // Generate alternative titles based on chapter summary
      const altTitles: string[] = [];
      if (score < 65 && ch.summary) {
        const s = ch.summary.slice(0, 60);
        // Pattern-based alternatives
        if (/战斗|打斗|对决|击败/.test(s)) altTitles.push('激战！' + s.slice(0, 8));
        if (/秘密|真相|发现|揭露/.test(s)) altTitles.push('真相浮出水面');
        if (/突破|升级|进阶|晋升/.test(s)) altTitles.push('突破！新的境界');
        if (/危机|危险|陷阱|伏击/.test(s)) altTitles.push('危机四伏');
        if (/重逢|相遇|见面/.test(s)) altTitles.push('意外的重逢');
        if (/计划|准备|布局/.test(s)) altTitles.push('暗流涌动');
        if (altTitles.length === 0) {
          // Fallback: use key words
          const words = s.replace(/[，。！？、；：""''（）《》\s]/g, ' ').split(' ').filter(w => w.length >= 2);
          if (words.length >= 2) altTitles.push(words.slice(0, 2).join('·'));
        }
      }

      let suggestion: string | undefined;
      if (score < 50) {
        const hints = [
          '💡 加入冲突词：如「危机」「对决」「真相」',
          '💡 用疑问句：如「谁是幕后黑手？」',
          '💡 加入数字：如「三重试炼」',
          '💡 制造悬念：如「不该打开的门」',
        ];
        suggestion = hints[Math.floor(Math.random() * hints.length)];
      }

      return {
        chapter: ch.number,
        title: ch.title,
        score: Math.max(0, Math.min(100, score)),
        suggestion,
        issues,
        altTitles,
      };
    });
}

export function SmartRecommend({ genre, chapters }: {
  genre: string;
  chapters?: ChapterMeta[];
}) {
  const [blends, setBlends] = useState<GenreBlend[]>([]);
  const [titleScores, setTitleScores] = useState<TitleScore[]>([]);

  useEffect(() => {
    if (chapters && chapters.length > 0) {
      setBlends(analyzeBlends(genre, chapters));
      setTitleScores(scoreTitles(chapters));
    }
  }, [genre, chapters]);

  if (!chapters || chapters.length < 2) return null;

  return (
    <div className="space-y-4">
      {/* Genre Blend Recommendations */}
      {blends.length > 0 && (
        <div className="p-4 bg-card border border-border rounded-xl">
          <h3 className="font-heading text-base font-semibold text-ink mb-3">🧬 智能题材分析</h3>
          <p className="text-[11px] text-ink-muted mb-3">
            你的{genre}小说中检测到其他题材元素，建议融合以扩大受众：
          </p>
          <div className="flex gap-2 flex-wrap">
            {blends.map((b, i) => (
              <div key={i}
                className="px-3 py-2 rounded-lg border border-accent/20 bg-accent-soft/50 hover:border-accent/40 transition-colors">
                <div className="flex items-center gap-1.5 mb-0.5">
                  <span className="text-xs font-semibold text-ink">{genre}</span>
                  <span className="text-[10px] text-accent">+{b.secondary}</span>
                  <span className="text-[10px] text-ink-subtle">
                    {(b.confidence * 100).toFixed(0)}%匹配
                  </span>
                </div>
                <p className="text-[10px] text-ink-muted">{b.reason}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Chapter Title Optimization */}
      <div className="p-4 bg-card border border-border rounded-xl">
        <div className="flex items-center justify-between mb-3">
          <div>
            <h3 className="font-heading text-base font-semibold text-ink">📝 章节标题优化</h3>
            <p className="text-[11px] text-ink-muted">标题影响点击率，番茄小说标题即门面</p>
          </div>
          <span className="text-[10px] text-ink-subtle">
            均分 {Math.round(titleScores.reduce((s, t) => s + t.score, 0) / (titleScores.length || 1))}
          </span>
        </div>

        {titleScores.length === 0 ? (
          <p className="text-sm text-ink-muted text-center py-4">暂无已生成章节标题</p>
        ) : (
          <div className="space-y-1.5">
            {titleScores.map(t => (
              <div key={t.chapter}
                className="flex items-center gap-3 px-3 py-2 rounded-md hover:bg-paper transition-colors group">
                <span className="text-[10px] text-ink-subtle tabular-nums w-10">Ch{t.chapter}</span>
                <span className="flex-1 text-sm text-ink truncate">{t.title}</span>
                <div className="flex items-center gap-2 shrink-0">
                  {/* Score bar */}
                  <div className="w-12 h-1.5 bg-border rounded-full overflow-hidden">
                    <div className={`h-full rounded-full transition-all ${
                      t.score >= 70 ? 'bg-emerald-400' : t.score >= 45 ? 'bg-amber-400' : 'bg-red-400'
                    }`} style={{ width: `${t.score}%` }} />
                  </div>
                  <span className={`text-[10px] font-semibold tabular-nums w-7 text-right ${
                    t.score >= 70 ? 'text-emerald-500' : t.score >= 45 ? 'text-amber-500' : 'text-red-500'
                  }`}>{t.score}</span>
                  {t.altTitles.length > 0 && (
                    <span className="hidden group-hover:flex gap-1 items-center">
                      <span className="text-[10px] text-accent">建议:</span>
                      {t.altTitles.slice(0, 2).map((alt, j) => (
                        <span key={j} className="text-[10px] text-accent bg-accent-soft px-1 rounded">{alt}</span>
                      ))}
                    </span>
                  )}
                  {t.suggestion && t.altTitles.length === 0 && (
                    <span className="hidden group-hover:inline text-[10px] text-accent cursor-help"
                      title={t.suggestion}>💡</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
