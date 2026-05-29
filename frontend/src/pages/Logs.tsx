import { useEffect, useState, useCallback, useMemo } from 'react';
import { Badge } from 'src/components/ui/badge';
import { toast } from 'sonner';
import { RefreshCw, ClipboardList } from 'lucide-react';

interface LogEntry {
 id: number;
 novel_id: string | null;
 event: string;
 detail: string;
 created_at: string;
}

type Severity = 'critical' | 'error' | 'warning' | 'info';

function classifyLog(log: LogEntry): { severity: Severity; label: string; emoji: string } {
 const e = log.event;
 const d = (log.detail || '').toLowerCase();
 if (e.includes('critical') || d.includes('timeout') || d.includes('crash')) return { severity: 'critical', label: '严重', emoji: '🔴' };
 if (e.includes('error') || e.includes('failed') || d.includes('fail') || d.includes('error')) return { severity: 'error', label: '错误', emoji: '🟠' };
 if (e.includes('retry') || d.includes('retry') || d.includes('warn')) return { severity: 'warning', label: '警告', emoji: '🟡' };
 return { severity: 'info', label: '信息', emoji: '🔵' };
}

function eventCategory(log: LogEntry): string {
 const e = log.event;
 if (e.includes('chapter')) return '章节';
 if (e.includes('generate')) return '生成';
 if (e.includes('publish')) return '发布';
 if (e.includes('error') || e.includes('fail')) return '错误';
 if (e.includes('auto')) return '自动';
 if (e.includes('mode')) return '模式';
 return '系统';
}

function fmtTime(ts: string): string {
 try { return new Date(ts + 'Z').toLocaleString('zh-CN', { month:'short', day:'numeric', hour:'2-digit', minute:'2-digit', second:'2-digit' }); }
 catch { return ts; }
}

function fmtDetail(detail: string): { summary: string; full: string } {
 try {
 const obj = JSON.parse(detail);
 // Handle error objects specially
 if (obj.error) return { summary: obj.error.slice(0, 80), full: JSON.stringify(obj, null, 2) };
 if (obj.message) return { summary: obj.message.slice(0, 80), full: JSON.stringify(obj, null, 2) };
 return { summary: JSON.stringify(obj).slice(0, 80), full: JSON.stringify(obj, null, 2) };
 } catch {
 return { summary: detail.slice(0, 80), full: detail };
 }
}

