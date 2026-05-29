import { useMemo } from 'react';

// Daily word count log: { "2026-05-22": 2500, ... }
const STORAGE_KEY = 'writing-daily-log';

export function logDailyWords(words: number) {
 const today = new Date().toISOString().slice(0, 10);
 try {
 const log = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}');
 log[today] = (log[today] || 0) + words;
 localStorage.setItem(STORAGE_KEY, JSON.stringify(log));
 } catch { /* skip */ }
}

function getIntensity(count: number, max: number): string {
 if (count === 0) return 'bg-border/30';
 const pct = count / (max || 1);
 if (pct > 0.75) return 'bg-success-soft0';
 if (pct > 0.5) return 'bg-emerald-400';
 if (pct > 0.25) return 'bg-emerald-300';
 return 'bg-emerald-200 dark:bg-emerald-800';
}

interface DayCell {
 date: Date;
 count: number;
 iso: string;
}

export function WritingCalendar() {
 const { days, maxCount, streak, totalDays, totalWords } = useMemo(() => {
 // Read from localStorage daily log
 let dailyMap: Record<string, number> = {};
 try {
 dailyMap = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}');
 } catch { /* use empty */ }

 // Generate last 84 days (12 weeks)
 const cells: DayCell[] = [];
 const now = new Date();
 let max = 0;
 for (let i = 83; i >= 0; i--) {
 const d = new Date(now);
 d.setDate(d.getDate() - i);
 const iso = d.toISOString().slice(0, 10);
 const count = dailyMap[iso] || 0;
 if (count > max) max = count;
 cells.push({ date: d, count, iso });
 }

 // Calculate current streak (consecutive days with writing)
 let currentStreak = 0;
 for (let i = cells.length - 1; i >= 0; i--) {
 if (cells[i].count > 0) currentStreak++;
 else break;
 }

 const totalW = cells.reduce((s, c) => s + c.count, 0);
 return {
 days: cells,
 maxCount: max,
 streak: currentStreak,
 totalDays: cells.filter(c => c.count > 0).length,
 totalWords: totalW,
 };
 }, []);

 // Group into weeks (columns)
 const weeks: DayCell[][] = [];
 for (let i = 0; i < days.length; i += 7) {
 weeks.push(days.slice(i, i + 7));
 }

 const dayLabels = ['一', '', '三', '', '五', '', '日'];

 return (
 <div className="p-4 bg-card border border-border rounded-xl">
 <div className="flex items-center justify-between mb-3">
 <div>
 <h3 className="font-heading text-base font-semibold text-ink">写作日历</h3>
 <p className="text-[11px] text-ink-muted mt-0.5">过去12周</p>
 </div>
 <div className="flex gap-3 text-xs">
 <div className="text-center">
 <div className="font-heading text-lg font-semibold text-accent">{streak}</div>
 <div className="text-[10px] text-ink-muted">连续天数</div>
 </div>
 <div className="text-center">
 <div className="font-heading text-lg font-semibold text-ink">{totalDays}</div>
 <div className="text-[10px] text-ink-muted">写作天数</div>
 </div>
 <div className="text-center">
 <div className="font-heading text-lg font-semibold text-ink">{totalWords.toLocaleString()}</div>
 <div className="text-[10px] text-ink-muted">总字数</div>
 </div>
 </div>
 </div>

 {/* Heatmap grid */}
 <div className="flex gap-0.5">
 {/* Day labels */}
 <div className="flex flex-col gap-0.5 mr-1 pt-[14px]">
 {dayLabels.map((l, i) => (
 <span key={i} className="text-[8px] text-ink-subtle h-3 w-3 flex items-center justify-center">
 {l}
 </span>
 ))}
 </div>
 {/* Week columns */}
 {weeks.map((week, wi) => (
 <div key={wi} className="flex flex-col gap-0.5">
 {/* Month label on first week of month */}
 {week[0] && week[0].date.getDate() <= 7 && (
 <span className="text-[8px] text-ink-subtle h-3 mb-0.5">
 {week[0].date.getMonth() + 1}月
 </span>
 )}
 {week[0] && week[0].date.getDate() > 7 && wi === 0 && (
 <span className="text-[8px] text-ink-subtle h-3 mb-0.5">&nbsp;</span>
 )}
 {week.map((cell, di) => (
 <div key={di}
 className={`w-3 h-3 rounded-sm ${getIntensity(cell.count, maxCount)}`}
 title={`${cell.iso}: ${cell.count.toLocaleString()} 字`}
 />
 ))}
 </div>
 ))}
 </div>

 {/* Legend */}
 <div className="flex items-center gap-1 mt-3 justify-end">
 <span className="text-[9px] text-ink-subtle mr-1">少</span>
 {['bg-border/30', 'bg-emerald-200 dark:bg-emerald-800', 'bg-emerald-300', 'bg-emerald-400', 'bg-success-soft0'].map((c, i) => (
 <div key={i} className={`w-2.5 h-2.5 rounded-sm ${c}`} />
 ))}
 <span className="text-[9px] text-ink-subtle ml-1">多</span>
 </div>
 </div>
 );
}
