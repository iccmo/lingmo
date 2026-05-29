import { useState, useEffect } from 'react';

interface Props { novelId: string }

export function WriterStatusBar({ novelId }: Props) {
 const [gate, setGate] = useState<any>(null);
 const [constraints, setConstraints] = useState<any>(null);
 const [showConstraints, setShowConstraints] = useState(false);

 useEffect(() => {
 fetch(`/api/novels/${novelId}/quality-gate`)
 .then(r => r.json())
 .then(setGate)
 .catch(() => {});
 fetch(`/api/novels/${novelId}/preview-constraints?level=L1`)
 .then(r => r.json())
 .then(setConstraints)
 .catch(() => {});
 }, [novelId]);

 const gateColor = gate?.gate?.includes('良好') ? 'text-success'
 : gate?.gate?.includes('注意') ? 'text-warn'
 : 'text-destructive';

 return (
 <div className="flex items-center gap-3 mb-3 text-[11px]">
 {/* Quality Gate */}
 {gate && (
 <span className={`flex items-center gap-1 px-2 py-0.5 rounded-full border ${
 gate.gate === '良好' ? 'border-success/20 bg-success-soft dark:bg-emerald-950/20'
 : 'border-warn/20 bg-warn-soft dark:bg-amber-950/20'
 }`}>
 <span className={gateColor}>{gate.gate}</span>
 </span>
 )}

 {/* Stats */}
 {gate && (
 <span className="text-ink-subtle">
 {gate.character_count}角色 · {gate.active_foreshadowing}伏笔 · {gate.errors || 0}错
 </span>
 )}

 {/* Constraint Preview Toggle */}
 <button onClick={() => setShowConstraints(!showConstraints)}
 className="text-accent hover:underline">
 {constraints ? `约束L1·${constraints.hard_count}条` : '加载约束…'}
 </button>

 {/* Expanded Constraint Preview */}
 {showConstraints && constraints && (
 <div className="absolute top-full left-0 mt-1 z-30 p-3 rounded-lg bg-card border border-border shadow-xl w-80 text-[10px]">
 <div className="flex items-center justify-between mb-1">
 <span className="font-medium text-ink">第{constraints.next_chapter}章约束</span>
 <span className="text-ink-subtle">{constraints.hard_count}硬/{constraints.soft_count}软</span>
 </div>
 <pre className="text-ink whitespace-pre-wrap max-h-[200px] overflow-y-auto">
 {constraints.preview || '(暂无约束 — 生成一章后自动填充)'}
 </pre>
 <div className="flex gap-2 mt-1 text-ink-subtle">
 {Object.entries(constraints.all_levels || {}).map(([level, info]: [string, any]) => (
 <span key={level}>{level}:{info.chars}字</span>
 ))}
 </div>
 </div>
 )}
 </div>
 );
}
