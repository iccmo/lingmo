import { useEffect, useState, useRef } from 'react';
import { AlertTriangle, CheckCircle2, FileText } from 'lucide-react';

/** Simulated progress during long blocking phases */
function useSmoothProgress(status: string, realProgress: number): number {
 const [smooth, setSmooth] = useState(realProgress);
 const timer = useRef<ReturnType<typeof setInterval>>(undefined);

 useEffect(() => {
 if (status === 'generating' && realProgress <= 22) {
 const start = Date.now();
 timer.current = setInterval(() => {
 const elapsed = (Date.now() - start) / 1000;
 const simulated = Math.min(realProgress + 2, 10 + elapsed * 0.15);
 setSmooth(Math.min(simulated, 22));
 }, 500);
 return () => clearInterval(timer.current);
 }
 if (status === 'generating' && realProgress <= 52) {
 const start = Date.now();
 timer.current = setInterval(() => {
 const elapsed = (Date.now() - start) / 1000;
 const simulated = Math.min(realProgress + 2, 20 + elapsed * 0.3);
 setSmooth(Math.min(simulated, 52));
 }, 500);
 return () => clearInterval(timer.current);
 }
 setSmooth(realProgress);
 return () => clearInterval(timer.current);
 }, [status, realProgress]);

 return smooth;
}

function fmtElapsed(seconds: number): string {
 if (seconds < 60) return `${seconds}秒`;
 const m = Math.floor(seconds / 60);
 const s = seconds % 60;
 return `${m}分${s}秒`;
}

interface GenStatus {
 status: string;
 message: string;
 progress: number;
 quality_detail?: Record<string, number>;
 grade?: string;
 overall?: number;
 stream_content?: string;
}

const GATES = [
 { key: '构思', icon: '', desc: '分析前文·构思走向', range: [0, 20], detail: 'AI 正在阅读前文，分析剧情走向，构建章节框架。最长约60秒。' },
 { key: '草拟', icon: '', desc: '生成正文初稿', range: [20, 50], detail: 'AI 正在写作正文。同时生成2个候选版本，选出最佳。约40秒。' },
 { key: '评审', icon: '', desc: 'A级(≥0.8)·不达标重写', range: [50, 68], detail: 'LLM Judge 正在6维度评分。低于门槛自动重写（最多3次）。' },
 { key: '润色', icon: '', desc: '去AI味·文学提升', range: [68, 85], detail: '正在去除AI写作痕迹，提升文学质感。约25秒。' },
 { key: '质检', icon: '', desc: '事实核查·终审放行', range: [85, 100], detail: '最后审核：事实一致性、逻辑连贯性。通过即发布。' },
];

function gatePhase(progress: number): number {
 for (let i = GATES.length - 1; i >= 0; i--) {
 if (progress >= GATES[i].range[0]) return i;
 }
 return 0;
}

