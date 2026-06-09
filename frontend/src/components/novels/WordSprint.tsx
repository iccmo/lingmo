import { useState, useEffect, useRef } from 'react';
import { Timer } from 'lucide-react';

interface Props {
 onComplete?: (wordsWritten: number) => void;
}

export function WordSprint({ onComplete }: Props) {
 const [running, setRunning] = useState(false);
 const [seconds, setSeconds] = useState(25 * 60); // 25 min default
 const [duration, setDuration] = useState(25);
 const [startWords, setStartWords] = useState(0);
 const [currentWords, setCurrentWords] = useState(0);
 const [show, setShow] = useState(false);
 const intervalRef = useRef<ReturnType<typeof setInterval>>(undefined);

 useEffect(() => {
 if (!running) return;
 intervalRef.current = setInterval(() => {
 setSeconds(s => {
 if (s <= 1) {
 setRunning(false);
 onComplete?.(Math.max(0, currentWords - startWords));
 return 0;
 }
 return s - 1;
 });
 }, 1000);
 return () => clearInterval(intervalRef.current);
 }, [running, currentWords, startWords, onComplete]);

 function start() {
 setSeconds(duration * 60);
 setStartWords(currentWords);
 setRunning(true);
 }

 function stop() {
 setRunning(false);
 clearInterval(intervalRef.current);
 }

 function reset() {
 stop();
 setSeconds(duration * 60);
 setStartWords(0);
 setCurrentWords(0);
 }

 const mins = Math.floor(seconds / 60);
 const secs = seconds % 60;
 const progress = 1 - seconds / (duration * 60);
 const wordsWritten = Math.max(0, currentWords - startWords);

 if (!show) {
 return (
 <button onClick={() => setShow(true)}
 className="text-[11px] text-ink-muted hover:text-accent px-2 py-1 rounded border border-border hover:border-accent/30 transition-colors">
 <Timer size={14} className='mr-1' /> 专注冲刺
 </button>
 );
 }

 return (
 <div className="fixed bottom-20 right-8 z-40 bg-card border border-border rounded-xl shadow-xl p-4 w-[260px] animate-[fadeSlideIn_0.2s_ease-out]">
 <div className="flex items-center justify-between mb-3">
 <h3 className="font-heading text-sm font-semibold text-ink"><Timer size={14} className='mr-1' /> 专注冲刺</h3>
 <button onClick={() => { stop(); setShow(false); }}
 className="text-xs text-ink-muted hover:text-ink">✕</button>
 </div>

 {/* Timer display */}
 <div className="text-center mb-3">
 <div className={`font-mono text-3xl font-bold tabular-nums ${running ? 'text-accent' : 'text-ink'}`}>
 {String(mins).padStart(2, '0')}:{String(secs).padStart(2, '0')}
 </div>
 <div className="h-1.5 bg-border rounded-full mt-2 overflow-hidden">
 <div className="h-full bg-accent rounded-full transition-all duration-1000"
 style={{ width: `${progress * 100}%` }} />
 </div>
 </div>

 {/* Duration selector */}
 {!running && (
 <div className="flex gap-1 mb-3 justify-center">
 {[15, 25, 45, 60].map(d => (
 <button key={d} onClick={() => { setDuration(d); setSeconds(d * 60); }}
 className={`text-[10px] px-2 py-0.5 rounded border transition-colors ${
 duration === d ? 'bg-accent text-white border-accent' : 'border-border text-ink-muted hover:text-ink'
 }`}>
 {d}min
 </button>
 ))}
 </div>
 )}

 {/* Words counter */}
 <div className="flex items-center justify-between text-[10px] text-ink-muted mb-3">
 <span>已写: {wordsWritten.toLocaleString()} 字</span>
 <span>速率: {running && seconds < duration * 60 ? Math.round(wordsWritten / ((duration * 60 - seconds) / 60)) : 0} 字/分</span>
 </div>

 {/* Controls */}
 <div className="flex gap-2">
 {!running ? (
 <button onClick={start}
 className="flex-1 text-xs py-1.5 rounded-md bg-accent text-white hover:bg-accent-hover transition-colors">
 ▶ 开始
 </button>
 ) : (
 <button aria-label="停止" onClick={stop}
 className="flex-1 text-xs py-1.5 rounded-md bg-warn-soft0 text-white hover:bg-amber-600 transition-colors">
 ⏸ 暂停
 </button>
 )}
 <button onClick={reset}
 className="text-xs px-3 py-1.5 rounded-md border border-border text-ink-muted hover:text-ink transition-colors">
 重置
 </button>
 </div>

 {/* Complete message */}
 {!running && seconds === 0 && wordsWritten > 0 && (
 <p className="text-[10px] text-success text-center mt-2 animate-[fadeSlideIn_0.3s_ease-out]">
 🎉 冲刺完成！写了 {wordsWritten.toLocaleString()} 字
 </p>
 )}
 </div>
 );
}
