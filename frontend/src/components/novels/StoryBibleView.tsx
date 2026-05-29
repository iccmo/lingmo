import { useState, useEffect } from 'react';
import { ConsistencyScoreView } from './ConsistencyScoreView';
import { BookOpen, CheckCircle2, Lightbulb, Telescope, Timer, Users } from 'lucide-react';

interface ReaderState {
 current_chapter: number; reader_mood: string; suggestion: string;
 known_characters: Array<{name: string; emotion: string}>;
 expecting: Array<{desc: string; due: number | null}>;
 cost_balance: {gains: number; losses: number};
}

interface StoryBibleData {
 characters: Array<{
 char_name: string; emotion: string; physical_state: string;
 goal: string; location: string; chapter_num: number;
 }>;
 foreshadowing: Array<{
 id: number; description: string; created_chapter: number;
 due_by_chapter: number | null; status: string;
 }>;
 timeline: Array<{
 chapter_num: number; absolute_time: string; event_summary: string;
 }>;
 consistency_log: Array<{
 id: number; chapter_num: number; check_type: string; severity: string;
 description: string; fix_suggestion: string; was_fixed?: boolean;
 }>;
}

interface Props { novelId: string }

export function StoryBibleView({ novelId }: Props) {
 const [data, setData] = useState<StoryBibleData | null>(null);
 const [reader, setReader] = useState<ReaderState | null>(null);
 const [counterpoint, setCounterpoint] = useState<any>(null);
 const [loading, setLoading] = useState(true);
 const [_constraintPreview] = useState<any>(null);

 useEffect(() => {
 Promise.all([
 fetch(`/api/novels/${novelId}/story-bible`).then(r => r.json()),
 fetch(`/api/novels/${novelId}/reader-state`).then(r => r.json()).catch(() => null),
 fetch(`/api/novels/${novelId}/counterpoint`).then(r => r.json()).catch(() => null),
 ]).then(([bible, rstate, cp]) => {
 setData(bible);
 setReader(rstate);
 setCounterpoint(cp);
 }).catch(() => {}).finally(() => setLoading(false));
 }, [novelId]);

 if (loading) return <div className="skeleton h-20 rounded-lg" />;
 if (!data) return <p className="text-xs text-ink-subtle py-4">暂无数据，生成新章后自动填充</p>;

 const hasData = data.characters.length > 0 || data.foreshadowing.length > 0 || data.timeline.length > 0;

 if (!hasData) {
 return (
 <div className="text-center py-8">
 <p className="text-2xl mb-2"><BookOpen size={12} className="inline" /></p>
 <p className="text-xs text-ink-subtle">故事圣经为空</p>
 <p className="text-[10px] text-ink-subtle mt-1">生成下一章后自动从正文提取</p>
 </div>
 );
 }

 return (
 <div className="space-y-3">
 {/* Cross-Chapter Consistency Score (跨章一致性评分) */}
 <ConsistencyScoreView novelId={novelId} />

 {/* Counterpoint (§16) */}
 {counterpoint && (
 <div className="flex gap-2 text-[9px]">
 {counterpoint.lines?.map((l: any) => (
 <div key={l.id} className={`flex-1 p-1.5 rounded text-center ${
 l.status === '正常' ? 'bg-success-soft dark:bg-emerald-950/20' : 'bg-warn-soft dark:bg-amber-950/20'
 }`}>
 <div className="text-ink-subtle">{l.name}</div>
 <div className={`font-medium ${l.status === '正常' ? 'text-success' : 'text-warn'}`}>{l.speed}</div>
 </div>
 ))}
 </div>
 )}

 {/* Reader State (§67) */}
 {reader && (
 <div className="p-2 rounded-lg bg-accent-soft/20 border border-accent/10">
 <div className="flex items-center justify-between mb-1">
 <span className="text-[11px] font-semibold text-ink">读者状态</span>
 <span className={`text-[10px] font-medium ${
 reader.reader_mood === 'engaged' ? 'text-success' : 'text-warn'
 }`}>
 {reader.reader_mood === 'engaged' ? '投入' : '漂移'}
 </span>
 </div>
 <p className="text-[10px] text-ink-muted">{reader.suggestion}</p>
 <div className="flex gap-3 mt-1 text-[9px] text-ink-subtle">
 <span>知道 {reader.known_characters.length} 角色</span>
 <span>期待 {reader.expecting.length} 伏笔</span>
 <span>收支 {reader.cost_balance.gains}/{reader.cost_balance.losses}</span>
 </div>
 </div>
 )}

 {/* Character States */}
 {data.characters.length > 0 && (
 <div>
 <h4 className="text-xs font-semibold text-ink mb-2"><Users size={12} className="inline" /> 角色状态</h4>
 <div className="space-y-1.5">
 {data.characters.slice(-10).reverse().map((c, i) => (
 <div key={i} className="p-2 rounded-lg bg-paper border border-border text-[10px]">
 <div className="flex items-center justify-between mb-0.5">
 <span className="font-medium text-ink">{c.char_name}</span>
 <span className="text-ink-subtle">Ch{c.chapter_num}</span>
 </div>
 <div className="text-ink-muted space-y-0.5">
 {c.emotion && <span>情绪：{c.emotion}</span>}
 {c.physical_state && <span className="ml-2">身体：{c.physical_state}</span>}
 {c.location && <span className="ml-2">📍{c.location}</span>}
 </div>
 {c.goal && <div className="text-ink-subtle mt-0.5">目标：{c.goal}</div>}
 </div>
 ))}
 </div>
 </div>
 )}

 {/* Active Foreshadowing */}
 {data.foreshadowing.length > 0 && (
 <div>
 <h4 className="text-xs font-semibold text-ink mb-2"><Telescope size={12} className="inline" /> 伏笔追踪 ({data.foreshadowing.length})</h4>
 <div className="space-y-1">
 {data.foreshadowing.map(f => (
 <div key={f.id} className={`p-1.5 rounded text-[10px] flex items-center justify-between ${
 f.status === 'overdue' ? 'bg-destructive-soft dark:bg-red-950/20 border border-destructive/20 ' : 'bg-paper'
 }`}>
 <span className="text-ink truncate flex-1">{f.description}</span>
 <span className="flex items-center gap-1 ml-2 shrink-0">
 <span className={`text-ink-subtle ${f.status === 'overdue' ? 'text-destructive' : ''}`}>
 {f.status === 'overdue' ? '过期' : `Ch${f.created_chapter} → ${f.due_by_chapter || '?'}`}
 </span>
 {f.status === 'active' && (
 <button onClick={async (e) => {
 e.stopPropagation();
 const ch = prompt('回收于第几章？', String(f.due_by_chapter || ''));
 if (ch) {
 await fetch(`/api/novels/${novelId}/foreshadowing/${f.id}/resolve`, {
 method: 'POST', headers: {'Content-Type': 'application/json'},
 body: JSON.stringify({chapter_num: parseInt(ch), text: ''}),
 });
 window.location.reload();
 }
 }} className="text-[9px] text-accent hover:underline">回收</button>
 )}
 </span>
 </div>
 ))}
 </div>
 </div>
 )}

 {/* Timeline */}
 {data.timeline.length > 0 && (
 <div>
 <h4 className="text-xs font-semibold text-ink mb-2"><Timer size={12} className="inline" /> 时间线</h4>
 <div className="space-y-0.5">
 {data.timeline.slice(-5).reverse().map((t, i) => (
 <div key={i} className="flex items-center gap-2 text-[10px] py-0.5">
 <span className="text-ink-subtle w-8 shrink-0">Ch{t.chapter_num}</span>
 <span className="text-ink-muted w-16 shrink-0">{t.absolute_time || '?'}</span>
 <span className="text-ink truncate">{t.event_summary}</span>
 </div>
 ))}
 </div>
 </div>
 )}

 {/* Cost Ledger (§50) */}
 {(data as any).cost_ledger && (data as any).cost_ledger.length > 0 && (
 <div>
 <h4 className="text-xs font-semibold text-ink mb-2">
 代价账簿
 {(() => {
 const entries = (data as any).cost_ledger || [];
 const gains = entries.filter((e: any) => e.gain).length;
 const losses = entries.filter((e: any) => e.loss).length;
 const bal = gains - losses;
 return <span className={`ml-1 text-[10px] ${bal > 2 ? 'text-warn' : bal < -2 ? 'text-destructive' : 'text-success'}`}>
 ({gains}得/{losses}失 {bal >= 0 ? '+' : ''}{bal})
 </span>;
 })()}
 </h4>
 <div className="space-y-1">
 {(data as any).cost_ledger.slice(-10).reverse().map((e: any, i: number) => (
 <div key={i} className="p-1.5 rounded bg-paper border border-border text-[10px]">
 <div className="flex items-center justify-between">
 <span className="font-medium text-ink">{e.character_name}</span>
 <span className="text-ink-subtle">Ch{e.chapter_num}</span>
 </div>
 <div className="flex gap-2 mt-0.5">
 {e.gain && <span className="text-success ">+{e.gain}</span>}
 {e.loss && <span className="text-destructive">-{e.loss}</span>}
 </div>
 </div>
 ))}
 </div>
 </div>
 )}

 {/* Consistency Issues */}
 {data.consistency_log.length > 0 && (
 <div>
 <h4 className="text-xs font-semibold text-ink mb-2">
 一致性校验
 {data.consistency_log.filter(c => c.severity === 'error').length > 0 &&
 <span className="text-destructive ml-1">({data.consistency_log.filter(c => c.severity === 'error').length} 错误)</span>
 }
 {/* System Confidence Index (§66) */}
 {(() => {
 const all = data.consistency_log;
 const errors = all.filter(c => c.severity === 'error').length;
 const warnings = all.filter(c => c.severity === 'warning').length;
 const fixed = all.filter(c => c.was_fixed).length;
 const score = Math.max(0, Math.min(100, 100 - errors * 15 - warnings * 5 + fixed * 10));
 return <span className={`ml-2 text-[10px] font-mono ${score >= 80 ? 'text-success' : score >= 50 ? 'text-warn' : 'text-destructive'}`}>
 信心 {score}%
 </span>;
 })()}
 </h4>
 <div className="space-y-1">
 {data.consistency_log.slice(0, 10).map((c, i) => (
 <div key={i} className={`p-1.5 rounded text-[10px] ${
 c.severity === 'error' ? 'bg-destructive-soft dark:bg-red-950/20 border border-destructive/20 '
 : c.severity === 'warning' ? 'bg-warn-soft dark:bg-amber-950/20 border border-warn/20 '
 : 'bg-paper'
 }`}>
 <div className="flex items-center gap-1.5">
 <span className={`font-medium ${
 c.severity === 'error' ? 'text-destructive' : c.severity === 'warning' ? 'text-warn' : 'text-info'
 }`}>
 {c.severity === 'error' ? '🔴' : c.severity === 'warning' ? '🟡' : '🔵'}
 </span>
 <span className="text-ink-subtle">{c.check_type}</span>
 <span className="text-ink-subtle">Ch{c.chapter_num}</span>
 </div>
 <p className="text-ink mt-0.5">{c.description}</p>
 {c.fix_suggestion && <p className="text-ink-subtle mt-0.5"><Lightbulb size={12} className="inline" /> {c.fix_suggestion}</p>}
 {!c.was_fixed && (
 <button onClick={async () => {
 await fetch(`/api/novels/${novelId}/consistency/${c.id}/fix`, {method: 'POST'});
 window.location.reload();
 }}
 className="text-[9px] text-accent hover:underline mt-0.5"><CheckCircle2 size={12} className="text-success inline" /> 标记已修复</button>
 )}
 {c.was_fixed && <span className="text-[9px] text-success mt-0.5"><CheckCircle2 size={12} className="text-success inline" /> 已修复</span>}
 </div>
 ))}
 </div>
 </div>
 )}
 </div>
 );
}
