import { useState, useEffect, useRef, useCallback } from 'react';

const MOTIVATIONAL_QUOTES = [
 '每个伟大的故事都始于一个决定。继续写吧。',
 '写作不是等灵感来了才动笔，而是动笔后灵感才会来。',
 '最好的章节往往是写出来之后才发现的。',
 '别想太多，把手指放在键盘上，让文字流动。',
 '写作是一种马拉松，而不是短跑。保持节奏。',
 '你今天的每一个字，都在塑造明天的故事。',
 '写作的魔力在于：你创造了从未存在的世界。',
 '不要追求完美，追求完成。完美在修改中诞生。',
 '每一个句子都是一步，每一步都让你更接近目标。',
 '相信你的声音，故事只有你能讲述。',
 '写作是一种思考方式——用笔来整理你的思绪。',
 '最难的永远是第一个字，但你已经写下了它。',
];

const POMODORO_DURATION = 25 * 60; // 25 minutes in seconds
const BREAK_DURATION = 5 * 60; // 5 minutes

function getTodayPomodoroKey(): string {
 const d = new Date();
 return `pomodoro-sessions-${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

function playBeep() {
 try {
 const ctx = new (window.AudioContext || (window as any).webkitAudioContext)();
 const duration = 0.15;
 const frequencies = [880, 1100, 1320];

 frequencies.forEach((freq, i) => {
 const osc = ctx.createOscillator();
 const gain = ctx.createGain();
 osc.type = 'sine';
 osc.frequency.setValueAtTime(freq, ctx.currentTime + i * duration);
 gain.gain.setValueAtTime(0.3, ctx.currentTime + i * duration);
 gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + i * duration + duration);
 osc.connect(gain);
 gain.connect(ctx.destination);
 osc.start(ctx.currentTime + i * duration);
 osc.stop(ctx.currentTime + i * duration + duration);
 });

 setTimeout(() => ctx.close(), 1000);
 } catch {
 // Web Audio API not available
 }
}

export function PomodoroTimer() {
 const [show, setShow] = useState(false);
 const [running, setRunning] = useState(false);
 const [isBreak, setIsBreak] = useState(false);
 const [seconds, setSeconds] = useState(POMODORO_DURATION);
 const [totalDuration, setTotalDuration] = useState(POMODORO_DURATION);
 const [sessionsToday, setSessionsToday] = useState<number>(() => {
 try {
 return parseInt(localStorage.getItem(getTodayPomodoroKey()) || '0', 10);
 } catch {
 return 0;
 }
 });
 const [quote, setQuote] = useState<string>('');
 const [showQuote, setShowQuote] = useState(false);
 const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

 const clearTimer = useCallback(() => {
 if (intervalRef.current) {
 clearInterval(intervalRef.current);
 intervalRef.current = null;
 }
 }, []);

 // Timer tick
 useEffect(() => {
 if (!running) return;

 intervalRef.current = setInterval(() => {
 setSeconds(s => {
 if (s <= 1) {
 clearTimer();
 setRunning(false);
 playBeep();

 if (isBreak) {
 // Break finished -> back to work
 setIsBreak(false);
 setTotalDuration(POMODORO_DURATION);
 setShowQuote(false);
 return POMODORO_DURATION;
 } else {
 // Pomodoro finished -> record session + start break
 setSessionsToday(prev => {
 const next = prev + 1;
 localStorage.setItem(getTodayPomodoroKey(), String(next));
 return next;
 });
 setIsBreak(true);
 setTotalDuration(BREAK_DURATION);
 setQuote(MOTIVATIONAL_QUOTES[Math.floor(Math.random() * MOTIVATIONAL_QUOTES.length)]);
 setShowQuote(true);
 return BREAK_DURATION;
 }
 }
 return s - 1;
 });
 }, 1000);

 return clearTimer;
 }, [running, isBreak, clearTimer]);

 // Cleanup on unmount
 useEffect(() => {
 return () => clearTimer();
 }, [clearTimer]);

 function startTimer() {
 if (isBreak) {
 setIsBreak(false);
 setTotalDuration(POMODORO_DURATION);
 setSeconds(POMODORO_DURATION);
 setShowQuote(false);
 }
 setRunning(true);
 }

 function pauseTimer() {
 setRunning(false);
 clearTimer();
 }

 function resetTimer() {
 clearTimer();
 setRunning(false);
 setIsBreak(false);
 setTotalDuration(POMODORO_DURATION);
 setSeconds(POMODORO_DURATION);
 setShowQuote(false);
 }

 const mins = Math.floor(seconds / 60);
 const secsRem = seconds % 60;
 const progress = totalDuration > 0 ? 1 - seconds / totalDuration : 0;

 // Background color shifts from green -> yellow -> red
 const remainingRatio = totalDuration > 0 ? seconds / totalDuration : 1;
 let bgColor: string;
 if (isBreak) {
 bgColor = 'from-emerald-400 to-emerald-500';
 } else if (remainingRatio > 0.6) {
 bgColor = 'from-emerald-500 to-emerald-600';
 } else if (remainingRatio > 0.3) {
 bgColor = 'from-amber-400 to-amber-500';
 } else if (remainingRatio > 0.1) {
 bgColor = 'from-orange-400 to-red-500';
 } else {
 bgColor = 'from-red-500 to-red-600';
 }

 const timeColor = isBreak
 ? 'text-white'
 : remainingRatio > 0.6
 ? 'text-white'
 : remainingRatio > 0.3
 ? 'text-amber-900'
 : remainingRatio > 0.1
 ? 'text-white'
 : 'text-white';

 return (
 <>
 {/* Floating trigger button */}
 {!show && (
 <button
 onClick={() => setShow(true)}
 className="fixed bottom-20 left-6 z-40 w-12 h-12 rounded-full bg-card border-2 border-border
 shadow-lg hover:shadow-xl hover:border-accent/30 transition-all hover:scale-110 active:scale-95
 flex items-center justify-center text-xl select-none"
 title="番茄钟写作模式"
 >
 🍅
 </button>
 )}

 {/* Timer panel */}
 {show && (
 <div className="fixed bottom-20 left-6 z-40 bg-card border border-border rounded-xl shadow-xl p-4 w-[280px] animate-[fadeSlideIn_0.2s_ease-out]">
 {/* Header */}
 <div className="flex items-center justify-between mb-3">
 <h3 className="font-heading text-sm font-semibold text-ink">
 {isBreak ? '☕ 休息时间' : '🍅 番茄钟'}
 </h3>
 <button
 onClick={() => { pauseTimer(); setShow(false); }}
 className="text-xs text-ink-muted hover:text-ink"
 >
 ✕
 </button>
 </div>

 {/* Timer display with color background */}
 <div className={`relative mb-3 rounded-xl overflow-hidden`}>
 <div
 className={`bg-gradient-to-br ${bgColor} p-6 text-center transition-all duration-1000`}
 >
 <div className={`font-mono text-4xl font-bold tabular-nums ${timeColor}`}>
 {String(mins).padStart(2, '0')}:{String(secsRem).padStart(2, '0')}
 </div>
 <div className={`text-xs mt-1 ${timeColor} opacity-80`}>
 {isBreak ? `休息 ${BREAK_DURATION / 60} 分钟` : `${POMODORO_DURATION / 60} 分钟专注`}
 </div>
 </div>
 {/* Pulse animation when running */}
 {running && (
 <div
 className="absolute inset-0 rounded-xl pointer-events-none animate-pulse"
 style={{
 boxShadow: 'inset 0 0 0 2px rgba(255,255,255,0.3)',
 }}
 />
 )}
 </div>

 {/* Progress bar */}
 <div className="h-1.5 bg-border rounded-full mb-3 overflow-hidden">
 <div
 className={`h-full rounded-full transition-all duration-1000 ${
 isBreak ? 'bg-emerald-400' : 'bg-white/80 dark:bg-white/60'
 }`}
 style={{ width: `${progress * 100}%` }}
 />
 </div>

 {/* Controls */}
 <div className="flex gap-2 mb-3">
 {!running ? (
 <button
 onClick={startTimer}
 className="flex-1 text-xs py-2 rounded-md bg-accent text-white hover:bg-accent-hover transition-colors font-medium"
 >
 ▶ {isBreak ? '开始休息' : '开始专注'}
 </button>
 ) : (
 <button
 onClick={pauseTimer}
 className="flex-1 text-xs py-2 rounded-md bg-warn-soft0 text-white hover:bg-amber-600 transition-colors font-medium"
 >
 ⏸ 暂停
 </button>
 )}
 <button
 onClick={resetTimer}
 className="text-xs px-3 py-2 rounded-md border border-border text-ink-muted hover:text-ink transition-colors"
 >
 重置
 </button>
 </div>

 {/* Session counter */}
 <div className="flex items-center justify-between text-[10px] text-ink-muted mb-2">
 <span>今日完成</span>
 <span className="font-semibold text-accent tabular-nums">
 {sessionsToday} 个番茄
 </span>
 </div>

 {/* Motivational quote during break */}
 {showQuote && quote && (
 <div className="p-2.5 rounded-lg bg-accent-soft/50 border border-accent/10 text-xs text-ink leading-relaxed italic animate-[fadeSlideIn_0.3s_ease-out]">
 "{quote}"
 </div>
 )}
 </div>
 )}
 </>
 );
}