export function Logs() {
 const [logs, setLogs] = useState<LogEntry[]>([]);
 const [loading, setLoading] = useState(true);
 const [expanded, setExpanded] = useState<number | null>(null);
 const [filterSeverity, setFilterSeverity] = useState('');
 const [filterCategory, setFilterCategory] = useState('');
 const [filterNovel, setFilterNovel] = useState('');
 const [autoRefresh, setAutoRefresh] = useState(false);

 const loadLogs = useCallback(() => {
 setLoading(prev => logs.length === 0 && prev);
 fetch('/api/logs').then(r => r.json()).then(d => {
 setLogs((d.logs || []).slice(0, 200));
 }).catch(() => toast.error('加载日志失败')).finally(() => setLoading(false));
 }, []);

 useEffect(() => { loadLogs(); }, [loadLogs]);

 // Auto-refresh
 useEffect(() => {
 if (!autoRefresh) return;
 const timer = setInterval(loadLogs, 5000);
 return () => clearInterval(timer);
 }, [autoRefresh, loadLogs]);

 // Filter + classify
 const filtered = useMemo(() => logs.filter(log => {
 if (filterSeverity) {
 const s = classifyLog(log).severity;
 if (filterSeverity === 'error-group' && !['critical','error'].includes(s)) return false;
 if (filterSeverity === 'critical' && s !== 'critical') return false;
 if (filterSeverity === 'error' && s !== 'error') return false;
 if (filterSeverity === 'warning' && s !== 'warning') return false;
 }
 if (filterCategory && eventCategory(log) !== filterCategory) return false;
 if (filterNovel && log.novel_id && !log.novel_id.includes(filterNovel)) return false;
 return true;
 }), [logs, filterSeverity, filterCategory, filterNovel]);

 // Error summary
 const errorSummary = useMemo(() => {
 const recent = logs.slice(0, 50);
 const critical = recent.filter(l => classifyLog(l).severity === 'critical').length;
 const errors = recent.filter(l => classifyLog(l).severity === 'error').length;
 const warnings = recent.filter(l => classifyLog(l).severity === 'warning').length;
 const lastError = recent.find(l => ['critical','error'].includes(classifyLog(l).severity));
 // Group by error type
 const typeMap = new Map<string, number>();
 for (const l of recent) {
 if (['critical','error'].includes(classifyLog(l).severity)) {
 const key = l.event.split('.')[0] || l.event;
 typeMap.set(key, (typeMap.get(key) || 0) + 1);
 }
 }
 const topTypes = [...typeMap.entries()].sort((a,b) => b[1]-a[1]).slice(0, 3);
 return { critical, errors, warnings, total: recent.length, lastError, topTypes };
 }, [logs]);

 if (loading && logs.length === 0) {
 return <div className="space-y-4"><div className="skeleton h-6 w-24" /><div className="skeleton h-10 w-48" /></div>;
 }

 return (
 <div className="page-enter">
 <div className="flex items-center justify-between mb-3">
 <div>
 <h1 className="font-heading text-[28px] font-semibold text-ink">运行日志</h1>
 <p className="text-sm text-ink-muted mt-1">{logs.length} 条记录</p>
 </div>
 <div className="flex gap-2">
 <button onClick={() => setAutoRefresh(!autoRefresh)}
 className={`text-xs px-2.5 py-1.5 rounded-lg border transition-colors ${
 autoRefresh ? 'bg-accent text-white border-accent' : 'border-border text-ink-muted hover:text-ink'
 }`}>
 {autoRefresh ? '⏸ 停止刷新' : '▶ 自动刷新'}
 </button>
 <button onClick={loadLogs}
 className="text-xs px-3 py-1.5 rounded-lg border border-border text-ink-muted hover:text-ink transition-colors">
 <RefreshCw size={13} className='mr-1' /> 刷新
 </button>
 </div>
 </div>

 {/* Error summary dashboard */}
 {(errorSummary.critical > 0 || errorSummary.errors > 0) && (
 <div className="mb-4 p-4 rounded-xl bg-destructive-soft/50 dark:bg-red-950/20 border border-destructive/20 ">
 <h3 className="text-xs font-semibold text-destructive mb-2">📊 错误摘要（最近50条）</h3>
 <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-[11px] mb-2">
 {errorSummary.critical > 0 && <div className="p-2 rounded-lg bg-destructive-soft/50 dark:bg-red-900/20 text-center"><div className="font-bold text-destructive">🔴 {errorSummary.critical}</div><div className="text-destructive">严重</div></div>}
 {errorSummary.errors > 0 && <div className="p-2 rounded-lg bg-orange-100/50 dark:bg-orange-900/20 text-center"><div className="font-bold text-orange-600">🟠 {errorSummary.errors}</div><div className="text-orange-500">错误</div></div>}
 {errorSummary.warnings > 0 && <div className="p-2 rounded-lg bg-warn-soft/50 text-center"><div className="font-bold text-warn">🟡 {errorSummary.warnings}</div><div className="text-warn">警告</div></div>}
 <div className="p-2 rounded-lg bg-paper border border-border text-center"><div className="font-bold text-ink">{errorSummary.total}</div><div className="text-ink-subtle">总计</div></div>
 </div>
 {errorSummary.topTypes.length > 0 && (
 <p className="text-[10px] text-destructive">
 最多错误类型：{errorSummary.topTypes.map(([k,v],i) => <span key={k}>{k}({v}次){i<errorSummary.topTypes.length-1?' · ':''}</span>)}
 </p>
 )}
 {errorSummary.lastError && (
 <p className="text-[10px] text-ink-subtle mt-1">
 最近错误：{fmtTime(errorSummary.lastError.created_at)} — {fmtDetail(errorSummary.lastError.detail).summary}
 </p>
 )}
 </div>
 )}

 {/* Filters */}
 <div className="flex gap-2 mb-4 flex-wrap">
 <select value={filterSeverity} onChange={e => setFilterSeverity(e.target.value)}
 className="text-xs rounded-md border border-input bg-card text-ink px-2 py-1.5">
 <option value="">全部级别</option>
 <option value="error-group">🔴🟠 错误</option>
 <option value="critical">🔴 严重</option>
 <option value="error">🟠 错误</option>
 <option value="warning">🟡 警告</option>
 </select>
 <select value={filterCategory} onChange={e => setFilterCategory(e.target.value)}
 className="text-xs rounded-md border border-input bg-card text-ink px-2 py-1.5">
 <option value="">全部类型</option>
 <option value="章节">章节</option>
 <option value="生成">生成</option>
 <option value="发布">发布</option>
 <option value="错误">错误</option>
 <option value="自动">自动</option>
 </select>
 <input value={filterNovel} onChange={e => setFilterNovel(e.target.value)}
 placeholder="小说ID..." className="text-xs rounded-md border border-input bg-card text-ink px-2 py-1.5 w-32 placeholder:text-ink-subtle" />
 {(filterSeverity || filterCategory || filterNovel) && (
 <button onClick={() => { setFilterSeverity(''); setFilterCategory(''); setFilterNovel(''); }}
 className="text-[10px] text-ink-muted hover:text-ink px-2">清除</button>
 )}
 <span className="text-[10px] text-ink-subtle self-center ml-auto">{filtered.length} 条匹配</span>
 </div>

 {/* Log list */}
 {filtered.length === 0 ? (
 <div className="text-center py-20">
 <ClipboardList size={48} className="text-ink-subtle mb-4 opacity-60" />
 <h3 className="font-heading text-xl font-semibold text-ink mb-1">
 {logs.length === 0 ? '暂无日志' : '无匹配日志'}
 </h3>
 <p className="text-sm text-ink-muted">
 {logs.length === 0 ? '创建小说并生成章节后，日志将显示在这里' : '尝试调整筛选条件'}
 </p>
 </div>
 ) : (
 <div className="space-y-0.5 max-w-[900px]">
 {filtered.map(log => {
 const cls = classifyLog(log);
 const cat = eventCategory(log);
 const detail = fmtDetail(log.detail);
 return (
 <div key={log.id}
 className={`rounded-lg border transition-all ${
 expanded === log.id ? 'border-accent/30 bg-accent-soft/5' :
 cls.severity === 'critical' ? 'border-red-100 dark:border-red-900/30 bg-destructive-soft/20 dark:bg-red-950/5' :
 cls.severity === 'error' ? 'border-orange-100 dark:border-orange-900/30 bg-orange-50/20 dark:bg-orange-950/5' :
 'border-transparent hover:border-border'
 }`}>
 <div onClick={() => setExpanded(expanded === log.id ? null : log.id)}
 className="flex items-center gap-2 px-3 py-2.5 cursor-pointer">
 <span className="text-xs shrink-0">{cls.emoji}</span>
 <span className="text-[10px] text-ink-subtle w-16 tabular-nums shrink-0">{fmtTime(log.created_at).slice(-8)}</span>
 <Badge variant="outline" className="text-[10px] shrink-0">{cat}</Badge>
 <span className="text-xs text-ink-muted truncate flex-1">{detail.summary}</span>
 <span className="text-[10px] text-ink-subtle shrink-0">{log.novel_id || '系统'}</span>
 </div>
 {expanded === log.id && (
 <div className="px-4 pb-3">
 <div className="flex gap-2 mb-2 text-[10px]">
 <span className="text-ink-subtle">事件：{log.event}</span>
 <span className="text-ink-subtle">时间：{fmtTime(log.created_at)}</span>
 {log.novel_id && <span className="text-ink-subtle">小说：{log.novel_id}</span>}
 </div>
 <pre className="text-[11px] text-ink-muted whitespace-pre-wrap font-mono bg-paper p-2.5 rounded-lg border border-border leading-relaxed overflow-x-auto max-h-[300px] overflow-y-auto">
 {detail.full}
 </pre>
 </div>
 )}
 </div>
 );
 })}
 </div>
 )}
 </div>
 );
}
