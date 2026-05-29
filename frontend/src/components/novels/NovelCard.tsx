import { useNavigate } from 'react-router-dom';
import { useState } from 'react';
import type { NovelSummary } from 'src/types';
import { toast } from 'sonner';
import {
 Trophy, BookOpen, FileText, Sprout, Star, Trash2,
 Zap, ArrowRight, AlertTriangle, Loader2,
} from 'lucide-react';

function wordProgress(total: number): { pct: number; label: string; color: string; Icon: typeof Trophy } {
 const milestones = [
 { limit: 100000, Icon: Trophy, label: '成书', color: 'text-success' },
 { limit: 50000, Icon: BookOpen, label: '中篇', color: 'text-info' },
 { limit: 20000, Icon: FileText, label: '短篇', color: 'text-warn' },
 { limit: 5000, Icon: Sprout, label: '开篇', color: 'text-violet-500' },
 ];
 for (const m of milestones) {
 if (total >= m.limit) return { pct: Math.min(100, Math.round((total / 100000) * 100)), ...m };
 }
 return { pct: 0, Icon: Sprout, label: '起步', color: 'text-ink-muted' };
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
 setStarred((prev: boolean) => {
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
 const ProgressIcon = progress.Icon;

 const healthScore = hasContent ? (() => {
 let score = 50;
 score += Math.min(20, novel.total_words / 5000);
 score += Math.min(15, novel.total_chapters * 2);
 if (ch?.generated_at) {
 try {
 const daysSince = (Date.now() - new Date(ch.generated_at + 'Z').getTime()) / 86400000;
 if (daysSince < 3) score += 15;
 else if (daysSince < 7) score += 8;
 } catch {}
 }
 return Math.min(100, Math.round(score));
 })() : 0;

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
 window.location.reload();
 }
 }

 return (
 <div
 className="group relative rounded-xl border border-border bg-card p-5 transition-all duration-200
 hover:-translate-y-1 hover:shadow-lg hover:border-accent/20 cursor-pointer"
 onClick={() => navigate(`/novels/${novel.id}`)}
 >
 {/* Header row */}
 <div className="flex items-start justify-between mb-3">
 <div className="flex-1 min-w-0">
 <h3 className="font-heading text-lg font-semibold text-ink truncate group-hover:text-accent transition-colors flex items-center gap-2">
 {novel.title}
 {isGenerating && (
 <Loader2 size={14} className="text-accent animate-spin shrink-0" />
 )}
 </h3>
 <div className="flex gap-2 mt-1">
 <span className="text-[11px] px-2 py-0.5 rounded-full bg-surface text-ink-muted border border-border">
 {novel.genre}
 </span>
 {hasContent && (
 <span className={`text-[11px] px-2 py-0.5 rounded-full border border-current/15 font-semibold flex items-center gap-1 ${progress.color}`}>
 <ProgressIcon size={11} />
 {progress.label}
 </span>
 )}
 </div>
 </div>
 <div className="flex items-center gap-0.5">
 {/* Star always visible when starred; otherwise on hover */}
 <button
 onClick={toggleStar}
 className={`p-1.5 rounded-md transition-all min-w-[32px] min-h-[32px] flex items-center justify-center
 ${starred ? 'text-warn' : 'text-ink-muted hover:text-warn opacity-0 group-hover:opacity-100'}`}
 title={starred ? '取消收藏' : '收藏'}>
 <Star size={14} fill={starred ? 'currentColor' : 'none'} />
 </button>
 <button
 onClick={e => { e.stopPropagation(); handleDelete(); }}
 className="p-1.5 rounded-md text-ink-muted hover:text-destructive transition-all min-w-[32px] min-h-[32px] flex items-center justify-center
 opacity-0 group-hover:opacity-100">
 <Trash2 size={14} />
 </button>
 </div>
 </div>

 {/* Stats bar */}
 <div className="flex gap-4 text-xs text-ink-muted mb-3 flex-wrap">
 {hasContent ? (
 <>
 <span className="flex items-center gap-1"><BookOpen size={12} />{novel.total_chapters}章</span>
 <span className="flex items-center gap-1"><FileText size={12} />{(novel.total_words/10000).toFixed(1)}万字</span>
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
 <span className="text-ink-subtle flex items-center gap-1.5"><FileText size={12} />空 — 点击开始创作</span>
 )}
 </div>

 {/* Synopsis */}
 <p className="text-[13px] text-ink-muted leading-relaxed line-clamp-2 mb-3">
 {novel.synopsis || '暂无简介'}
 </p>

 {/* Health progress */}
 {hasContent && (
 <div className="mb-3">
 <div className="flex justify-between text-[10px] mb-1">
 <span className="text-ink-subtle">健康度</span>
 <span className={`tabular-nums font-semibold ${healthScore >= 70 ? 'text-success' : healthScore >= 45 ? 'text-warn' : 'text-destructive'}`}>{healthScore}</span>
 </div>
 <div className="h-1.5 bg-border rounded-full overflow-hidden">
 <div className={`h-full rounded-full transition-all duration-500 ${healthScore >= 70 ? 'bg-success' : healthScore >= 45 ? 'bg-warn' : 'bg-destructive'}`}
 style={{ width: `${healthScore}%` }} />
 </div>
 </div>
 )}

 {/* Attention indicators */}
 {needsAttention.length > 0 && (
 <div className="flex gap-1.5 mb-3 flex-wrap">
 {needsAttention.map(a => (
 <span key={a} className="text-[10px] px-1.5 py-0.5 rounded-full bg-warn-soft text-warn border border-warn/20 flex items-center gap-1">
 <AlertTriangle size={10} /> {a}
 </span>
 ))}
 </div>
 )}

 {/* Actions */}
 <div className="flex gap-2" onClick={e => e.stopPropagation()}>
 <button
 className="flex-1 text-xs py-2 rounded-md bg-accent text-white hover:bg-accent-hover transition-colors font-medium disabled:opacity-50
 flex items-center justify-center gap-1.5 min-h-[36px]"
 disabled={isGenerating}
 onClick={() => { onGenerate?.(novel.id); }}>
 {isGenerating ? (
 <><Loader2 size={13} className="animate-spin" /> 生成中...</>
 ) : hasContent ? (
 <><Zap size={13} /> 续写下一章</>
 ) : (
 <><Zap size={13} /> 生成第一章</>
 )}
 </button>
 <button
 className="text-xs py-2 px-3 rounded-md border border-border text-ink-muted hover:text-ink hover:bg-surface transition-colors
 flex items-center gap-1 min-h-[36px]"
 onClick={() => navigate(`/novels/${novel.id}`)}>
 {hasContent ? '继续阅读' : '详情'} <ArrowRight size={12} />
 </button>
 </div>
 </div>
 );
}
