import { useEffect, useState, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Card, CardContent } from 'src/components/ui/card';
import { Badge } from 'src/components/ui/badge';
import { api } from 'src/lib/api';
import { toast } from 'sonner';
import type { NovelDetail } from 'src/types';
import { AlertTriangle } from 'lucide-react';

interface ForeshadowData { total_open: number; total_resolved: number; stale: { content: string; buried_chapter: number; age: number }[]; warning: string; }
interface LogEntry { id: number; event: string; detail: string; created_at: string; novel_id?: string; }

export function MemoryBank() {
 const { id } = useParams<{ id: string }>();
 const navigate = useNavigate();
 const [novel, setNovel] = useState<NovelDetail | null>(null);
 const [foreshadow, setForeshadow] = useState<ForeshadowData | null>(null);
 const [logs, setLogs] = useState<LogEntry[]>([]);
 const [loading, setLoading] = useState(true);
 const [tab, setTab] = useState<'overview' | 'history' | 'foreshadow' | 'characters'>('overview');

 useEffect(() => {
 if (!id) return;
 Promise.all([
 api.novels.get(id),
 fetch(`/api/novels/${id}/foreshadowing`).then(r => r.json()).catch(() => null),
 fetch('/api/logs').then(r => r.json()).then(d => (d.logs || []).filter((l: LogEntry) => l.novel_id === id).slice(0, 50)).catch(() => []),
 ]).then(([n, f, l]) => {
 setNovel(n); setForeshadow(f); setLogs(l);
 }).catch(() => toast.error('加载失败')).finally(() => setLoading(false));
 }, [id]);

 const genChapters = useMemo(() => (novel?.chapters || []).filter(c => c.word_count > 0), [novel]);

 // Generation stats
 const genLogs = logs.filter(l => l.event.includes('chapter') || l.event.includes('generate'));
 const today = new Date().toISOString().slice(0, 10);
 const todayLogs = genLogs.filter(l => l.created_at?.startsWith(today));
 const lastGen = genLogs[0];

 if (loading) return <div className="p-8 space-y-4"><div className="skeleton h-8 w-48" /><div className="skeleton h-40 rounded-lg" /></div>;
 if (!novel) return <div className="p-8 text-ink-muted">小说未找到</div>;

 return (
 <div className="page-enter">
 <button onClick={() => navigate(`/novels/${id}`)} className="text-xs text-ink-muted hover:text-ink mb-2 block">← 返回小说详情</button>
 <div className="flex items-center justify-between mb-4">
 <div>
 <h1 className="font-heading text-[28px] font-semibold text-ink leading-tight">创作记忆</h1>
 <p className="text-sm text-ink-muted mt-1">{novel.title} · {genChapters.length}章 · {novel.total_words.toLocaleString()}字</p>
 </div>
 <div className="flex gap-1">
 {[
 { key: 'overview' as const, label: '概览' },
 { key: 'history' as const, label: '生成记录' },
 { key: 'foreshadow' as const, label: '伏笔' },
 { key: 'characters' as const, label: '角色' },
 ].map(t => (
 <button key={t.key} onClick={() => setTab(t.key)}
 className={`text-[11px] px-3 py-1.5 rounded-md transition-colors ${
 tab === t.key ? 'bg-accent text-white' : 'text-ink-muted hover:text-ink hover:bg-paper'
 }`}>{t.label}</button>
 ))}
 </div>
 </div>

 {/* Overview Tab */}
 {tab === 'overview' && (
 <div className="grid gap-4 max-w-[720px]">
 {/* Quick stats */}
 <div className="grid grid-cols-4 gap-3">
 {[
 { v: genChapters.length, l: '已写章节' },
 { v: todayLogs.length, l: '今日生成' },
 { v: novel.world?.power_system || '未设定', l: '修炼体系' },
 { v: novel.world?.era || '未设定', l: '时代背景' },
 ].map(s => (
 <Card key={s.l} className="border-border"><CardContent className="p-3 text-center">
 <div className="font-heading text-xl font-semibold text-ink">{s.v}</div>
 <div className="text-[10px] text-ink-muted mt-0.5">{s.l}</div>
 </CardContent></Card>
 ))}
 </div>

 {/* Latest generation */}
 {lastGen && (
 <Card className="border-border"><CardContent className="p-4">
 <h3 className="font-heading text-sm font-semibold text-ink mb-2">最近生成</h3>
 <div className="text-xs text-ink-muted space-y-1">
 <p>事件：{lastGen.event} · {new Date(lastGen.created_at + 'Z').toLocaleString('zh-CN')}</p>
 {lastGen.detail && <p className="text-ink-subtle">{lastGen.detail.slice(0, 200)}</p>}
 </div>
 </CardContent></Card>
 )}

 {/* Chapter list summary */}
 <Card className="border-border"><CardContent className="p-4">
 <h3 className="font-heading text-sm font-semibold text-ink mb-2">章节概览</h3>
 <div className="space-y-1">
 {genChapters.slice(-5).map(ch => (
 <div key={ch.number} className="flex items-center gap-2 text-xs">
 <span className="text-ink-subtle w-12 tabular-nums">第{ch.number}章</span>
 <span className="text-ink flex-1 truncate">{ch.title}</span>
 <span className="text-ink-subtle tabular-nums">{ch.word_count.toLocaleString()}字</span>
 {ch.quality_score && (
 <span className={`tabular-nums font-mono ${ch.quality_score >= 0.7 ? 'text-success' : ch.quality_score >= 0.5 ? 'text-warn' : 'text-destructive'}`}>
 {ch.quality_score.toFixed(2)}
 </span>
 )}
 </div>
 ))}
 </div>
 </CardContent></Card>

 {/* Soul + character config summary */}
 {(() => {
 const fp = (() => { try { return JSON.parse(localStorage.getItem(`soul-fingerprint-${id}`) || 'null'); } catch { return null; } })();
 const chars = (() => { try { return JSON.parse(localStorage.getItem(`characters-soul-${id}`) || '[]'); } catch { return []; } })();
 if (!fp && chars.length === 0) return null;
 return (
 <Card className="border-border"><CardContent className="p-4">
 <h3 className="font-heading text-sm font-semibold text-ink mb-2">当前配置</h3>
 <div className="text-xs text-ink-muted space-y-1">
 {fp?.primaryPolarity && <p>💎 灵魂矛盾已配置 · 30组中选择</p>}
 {chars.length > 0 && <p>👥 {chars.length} 个角色已有详细灵魂档案</p>}
 {!fp && <p className="text-ink-subtle flex items-center gap-1"><AlertTriangle size={12} className='text-warn' /> 尚未配置灵魂矛盾</p>}
 </div>
 </CardContent></Card>
 );
 })()}
 </div>
 )}

 {/* History Tab */}
 {tab === 'history' && (
 <div className="max-w-[720px]">
 {genLogs.length === 0 ? (
 <div className="text-center py-16 text-sm text-ink-muted">暂无生成记录</div>
 ) : (
 <div className="space-y-1.5">
 {genLogs.slice(0, 30).map(log => (
 <div key={log.id} className="flex items-start gap-3 p-3 rounded-lg bg-paper border border-border text-xs">
 <span className="text-ink-subtle shrink-0 w-36 tabular-nums">
 {new Date(log.created_at + 'Z').toLocaleString('zh-CN', { month:'short', day:'numeric', hour:'2-digit', minute:'2-digit' })}
 </span>
 <Badge variant="outline" className="shrink-0 text-[10px]">{log.event}</Badge>
 <span className="text-ink-muted truncate flex-1">{log.detail?.slice(0, 100) || ''}</span>
 </div>
 ))}
 </div>
 )}
 </div>
 )}

 {/* Foreshadowing Tab */}
 {tab === 'foreshadow' && (
 <div className="max-w-[720px]">
 {!foreshadow ? (
 <div className="text-center py-16 text-sm text-ink-muted">加载中...</div>
 ) : (
 <div className="space-y-4">
 <div className="grid grid-cols-2 gap-3">
 <Card className="border-border"><CardContent className="p-3 text-center">
 <div className="font-heading text-2xl font-semibold text-warn">{foreshadow.total_open}</div>
 <div className="text-[10px] text-ink-muted">未回收伏笔</div>
 </CardContent></Card>
 <Card className="border-border"><CardContent className="p-3 text-center">
 <div className="font-heading text-2xl font-semibold text-success">{foreshadow.total_resolved}</div>
 <div className="text-[10px] text-ink-muted">已回收伏笔</div>
 </CardContent></Card>
 </div>
 {foreshadow.warning && (
 <div className="p-3 rounded-lg bg-warn-soft border border-warn/20 text-xs text-amber-700 dark:text-amber-300 ">
 <AlertTriangle size={12} className='text-warn mr-0.5 inline' /> {foreshadow.warning}
 </div>
 )}
 {foreshadow.stale.length > 0 && (
 <div className="space-y-1.5">
 <p className="text-xs font-semibold text-ink">超期伏笔</p>
 {foreshadow.stale.map((s, i) => (
 <div key={i} className="p-2.5 rounded-lg bg-paper border border-border text-[11px]">
 <span className="text-ink-subtle">第{s.buried_chapter}章埋 ({s.age}章前)</span>
 <span className="text-ink ml-2">{s.content}</span>
 </div>
 ))}
 </div>
 )}
 </div>
 )}
 </div>
 )}

 {/* Characters Tab */}
 {tab === 'characters' && (
 <div className="max-w-[720px]">
 {!novel.characters?.length ? (
 <div className="text-center py-16 text-sm text-ink-muted">暂无角色数据</div>
 ) : (
 <div className="space-y-2">
 {novel.characters.map((c) => (
 <Card key={c.id} className="border-border"><CardContent className="p-3">
 <div className="flex items-center gap-2 mb-1">
 <span className="font-heading text-sm font-semibold text-ink">{c.name}</span>
 <Badge variant="outline" className="text-[10px]">{c.role}</Badge>
 {c.status && <Badge variant="outline" className="text-[10px]">{c.status}</Badge>}
 </div>
 <div className="text-[11px] text-ink-muted space-y-0.5">
 {c.personality && <p>性格：{c.personality}</p>}
 {c.power_level && <p>境界：{c.power_level}</p>}
 {c.background && <p>背景：{c.background.slice(0, 100)}</p>}
 </div>
 </CardContent></Card>
 ))}
 </div>
 )}
 </div>
 )}
 </div>
 );
}
