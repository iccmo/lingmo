import { useMemo } from 'react';
import type { ChapterMeta } from 'src/types';

interface ChecklistItem {
  label: string;
  icon: string;
  pass: boolean;
  detail: string;
  weight: 'critical' | 'high' | 'medium';
}

export function PlatformChecklist({ chapters, genre }: {
  chapters?: ChapterMeta[];
  genre: string;
}) {
  const items = useMemo((): ChecklistItem[] => {
    if (!chapters || chapters.length === 0) return [];
    const latest = chapters.filter(c => c.word_count > 0).pop();
    if (!latest) return [];

    const results: ChecklistItem[] = [];

    // 1. Hook in last 3 sentences (critical)
    const hasHook = latest.ending_hook && latest.ending_hook.length > 5;
    results.push({
      label: '结尾钩子',
      icon: '🎣',
      pass: hasHook,
      detail: hasHook ? latest.ending_hook!.slice(0, 40) : '无钩子——读者不会点下一章',
      weight: 'critical',
    });

    // 2. Title clickbait score
    const titleScore = (() => {
      let s = 70;
      if (latest.title.length < 3) s -= 20;
      if (latest.title.length >= 4 && latest.title.length <= 12) s += 10;
      if (/[？?！!]/.test(latest.title)) s += 10;
      if (/[生死决战危机秘密真相]/.test(latest.title)) s += 5;
      return s;
    })();
    results.push({
      label: '标题吸睛度',
      icon: '📝',
      pass: titleScore >= 60,
      detail: `${titleScore}分 — ${titleScore >= 80 ? '优秀' : titleScore >= 60 ? '合格' : '建议优化'}`,
      weight: 'high',
    });

    // 3. Chapter length
    const wordCount = latest.word_count;
    const lengthOk = wordCount >= 2000 && wordCount <= 6000;
    results.push({
      label: '章节长度',
      icon: '📏',
      pass: lengthOk,
      detail: `${wordCount.toLocaleString()}字 — ${wordCount < 2000 ? '太短，读者觉得不值' : wordCount > 6000 ? '太长，手机阅读疲劳' : '适中'}`,
      weight: 'medium',
    });

    // 4. Quality score
    const q = latest.quality_score || 0;
    results.push({
      label: '质量评分',
      icon: '⭐',
      pass: q >= 0.6,
      detail: `${q.toFixed(2)} — ${q >= 0.8 ? '神作级' : q >= 0.6 ? '合格' : '需重写'}`,
      weight: 'high',
    });

    // 5. Dialogue density (web novel readers expect high dialogue)
    const summary = latest.summary || '';
    const dialogueMarkers = (summary.match(/[「「""''“”说问道答讲喊叫骂]/g) || []).length;
    const dialogueRatio = Math.round((dialogueMarkers / Math.max(1, Math.min(summary.length, 200))) * 100);
    results.push({
      label: '对话密度',
      icon: '💬',
      pass: dialogueRatio >= 30,
      detail: `${dialogueRatio}% — ${dialogueRatio >= 50 ? '对话丰富' : dialogueRatio >= 30 ? '适中' : '叙述偏多，网文读者偏好对话'}`,
      weight: 'medium',
    });

    // 6. Genre fit
    const genreTips: Record<string, string> = {
      '玄幻': '需要修炼体系/等级突破/打斗场面',
      '都市': '需要现代感/身份反差/金钱权力',
      '悬疑': '需要谜团/反转/紧张感',
      '科幻': '需要科技设定/未来感/硬核逻辑',
      '官场': '需要权力博弈/人情世故/潜规则',
      '系统流': '需要系统提示/数据面板/升级快感',
    };
    const tip = genreTips[genre] || '符合题材特征';
    results.push({
      label: '题材匹配',
      icon: '🎯',
      pass: true, // Always passes, just informative
      detail: tip,
      weight: 'medium',
    });

    return results;
  }, [chapters, genre]);

  if (items.length === 0) return null;

  const criticalFail = items.filter(i => i.weight === 'critical' && !i.pass).length;
  const totalScore = items.filter(i => i.pass).length;

  return (
    <div className="p-4 bg-card border border-border rounded-xl">
      <div className="flex items-center justify-between mb-3">
        <div>
          <h3 className="font-heading text-base font-semibold text-ink">📋 发布前检查</h3>
          <p className="text-[11px] text-ink-muted">番茄小说算法适配度评估</p>
        </div>
        <div className={`text-xs font-bold px-2 py-1 rounded ${
          criticalFail === 0 && totalScore >= 5
            ? 'bg-emerald-50 text-emerald-600 dark:bg-emerald-900/30 dark:text-emerald-400'
            : criticalFail > 0
            ? 'bg-red-50 text-red-600 dark:bg-red-900/30 dark:text-red-400'
            : 'bg-amber-50 text-amber-600 dark:bg-amber-900/30 dark:text-amber-400'
        }`}>
          {criticalFail === 0 && totalScore >= 5 ? '✅ 可以发布'
           : criticalFail > 0 ? '❌ 不建议发布'
           : '⚠️ 建议优化'}
        </div>
      </div>

      <div className="space-y-1.5">
        {items.map((item, i) => (
          <div key={i} className={`flex items-start gap-2 px-3 py-2 rounded-md text-[12px] ${
            !item.pass && item.weight === 'critical' ? 'bg-red-50/50 dark:bg-red-950/20' : ''
          }`}>
            <span className="shrink-0 mt-0.5">{item.pass ? '✅' : item.weight === 'critical' ? '❌' : '⚠️'}</span>
            <div className="flex-1 min-w-0">
              <span className="font-medium text-ink">{item.icon} {item.label}</span>
              <span className="text-ink-muted ml-2">{item.detail}</span>
            </div>
            {item.weight === 'critical' && !item.pass && (
              <span className="text-[10px] text-red-500 font-semibold shrink-0">必须修复</span>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
