import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Card, CardContent } from 'src/components/ui/card';
import { Badge } from 'src/components/ui/badge';
import { toast } from 'sonner';
import { RefreshCw, AlertTriangle, Telescope, CheckCircle2, Lightbulb, Pin, AlertOctagon } from 'lucide-react';

interface ForeshadowingAudit {
 total_open: number;
 total_resolved: number;
 oldest_open_chapter: number;
 stale: { content: string; buried_chapter: number; age: number }[];
 warning: string;
}

interface PlotPoint {
 type: string;
 content: string;
 is_resolved: number;
 sort_order: number;
}

export function Foreshadowing() {
 const { id } = useParams<{ id: string }>();
 const navigate = useNavigate();
 const [audit, setAudit] = useState<ForeshadowingAudit | null>(null);
 const [plotPoints, setPlotPoints] = useState<PlotPoint[]>([]);
 const [loading, setLoading] = useState(true);
 const [refreshing, setRefreshing] = useState(false);

 async function loadData() {
 if (!id) return;
 setLoading(true);
 try {
 const [auditRes, novelRes] = await Promise.all([
 fetch(`/api/novels/${id}/foreshadowing`).then(r => r.json()),
 fetch(`/api/novels/${id}`).then(r => r.json()),
 ]);
 setAudit(auditRes);
 setPlotPoints(novelRes.plot_points || []);
 } catch {
 toast.error('加载伏笔数据失败');
 } finally {
 setLoading(false);
 }
 }

 useEffect(() => { loadData(); }, [id]);

 async function handleRefresh() {
 setRefreshing(true);
 await loadData();
 setRefreshing(false);
 toast.success('伏笔审计已刷新');
 }

 if (loading) {
 return <div className="space-y-4"><div className="skeleton h-6 w-32" /><div className="skeleton h-40 rounded-lg" /></div>;
 }

 const openItems = plotPoints.filter(p => !p.is_resolved);
 const resolvedItems = plotPoints.filter(p => p.is_resolved);

 return (
 <div className="page-enter">
 <button onClick={() => navigate(`/novels/${id}`)} className="text-xs text-ink-muted hover:text-ink mb-2 block">
 ← 返回小说详情
 </button>

 <div className="flex items-center justify-between mb-2">
 <div>
 <h1 className="font-heading text-[28px] font-semibold text-ink leading-tight">伏笔追踪</h1>
 <p className="text-sm text-ink-muted mt-1">追踪已埋下的伏笔及其回收状态</p>
 </div>
 <button onClick={handleRefresh} disabled={refreshing}
 className="text-xs px-3 py-1.5 rounded-md border border-border text-ink-muted hover:text-ink transition-colors disabled:opacity-50">
 {refreshing ? '审计中...' : <><RefreshCw size={13} className='mr-1' /> 刷新审计</>}
 </button>
 </div>

 {/* Stats overview */}
 {audit && (
 <div className="grid grid-cols-4 gap-3 mb-6">
 <Card className="border-border">
 <CardContent className="p-4 text-center">
 <div className="font-heading text-[28px] font-semibold text-warn">{audit.total_open}</div>
 <div className="text-[11px] text-ink-muted">未回收伏笔</div>
 </CardContent>
 </Card>
 <Card className="border-border">
 <CardContent className="p-4 text-center">
 <div className="font-heading text-[28px] font-semibold text-success">{audit.total_resolved}</div>
 <div className="text-[11px] text-ink-muted">已回收伏笔</div>
 </CardContent>
 </Card>
 <Card className="border-border">
 <CardContent className="p-4 text-center">
 <div className="font-heading text-[28px] font-semibold text-ink">
 {audit.oldest_open_chapter > 0 ? `第${audit.oldest_open_chapter}章` : '—'}
 </div>
 <div className="text-[11px] text-ink-muted">最早未回收</div>
 </CardContent>
 </Card>
 <Card className="border-border">
 <CardContent className="p-4 text-center">
 <div className="font-heading text-[28px] font-semibold text-ink">
 {audit.total_open + audit.total_resolved}
 </div>
 <div className="text-[11px] text-ink-muted">伏笔总数</div>
 </CardContent>
 </Card>
 </div>
 )}

 {/* Stale warning */}
 {audit?.warning && (
 <div className="mb-4 p-3 bg-warn-soft border border-warn/20 rounded-lg ">
 <p className="text-xs text-amber-700 font-medium"><AlertTriangle size={12} className='mr-0.5' /> {audit.warning}</p>
 {audit.stale.length > 0 && (
 <div className="mt-2 space-y-1">
 {audit.stale.map((s, i) => (
 <div key={i} className="text-[11px] text-warn dark:text-warn flex gap-2">
 <span className="shrink-0">第{s.buried_chapter}章埋</span>
 <span className="text-ink-muted">({s.age}章前)</span>
 <span>— {s.content}</span>
 </div>
 ))}
 </div>
 )}
 </div>
 )}

 {/* Two-column layout: Open vs Resolved */}
 <div className="grid grid-cols-2 gap-4">
 {/* Open foreshadowing */}
 <div>
 <h2 className="font-heading text-lg font-semibold text-ink mb-3 flex items-center gap-2">
 <Telescope size={14} className='mr-1' /> 未回收
 <Badge variant="outline" className="text-xs">{openItems.length}</Badge>
 </h2>
 {openItems.length === 0 ? (
 <div className="text-center py-12 border border-dashed border-border rounded-lg">
 <p className="text-sm text-ink-muted">暂无未回收伏笔</p>
 <p className="text-xs text-ink-subtle mt-1">生成章节时 AI 会自动埋下伏笔</p>
 </div>
 ) : (
 <div className="space-y-2">
 {openItems.map((p, i) => (
 <Card key={i} className="border-border hover:border-accent/20 transition-colors">
 <CardContent className="p-3">
 <div className="flex items-start gap-2">
 <Telescope size={16} className="shrink-0 mt-0.5 text-accent" />
 <div className="flex-1 min-w-0">
 <p className="text-sm text-ink leading-relaxed">{p.content}</p>
 <div className="flex gap-2 mt-1.5">
 <Badge variant="outline" className="text-[10px]">{p.type || '伏笔'}</Badge>
 <span className="text-[10px] text-ink-subtle">等待回收</span>
 </div>
 </div>
 </div>
 </CardContent>
 </Card>
 ))}
 </div>
 )}
 </div>

 {/* Resolved foreshadowing */}
 <div>
 <h2 className="font-heading text-lg font-semibold text-ink mb-3 flex items-center gap-2">
 <CheckCircle2 size={14} className='mr-1 text-success' /> 已回收
 <Badge variant="outline" className="text-xs">{resolvedItems.length}</Badge>
 </h2>
 {resolvedItems.length === 0 ? (
 <div className="text-center py-12 border border-dashed border-border rounded-lg">
 <p className="text-sm text-ink-muted">暂无已回收伏笔</p>
 <p className="text-xs text-ink-subtle mt-1">当伏笔在后续章节被呼应时，会出现在这里</p>
 </div>
 ) : (
 <div className="space-y-2">
 {resolvedItems.map((p, i) => (
 <Card key={i} className="border-border opacity-70 hover:opacity-100 transition-all">
 <CardContent className="p-3">
 <div className="flex items-start gap-2">
 <CheckCircle2 size={16} className="shrink-0 mt-0.5 text-success" />
 <div className="flex-1 min-w-0">
 <p className="text-sm text-ink leading-relaxed">{p.content}</p>
 <div className="flex gap-2 mt-1.5">
 <Badge variant="outline" className="text-[10px]">{p.type || '伏笔'}</Badge>
 <span className="text-[10px] text-success">已回收</span>
 </div>
 </div>
 </div>
 </CardContent>
 </Card>
 ))}
 </div>
 )}
 </div>
 </div>

 {/* Writing tips */}
 <Card className="mt-6 border-border bg-muted/30">
 <CardContent className="p-4">
 <h3 className="font-heading text-base font-semibold text-ink mb-2"><Lightbulb size={14} className='mr-1' /> 伏笔管理技巧</h3>
 <div className="grid grid-cols-3 gap-3 text-xs text-ink-muted">
 <div>
 <p className="font-medium text-ink mb-0.5"><Pin size={12} className='mr-1' /> 三章原则</p>
 <p>重要伏笔应在3章内给出第一次暗示，避免读者遗忘</p>
 </div>
 <div>
 <p className="font-medium text-ink mb-0.5">🎯 分层回收</p>
 <p>小伏笔3-5章回收，大伏笔可跨卷。不同层次的伏笔有不同的节奏</p>
 </div>
 <div>
 <p className="font-medium text-ink mb-0.5"><AlertOctagon size={12} className='mr-1' /> 10章警戒线</p>
 <p>超过10章未回收的伏笔会出现在警告区。及时处理或确认是否仍有必要</p>
 </div>
 </div>
 </CardContent>
 </Card>
 </div>
 );
}
