import { useNavigate } from 'react-router-dom';
import { useState } from 'react';
import type { NovelSummary } from 'src/types';
import { toast } from 'sonner';

function wordProgress(total: number): { pct: number; label: string; color: string } {
  const milestones = [
    { limit: 100000, emoji: '🏆', label: '成书', color: 'text-emerald-500' },
    { limit: 50000, emoji: '📖', label: '中篇', color: 'text-sky-500' },
    { limit: 20000, emoji: '📝', label: '短篇', color: 'text-amber-500' },
    { limit: 5000, emoji: '🌱', label: '开篇', color: 'text-violet-500' },
  ];
  for (const m of milestones) {
    if (total >= m.limit) return { pct: Math.min(100, Math.round((total / 100000) * 100)), label: `${m.emoji} ${m.label}`, color: m.color };
  }
  return { pct: 0, label: '🌱 起步', color: 'text-ink-muted' };
}

export function NovelCard({ novel, onDelete, onGenerate, isGenerating }: {
  novel: NovelSummary;
  onDelete?: (id: string) => void;
  onGenerate?: (id: string) => void;
  isGenerating?: boolean;
}) {
  const navigate = useNavigate();
  const [starred, setStarred] = useState(() => {
    try { return JSON.parse(localStorage.getItem('starred-novels') || '[]').includes(novel.id); }
    catch { return false; }
  });

  function toggleStar(e: { stopPropagation: () => void }) {
    e.stopPropagation();
    setStarred(prev => {
      const next = !prev;
      try {
        const list: string[] = JSON.parse(localStorage.getItem('starred-novels') || '[]');
        if (next) { if (!list.includes(novel.id)) list.push(novel.id); }
        else { const idx = list.indexOf(novel.id); if (idx >= 0) list.splice(idx, 1); }
        localStorage.setItem('starred-novels', JSON.stringify(list));
      } catch {}
      return next;
    });
  }
  const ch = novel.latest_chapter;
  const hasContent = novel.total_chapters > 0;
  const progress = wordProgress(novel.total_words || 0);

  // Novel health score (aggregate)
  const healthScore = hasContent ? (() => {
    let score = 50;
    score += Math.min(20, novel.total_words / 5000); // up to 20 for volume
    score += Math.min(15, novel.total_chapters * 2); // up to 15 for chapters
    if (ch?.generated_at) {
      try {
        const daysSince = (Date.now() - new Date(ch.generated_at + 'Z').getTime()) / 86400000;
        if (daysSince < 3) score += 15;
        else if (daysSince < 7) score += 8;
      } catch {}
    }
    return Math.min(100, Math.round(score));
  })() : 0;

  // Attention indicators
  const needsAttention: string[] = [];
  if (hasContent && novel.total_words < 5000) needsAttention.push('刚起步');
  if (ch?.generated_at) {
    try {
      const daysSince = (Date.now() - new Date(ch.generated_at + 'Z').getTime()) / 86400000;
      if (daysSince > 7) needsAttention.push('超过7天未更新');
      else if (daysSince > 3) needsAttention.push('超过3天未更新');
    } catch {}
  }

  async function handleDelete() {
    if (!confirm(`确定删除《${novel.title}》？`)) return;
    // Optimistic: remove immediately
    onDelete?.(novel.id);
    try {
      await fetch(`/api/novels/${novel.id}`, { method: 'DELETE' });
      toast.success(`已删除《${novel.title}》`, {
        action: { label: '撤销', onClick: async () => {
          try {
            await fetch(`/api/novels/${novel.id}/restore`, { method: 'POST' });
            toast.success('已恢复');
          } catch { toast.error('恢复失败'); }
        }}
      });
    } catch {
      toast.error('删除失败，请刷新');
      // Reload to restore UI state
      window.location.reload();
    }
  }

  return (
    <div
      className="group rounded-xl border border-border bg-card p-5 transition-all duration-200
        hover:-translate-y-1 hover:shadow-lg hover:border-accent/20 cursor-pointer"
      onClick={() => navigate(`/novels/${novel.id}`)}
    >
      {/* Header row */}
      <div className="flex items-start justify-between mb-3">
        <div className="flex-1 min-w-0">
          <h3 className="font-heading text-lg font-semibold text-ink truncate group-hover:text-accent transition-colors flex items-center gap-2">
            {novel.title}
            {isGenerating && (
              <span className="relative flex h-2 w-2 shrink-0">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-accent opacity-75" />
                <span className="relative inline-flex rounded-full h-2 w-2 bg-accent" />
              </span>
            )}
          </h3>
          <div className="flex gap-2 mt-1">
            <span className="text-[11px] px-2 py-0.5 rounded-full bg-paper text-ink-muted border border-border">
              {novel.genre}
            </span>
            {hasContent && (
              <span className={`text-[11px] px-2 py-0.5 rounded-full border font-semibold ${progress.color}`}>
                {progress.label}
              </span>
            )}
          </div>
        </div>
        <button
          onClick={toggleStar}
          className={`text-xs transition-all p-1 ${starred ? 'text-amber-500' : 'opacity-0 group-hover:opacity-100 text-ink-muted'}`}
          title={starred ? '取消收藏' : '收藏'}>
          {starred ? '⭐' : '☆'}
        </button>
        <button
          onClick={e => { e.stopPropagation(); handleDelete(); }}
          className="opacity-0 group-hover:opacity-100 text-xs text-ink-muted hover:text-red-500 transition-all p-1">
          🗑
        </button>
      </div>

      {/* Stats bar */}
      <div className="flex gap-4 text-xs text-ink-muted mb-3 flex-wrap">
        {hasContent ? (
          <>
            <span>📖 {novel.total_chapters}章</span>
            <span>📝 {(novel.total_words/10000).toFixed(1)}万字</span>
            {ch && <span className="truncate">▸ 第{ch.number}章</span>}
            {ch?.generated_at && (
              <span className="text-ink-subtle text-[10px] ml-auto">
                {(() => {
                  try {
                    const d = new Date(ch.generated_at + 'Z');
                    const now = new Date();
                    const diffMin = Math.round((now.getTime() - d.getTime()) / 60000);
                    if (diffMin < 1) return '刚刚';
                    if (diffMin < 60) return `${diffMin}分钟前`;
                    if (diffMin < 1440) return `${Math.floor(diffMin / 60)}小时前`;
                    return d.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' });
                  } catch { return ''; }
                })()}
              </span>
            )}
          </>
        ) : (
          <span className="text-ink-subtle">📄 空 — 点击开始创作</span>
        )}
      </div>

      {/* Synopsis */}
      <p className="text-[13px] text-ink-muted leading-relaxed line-clamp-2 mb-3">
        {novel.synopsis || '暂无简介'}
      </p>

      {/* Health + Word count progress bar */}
      {hasContent && (
        <div className="mb-3">
          <div className="flex justify-between text-[10px] mb-1">
            <span className="text-ink-subtle">健康度</span>
            <span className={`tabular-nums font-semibold ${healthScore >= 70 ? 'text-emerald-500' : healthScore >= 45 ? 'text-amber-500' : 'text-red-500'}`}>{healthScore}</span>
          </div>
          <div className="h-1.5 bg-border rounded-full overflow-hidden">
            <div className={`h-full rounded-full transition-all duration-500 ${healthScore >= 70 ? 'bg-emerald-400' : healthScore >= 45 ? 'bg-amber-400' : 'bg-red-400'}`}
              style={{ width: `${healthScore}%` }} />
          </div>
        </div>
      )}

      {/* Attention indicators */}
      {needsAttention.length > 0 && (
        <div className="flex gap-1.5 mb-3 flex-wrap">
          {needsAttention.map(a => (
            <span key={a} className="text-[10px] px-1.5 py-0.5 rounded-full bg-amber-50 text-amber-600 border border-amber-200 dark:bg-amber-900/20 dark:text-amber-400 dark:border-amber-800">
              ⚠️ {a}
            </span>
          ))}
        </div>
      )}

      {/* Actions */}
      <div className="flex gap-2" onClick={e => e.stopPropagation()}>
        <button
          className="flex-1 text-xs py-2 rounded-md bg-accent text-white hover:bg-accent-hover transition-colors font-medium disabled:opacity-50"
          disabled={isGenerating}
          onClick={() => { onGenerate?.(novel.id); }}>
          {isGenerating ? '⏳ 生成中...' : hasContent ? '⚡ 续写下一章' : '⚡ 生成第一章'}
        </button>
        <button
          className="text-xs py-2 px-3 rounded-md border border-border text-ink-muted hover:text-ink hover:bg-paper transition-colors"
          onClick={() => navigate(`/novels/${novel.id}`)}>
          {hasContent ? '继续阅读 →' : '详情 →'}
        </button>
      </div>
    </div>
  );
}
