import { useState, useMemo } from 'react';
import { toast } from 'sonner';
import type { ChapterMeta } from 'src/types';

interface RetentionPoint {
  chapter: number;
  title: string;
  retention: number;    // % of readers still here
  dropRisk: number;     // 0-100 risk of losing readers at this chapter
  reasons: string[];
}

function simulateRetention(chapters: ChapterMeta[]): RetentionPoint[] {
  const withContent = chapters.filter(c => c.word_count > 0);
  if (withContent.length === 0) return [];

  let retention = 100;
  return withContent.map((ch, i) => {
    const reasons: string[] = [];
    let dropRisk = 0;

    // Quality score impact
    if (ch.quality_score !== undefined) {
      if (ch.quality_score < 0.4) { dropRisk += 40; reasons.push('质量偏低'); }
      else if (ch.quality_score < 0.55) { dropRisk += 25; reasons.push('质量一般'); }
    }

    // Hook strength impact
    if (ch.ending_hook) {
      const h = ch.ending_hook;
      if (!h || h.length < 5) { dropRisk += 15; reasons.push('结尾钩子弱'); }
      if (/(悬念|反转|危机|惊人|秘密|真相)/.test(h)) dropRisk -= 10;
    } else {
      dropRisk += 15;
      reasons.push('无结尾钩子');
    }

    // Word count impact (too short = readers feel cheated)
    if (ch.word_count < 1500) { dropRisk += 20; reasons.push('字数过少'); }

    // First chapter always has extra risk
    if (i === 0 && dropRisk > 15) {
      reasons.unshift('首章留存关键！');
    }

    // Consecutive weak chapters compound
    if (i > 0 && ch.quality_score !== undefined && ch.quality_score < 0.5) {
      const prev = withContent[i - 1];
      if (prev.quality_score !== undefined && prev.quality_score < 0.5) {
        dropRisk += 20;
        reasons.push('连续低质章节');
      }
    }

    dropRisk = Math.min(95, Math.max(0, dropRisk));
    const actualDrop = (dropRisk / 100) * retention * 0.7;
    retention = Math.max(5, retention - actualDrop);

    return {
      chapter: ch.number,
      title: ch.title,
      retention: Math.round(retention),
      dropRisk: Math.round(dropRisk),
      reasons,
    };
  });
}

/* ─── What-If Explorer ─── */
const WHAT_IF_SCENARIOS = [
  { label: '🔥 主角选择相反', key: 'opposite', desc: '如果主角在这一章做了完全相反的选择...' },
  { label: '💀 关键角色死亡', key: 'death', desc: '如果一个重要角色在这一章死去...' },
  { label: '🤝 宿敌变盟友', key: 'ally', desc: '如果宿敌在这一章与主角联手...' },
  { label: '🌪️ 外部灾难降临', key: 'disaster', desc: '如果天灾/意外事件在这一章发生...' },
];