export function GenerationPipeline({ genStatus, onRetry }: {
 genStatus: GenStatus;
 onRetry: () => void;
}) {
 const isError = genStatus.status === 'error';
 const isComplete = genStatus.status === 'complete';
 const active = isError || isComplete ? -1 : gatePhase(genStatus.progress);

 // Desktop notification on complete
 useEffect(() => {
 if (!isComplete) return;
 if (!('Notification' in window)) return;
 if (Notification.permission === 'granted') {
 new Notification('章节生成完成', {
 body: genStatus.message.slice(0, 100),
 icon: '/favicon.ico',
 });
 } else if (Notification.permission !== 'denied') {
 Notification.requestPermission();
 }
 }, [isComplete]);

 // Elapsed time
 const [elapsed, setElapsed] = useState(0);
 const startTime = useRef(Date.now());

 useEffect(() => {
 if (isComplete || isError) return;
 startTime.current = Date.now();
 setElapsed(0);
 const timer = setInterval(() => {
 setElapsed(Math.round((Date.now() - startTime.current) / 1000));
 }, 1000);
 return () => clearInterval(timer);
 }, [genStatus.status, isComplete, isError]);

 const smoothProgress = useSmoothProgress(genStatus.status, genStatus.progress);

 return (
 <div className={`mb-4 p-4 rounded-xl border-2 transition-all duration-500 ${
 isError ? 'bg-destructive-soft/80 border-destructive/20 dark:bg-red-950/50 '
 : isComplete ? 'bg-success-soft/80 border-success/20 dark:bg-emerald-950/50 '
 : 'bg-accent-soft/80 border-accent/20'
 }`}>
 {/* Header */}
 <div className="flex items-center gap-2.5 mb-4">
 {isError ? (
 <span className="text-base"><AlertTriangle size={12} className="text-warn inline" /></span>
 ) : isComplete ? (
 <span className="text-base"><CheckCircle2 size={12} className="text-success inline" /></span>
 ) : (
 <span className="relative flex h-3 w-3">
 <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-accent opacity-75" />
 <span className="relative inline-flex rounded-full h-3 w-3 bg-accent" />
 </span>
 )}
 <span className={`text-sm font-semibold ${
 isError ? 'text-red-700 dark:text-red-300'
 : isComplete ? 'text-success dark:text-emerald-300'
 : 'text-ink'
 }`}>
 {isError ? '生成失败' : isComplete ? '章节完成' : '正在创作...'}
 </span>
 {!isComplete && !isError && (
 <span className="text-[10px] text-ink-muted tabular-nums font-mono ml-auto">
 {fmtElapsed(elapsed)}
 </span>
 )}
 {isError && (
 <button onClick={onRetry}
 className="ml-auto text-xs px-2.5 py-1 rounded-md border border-red-300 hover:bg-destructive-soft dark:border-red-700 dark:hover:bg-red-900 transition-colors text-destructive ">
 重试
 </button>
 )}
 </div>

 {/* Pipeline for generating state */}
 {!isError && !isComplete && (
 <div className="space-y-3">
 {/* Progress bar with gate markers */}
 <div className="relative h-2 bg-border/60 rounded-full overflow-hidden">
 {GATES.map((g, _i) => (
 <div key={g.key} className="absolute top-0 w-0.5 h-full bg-white/20"
 style={{ left: `${g.range[1]}%` }} />
 ))}
 <div className="h-full bg-gradient-to-r from-accent/70 via-accent to-accent rounded-full transition-all duration-500"
 style={{ width: `${Math.max(smoothProgress, 3)}%` }} />
 <span className="absolute right-0 top-0 h-full flex items-center pr-2 text-[9px] text-white/70 font-mono tabular-nums">
 {Math.round(smoothProgress)}%
 </span>
 </div>

 {/* Gate labels */}
 <div className="flex justify-between">
 {GATES.map((g, i) => {
 const done = genStatus.progress >= g.range[1];
 const current = i === active;
 const upcoming = genStatus.progress < g.range[0];
 return (
 <div key={g.key} className="flex flex-col items-center gap-1" style={{ width: `${100 / GATES.length}%` }}>
 <span className={`text-base transition-all duration-300 ${
 done ? '' : upcoming ? 'opacity-30 grayscale' : current ? 'scale-110' : 'opacity-60'
 }`}>
 {g.icon}
 </span>
 <span className={`text-[10px] font-medium transition-colors ${
 done ? 'text-success '
 : current ? 'text-accent'
 : 'text-ink-subtle'
 }`}>
 {g.key}
 </span>
 {done && <span className="text-[9px] text-success">✓</span>}
 </div>
 );
 })}
 </div>

 {/* Current gate detail */}
 {active >= 0 && (
 <div className="p-2.5 rounded-lg bg-paper/50 border border-border/50 text-[11px]">
 <span className="text-accent font-medium">{GATES[active].icon} {GATES[active].key}阶段</span>
 <span className="text-ink-muted ml-2">{GATES[active].detail}</span>
 </div>
 )}

 {/* Live preview of streaming content */}
 {genStatus.stream_content && (
 <div className="p-3 rounded-lg bg-paper/50 border border-border/50 max-h-[240px] overflow-y-auto"
 ref={el => {
 if (el) el.scrollTop = el.scrollHeight;
 }}>
 <div className="flex items-center justify-between mb-1.5">
 <span className="text-[10px] text-ink-muted"><FileText size={12} className="inline" /> 实时预览</span>
 <span className="text-[9px] text-ink-subtle tabular-nums">{genStatus.stream_content.length} 字</span>
 </div>
 <div className="text-[13px] text-ink leading-[2.1] font-[var(--font-editor)] whitespace-pre-wrap animate-[fadeSlideIn_0.3s_ease-out]">
 {genStatus.stream_content}
 <span className="inline-block w-1.5 h-[1.1em] bg-accent animate-pulse ml-0.5 align-text-bottom rounded-sm" />
 </div>
 </div>
 )}

 {/* Status message + retry counter */}
 <p className="text-[11px] text-ink-muted text-center flex items-center justify-center gap-2 flex-wrap">
 <span>{genStatus.message}</span>
 {genStatus.message.includes('重写') && (() => {
 const match = genStatus.message.match(/第(\d+)次/);
 const retryNum = match ? parseInt(match[1]) : 1;
 const maxRetries = 3;
 return (
 <span className="inline-flex items-center gap-1">
 <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${
 retryNum >= maxRetries ? 'bg-destructive-soft text-destructive dark:bg-red-950 '
 : retryNum >= 2 ? 'bg-warn-soft text-warn dark:bg-amber-950 '
 : 'bg-info-soft text-info dark:bg-sky-950 '
 }`}>
 重试 {retryNum}/{maxRetries}
 </span>
 {genStatus.overall !== undefined && genStatus.overall > 0 && (
 <span className={`text-[10px] tabular-nums font-mono ${
 (genStatus.overall || 0) >= 0.8 ? 'text-success'
 : (genStatus.overall || 0) >= 0.65 ? 'text-warn'
 : 'text-destructive'
 }`}>
 Q={(genStatus.overall || 0).toFixed(2)}
 </span>
 )}
 </span>
 );
 })()}
 </p>
 </div>
 )}

 {/* Complete state */}
 {isComplete && (
 <div className="space-y-2">
 {/* A-grade celebration */}
 {genStatus.progress >= 90 && (
 <div className="text-center py-1 animate-[fadeSlideIn_0.3s_ease-out]">
 <span className="inline-flex items-center gap-1 px-3 py-1 rounded-full bg-gradient-to-r from-amber-100 to-emerald-100 dark:from-amber-900/30 dark:to-emerald-900/30 border border-success/20 text-xs font-bold text-success dark:text-emerald-300">
 A级品质 · 神作标准
 </span>
 </div>
 )}
 <div className="h-2 bg-emerald-200 dark:bg-emerald-800 rounded-full overflow-hidden">
 <div className="h-full bg-gradient-to-r from-emerald-400 to-emerald-500 rounded-full w-full" />
 </div>
 <div className="flex justify-between">
 {GATES.map(g => (
 <div key={g.key} className="flex flex-col items-center gap-0.5">
 <span className="text-sm">{g.icon}</span>
 <span className="text-[9px] text-success ">✓</span>
 </div>
 ))}
 </div>
 <p className="text-[11px] text-success text-center font-medium">
 {genStatus.message}
 <span className="text-ink-subtle ml-2 font-normal">耗时 {fmtElapsed(elapsed)}</span>
 </p>
 {/* Quality breakdown */}
 {genStatus.quality_detail && Object.keys(genStatus.quality_detail).length > 0 && (
 <div className="mt-2 pt-2 border-t border-success/20 grid grid-cols-3 gap-1.5">
 {Object.entries(genStatus.quality_detail).slice(0, 6).map(([k, v]) => (
 <div key={k} className="text-center p-1.5 rounded-lg bg-success-soft/50 dark:bg-emerald-950/30">
 <div className="text-[10px] text-ink-muted">{k}</div>
 <div className={`text-xs font-bold tabular-nums ${Number(v) >= 8 ? 'text-success' : Number(v) >= 6 ? 'text-warn' : 'text-destructive'}`}>
 {Number(v).toFixed(1)}
 </div>
 </div>
 ))}
 </div>
 )}
 </div>
 )}

 {/* Error state */}
 {isError && (
 <div className="space-y-2">
 <p className="text-xs text-destructive leading-relaxed font-medium">
 {genStatus.message.includes('Timeout') ? 'API 超时——网络延迟或模型响应过慢'
 : genStatus.message.includes('authentication') || genStatus.message.includes('Invalid') ? '🔑 API Key 无效——请在设置页更新'
 : genStatus.message.includes('rate') ? '🚦 请求频率过高——请稍后重试'
 : `${genStatus.message}`}
 <span className="text-ink-subtle ml-2 font-normal">耗时 {fmtElapsed(elapsed)}</span>
 </p>
 <p className="text-[10px] text-destructive dark:text-destructive">
 {genStatus.message}
 </p>
 </div>
 )}
 </div>
 );
}
