import { useState, useEffect, useCallback } from 'react';
import { toast } from 'sonner';
import { PenLine, Target } from 'lucide-react';

function getTodayKey(): string {
 const d = new Date();
 return `daily-words-${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

export function WritingGoal() {
 const [goal, setGoal] = useState<number>(() => {
 try {
 const saved = localStorage.getItem('writing-goal');
 return saved ? parseInt(saved, 10) : 2000;
 } catch {
 return 2000;
 }
 });
 const [todayWords, setTodayWords] = useState<number>(0);
 const [editing, setEditing] = useState(false);
 const [inputValue, setInputValue] = useState(String(goal));

 const refreshWords = useCallback(() => {
 const key = getTodayKey();
 const words = parseInt(localStorage.getItem(key) || '0', 10) || 0;
 setTodayWords(words);
 }, []);

 useEffect(() => {
 refreshWords();

 // Poll every 5 seconds for word count changes
 const interval = setInterval(refreshWords, 5000);
 return () => clearInterval(interval);
 }, [refreshWords]);

 // Listen for storage changes from other components
 useEffect(() => {
 const handler = () => refreshWords();
 window.addEventListener('storage', handler);
 // Custom event for same-tab updates
 window.addEventListener('daily-words-updated', handler);
 return () => {
 window.removeEventListener('storage', handler);
 window.removeEventListener('daily-words-updated', handler);
 };
 }, [refreshWords]);

 function saveGoal(value: number) {
 const clean = Math.max(100, Math.min(50000, value));
 setGoal(clean);
 localStorage.setItem('writing-goal', String(clean));
 setEditing(false);
 toast.success(`写作目标已设为 ${clean.toLocaleString()} 字/天`);
 }

 const progress = goal > 0 ? Math.min(1, todayWords / goal) : 0;
 const pct = Math.round(progress * 100);
 const remaining = Math.max(0, goal - todayWords);
 const isMet = todayWords >= goal && goal > 0;

 const message = isMet
 ? '🎉 今日目标达成!'
 : todayWords > 0
 ? `还差 ${remaining.toLocaleString()} 字，加油!`
 : '今日尚未动笔，开始写作吧!';

 const barColor = isMet
 ? 'bg-success-soft0'
 : progress > 0.75
 ? 'bg-accent'
 : progress > 0.5
 ? 'bg-warn-soft0'
 : progress > 0
 ? 'bg-orange-500'
 : 'bg-border';

 return (
 <div className="mb-6 p-4 bg-card border border-border rounded-xl">
 <div className="flex items-center justify-between mb-3">
 <div className="flex items-center gap-2">
 <h3 className="text-xs font-semibold text-ink-muted uppercase tracking-wide">
 <Target size={12} className="inline" /> 写作目标
 </h3>
 {!editing && (
 <button
 onClick={() => { setInputValue(String(goal)); setEditing(true); }}
 className="text-[10px] text-ink-subtle hover:text-accent transition-colors"
 >
 <PenLine size={12} className="inline" /> 调整
 </button>
 )}
 </div>
 {editing ? (
 <div className="flex items-center gap-1.5">
 <input
 type="number"
 value={inputValue}
 onChange={e => setInputValue(e.target.value)}
 onKeyDown={e => {
 if (e.key === 'Enter') saveGoal(parseInt(inputValue) || 2000);
 if (e.key === 'Escape') setEditing(false);
 }}
 min={100}
 max={50000}
 className="w-20 text-xs text-center rounded border border-input bg-paper px-2 py-1
 focus:outline-none focus:border-accent"
 autoFocus
 />
 <span className="text-[10px] text-ink-muted">字/天</span>
 <button
 onClick={() => saveGoal(parseInt(inputValue) || 2000)}
 className="text-[10px] text-accent hover:underline"
 >
 保存
 </button>
 <button
 onClick={() => setEditing(false)}
 className="text-[10px] text-ink-muted hover:text-ink"
 >
 取消
 </button>
 </div>
 ) : (
 <span className="text-[11px] text-ink-muted tabular-nums">
 {todayWords.toLocaleString()} / {goal.toLocaleString()} 字
 </span>
 )}
 </div>

 {/* Progress bar */}
 <div className="h-3 bg-paper dark:bg-muted border border-border rounded-full overflow-hidden mb-2">
 <div
 className={`h-full rounded-full transition-all duration-700 ease-out ${barColor}`}
 style={{ width: `${Math.max(pct, todayWords > 0 ? 2 : 0)}%` }}
 />
 </div>

 {/* Stats row */}
 <div className="flex items-center justify-between text-[11px]">
 <span className={`font-medium ${isMet ? 'text-success' : todayWords > 0 ? 'text-ink' : 'text-ink-muted'}`}>
 {pct}% {message}
 </span>
 {!isMet && goal > 0 && (
 <span className="text-ink-subtle">
 {remaining > 0 && todayWords > 0
 ? `${Math.ceil(remaining / 500)} 分钟`
 : ''}
 </span>
 )}
 </div>
 </div>
 );
}