export function ReaderSim({ novelId, chapters }: {
  novelId: string;
  chapters?: ChapterMeta[];
}) {
  const retention = useMemo(() => chapters ? simulateRetention(chapters) : [], [chapters]);
  const [whatIfChapter, setWhatIfChapter] = useState<number | null>(null);
  const [whatIfResult, setWhatIfResult] = useState<string>('');
  const [exploring, setExploring] = useState(false);

  if (!chapters || chapters.length < 3) return null;

  const withContent = chapters.filter(c => c.word_count > 0);
  const finalRetention = retention.length > 0 ? retention[retention.length - 1].retention : 100;
  const dangerChapters = retention.filter(r => r.dropRisk >= 50);
  const bestRetention = retention.length > 0
    ? retention.reduce((best, r) => r.retention > best.retention ? r : best, retention[0])
    : null;

  async function exploreWhatIf(chapterNum: number, scenario: string) {
    setWhatIfChapter(chapterNum);
    setExploring(true);
    try {
      const r = await fetch(`/api/novels/${novelId}/what-if`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ chapter: chapterNum, scenario }),
      });
      if (r.ok) {
        const d = await r.json();
        setWhatIfResult(d.summary || d.branch || '分支剧情已生成');
      } else {
        setWhatIfResult(getFallbackBranch(chapterNum, scenario, chapters));
      }
    } catch {
      setWhatIfResult(getFallbackBranch(chapterNum, scenario, chapters));
    } finally {
      setExploring(false);
    }
  }

  function getFallbackBranch(chNum: number, scenario: string, chs: ChapterMeta[]): string {
    const ch = chs.find(c => c.number === chNum);
    const title = ch?.title || '未知章节';
    const branches: Record<string, string> = {
      opposite: `第${chNum}章「${title}」的另一个可能：主角做出相反选择后，故事线发生偏移。原先的冲突可能提前或延后爆发，角色的成长路径也会不同。这是值得在番外或if线中探索的叙事可能性。`,
      death: `如果关键角色在第${chNum}章「${title}」中死去，整个势力格局将重新洗牌。主角失去重要支撑，但也可能因此获得更强的独立性和复仇动机。需要确保这个死亡推动而非拖累剧情。`,
      ally: `如果宿敌在第${chNum}章「${title}」中与主角联手，读者会感到意外但合理（如果铺垫充分）。这创造了「亦敌亦友」的复杂关系，可以成为全书最出彩的人物关系线之一。`,
      disaster: `如果在第${chNum}章「${title}」中引入外部灾难，故事的压力层级会瞬间提升。这让所有角色的真实面目暴露——谁逃跑、谁挺身而出。是检验角色弧线的绝佳场景。`,
    };
    return branches[scenario] || '分支剧情正在探索中...';
  }

  return (
    <div className="space-y-4">
      {/* Retention Simulator */}
      <div className="p-4 bg-card border border-border rounded-xl">
        <div className="flex items-center justify-between mb-3">
          <div>
            <h3 className="font-heading text-base font-semibold text-ink">👁️ 读者留存模拟</h3>
            <p className="text-[11px] text-ink-muted">模拟读者逐章阅读的留存率</p>
          </div>
          <div className="flex gap-2 text-xs">
            <div className={`text-center px-2 py-1 rounded ${
              finalRetention >= 50 ? 'bg-emerald-50 text-emerald-600 dark:bg-emerald-900/20 dark:text-emerald-400'
              : finalRetention >= 25 ? 'bg-amber-50 text-amber-600 dark:bg-amber-900/20 dark:text-amber-400'
              : 'bg-red-50 text-red-600 dark:bg-red-900/20 dark:text-red-400'
            }`}>
              <div className="font-bold text-base">{finalRetention}%</div>
              <div className="text-[9px]">最终留存</div>
            </div>
          </div>
        </div>

        {/* Retention bars */}
        <div className="space-y-1">
          {retention.map((r, i) => {
            const barColor = r.dropRisk >= 50 ? 'bg-red-400 dark:bg-red-500'
              : r.dropRisk >= 25 ? 'bg-amber-400 dark:bg-amber-500'
              : 'bg-emerald-400 dark:bg-emerald-500';
            const bgColor = r.dropRisk >= 50 ? 'bg-red-50 dark:bg-red-950'
              : r.dropRisk >= 25 ? 'bg-amber-50 dark:bg-amber-950' : '';

            return (
              <div key={r.chapter} className={`flex items-center gap-2 px-2 py-1 rounded ${bgColor} transition-colors`}>
                <span className="text-[10px] text-ink-subtle tabular-nums w-8 shrink-0">Ch{r.chapter}</span>
                <div className="flex-1 h-4 bg-border/50 rounded-full overflow-hidden relative">
                  <div className={`h-full rounded-full transition-all duration-500 ${barColor}`}
                    style={{ width: `${r.retention}%` }} />
                </div>
                <span className="text-[10px] font-semibold tabular-nums w-8 text-right shrink-0">{r.retention}%</span>
                {r.dropRisk >= 50 && (
                  <span className="text-[10px] text-red-500 shrink-0" title={r.reasons.join(', ')}>⚠️</span>
                )}
              </div>
            );
          })}
        </div>

        {/* Danger chapters */}
        {dangerChapters.length > 0 && (
          <div className="mt-3 pt-3 border-t border-border">
            <p className="text-[11px] text-amber-600 dark:text-amber-400 font-medium mb-1">
              ⚠️ {dangerChapters.length} 个高风险流失点：
            </p>
            <div className="flex gap-2 flex-wrap">
              {dangerChapters.map(r => (
                <span key={r.chapter}
                  className="text-[10px] px-2 py-0.5 rounded-full bg-amber-50 border border-amber-200 text-amber-700 dark:bg-amber-900/20 dark:border-amber-800 dark:text-amber-400">
                  Ch{r.chapter}: {r.reasons[0]}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* What-If Explorer */}
      <div className="p-4 bg-card border border-border rounded-xl">
        <h3 className="font-heading text-base font-semibold text-ink mb-2">🌿 '如果' 剧情浏览器</h3>
        <p className="text-[11px] text-ink-muted mb-3">
          选择一个章节和场景，探索故事的不同可能性
        </p>

        {/* Chapter selector */}
        <div className="flex gap-1.5 mb-3 flex-wrap">
          {withContent.slice(0, 10).map(ch => (
            <button key={ch.number}
              onClick={() => setWhatIfChapter(ch.number)}
              className={`text-[11px] px-2.5 py-1 rounded-full border transition-all ${
                whatIfChapter === ch.number
                  ? 'bg-accent-soft text-accent border-accent/30'
                  : 'border-border text-ink-muted hover:text-ink hover:border-accent/20'
              }`}>
              第{ch.number}章
            </button>
          ))}
        </div>

        {/* Scenario buttons */}
        {whatIfChapter && (
          <div className="flex gap-2 flex-wrap mb-3">
            {WHAT_IF_SCENARIOS.map(s => (
              <button key={s.key}
                onClick={() => exploreWhatIf(whatIfChapter, s.key)}
                disabled={exploring}
                className="text-[11px] px-3 py-2 rounded-lg border border-border hover:border-accent/30 hover:bg-accent-soft/30
                  transition-all disabled:opacity-40 text-left">
                <div className="font-medium text-ink">{s.label}</div>
                <div className="text-[10px] text-ink-muted mt-0.5">{s.desc}</div>
              </button>
            ))}
          </div>
        )}

        {/* Result */}
        {exploring && (
          <div className="flex items-center gap-2 text-sm text-ink-muted py-4">
            <div className="w-3 h-3 border-2 border-accent border-t-transparent rounded-full animate-spin" />
            正在生成分支剧情...
          </div>
        )}
        {whatIfResult && !exploring && (
          <div className="p-3 rounded-lg bg-accent-soft/50 border border-accent/10">
            <div className="flex items-center gap-1.5 mb-1">
              <span className="text-xs font-semibold text-accent">分支剧情</span>
              <span className="text-[10px] text-ink-subtle">第{whatIfChapter}章 · if线</span>
            </div>
            <p className="text-sm text-ink leading-relaxed">{whatIfResult}</p>
            <button onClick={() => { setWhatIfResult(''); }}
              className="text-[10px] text-ink-muted hover:text-ink mt-2">
              清除
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
