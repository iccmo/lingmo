import { useState, useEffect } from 'react';
import { ConsistencyScoreView } from './ConsistencyScoreView';

interface GenStatus {
 status: string;
 message: string;
 progress: number;
 overall?: number;
 grade?: string;
}

interface Props {
 novelId: string;
 chapterNum: number | null;
 genStatus: GenStatus | null;
}

interface QualityGateData {
 status: string;
 character_count?: number;
 active_foreshadowing?: number;
 errors?: number;
}

interface ConstraintsData {
 next_chapter: number;
 hard_count: number;
 soft_count: number;
 preview?: string;
}

const GATE_STATUS_MAP: Record<string, { icon: string; label: string; color: string }> = {
 good: { icon: '', label: '良好', color: 'text-success' },
 warning: { icon: '', label: '注意', color: 'text-warn' },
 error: { icon: '🔴', label: '需修复', color: 'text-destructive' },
};

const CARD_TITLE_CLASSES = 'text-[11px] font-semibold text-ink-muted uppercase tracking-wide mb-2';

export function WriterContext({ novelId, genStatus }: Props) {
 const [qualityExpanded, setQualityExpanded] = useState(true);
 const [constraintsExpanded, setConstraintsExpanded] = useState(true);
 const [consistencyExpanded, setConsistencyExpanded] = useState(true);

 // Quality Gate
 const [qualityData, setQualityData] = useState<QualityGateData | null>(null);
 const [qualityLoading, setQualityLoading] = useState(true);

 useEffect(() => {
 setQualityLoading(true);
 fetch(`/api/novels/${novelId}/quality-gate`)
 .then((r) => r.json())
 .then(setQualityData)
 .catch(() => setQualityData(null))
 .finally(() => setQualityLoading(false));
 }, [novelId]);

 // Constraints
 const [constraintsData, setConstraintsData] = useState<ConstraintsData | null>(null);
 const [constraintsLoading, setConstraintsLoading] = useState(true);

 useEffect(() => {
 setConstraintsLoading(true);
 fetch(`/api/novels/${novelId}/preview-constraints?level=L1`)
 .then((r) => r.json())
 .then(setConstraintsData)
 .catch(() => setConstraintsData(null))
 .finally(() => setConstraintsLoading(false));
 }, [novelId]);

 const gateStatus = qualityData ? (GATE_STATUS_MAP[qualityData.status] ?? GATE_STATUS_MAP.warning) : null;

 return (
 <aside className="space-y-3 w-full">
 {/* Quality Card */}
 <div className="bg-card border border-border rounded-lg p-3">
 <button
 type="button"
 className="flex items-center justify-between w-full text-left"
 onClick={() => setQualityExpanded((v) => !v)}
 >
 <h3 className={CARD_TITLE_CLASSES}>质量门槛</h3>
 <span className="text-[10px] text-ink-subtle">
 {qualityExpanded ? '收起' : '展开'}
 </span>
 </button>
 {qualityExpanded && (
 <div className="space-y-2">
 {qualityLoading ? (
 <p className="text-xs text-ink-subtle">加载中...</p>
 ) : qualityData && gateStatus ? (
 <>
 <p className={`text-sm font-medium ${gateStatus.color}`}>
 {gateStatus.icon} {gateStatus.label}
 </p>
 <p className="text-xs text-ink-subtle">
 {qualityData.character_count ?? 0}角色 · {qualityData.active_foreshadowing ?? 0}伏笔 · {qualityData.errors ?? 0}错
 </p>
 </>
 ) : (
 <p className="text-xs text-ink-subtle">暂无质量数据</p>
 )}
 </div>
 )}
 </div>

 {/* Constraints Card */}
 <div className="bg-card border border-border rounded-lg p-3">
 <button
 type="button"
 className="flex items-center justify-between w-full text-left"
 onClick={() => setConstraintsExpanded((v) => !v)}
 >
 <h3 className={CARD_TITLE_CLASSES}>写作约束</h3>
 <span className="text-[10px] text-ink-subtle">
 {constraintsExpanded ? '收起' : '展开'}
 </span>
 </button>
 {constraintsExpanded && (
 <div className="space-y-2">
 {constraintsLoading ? (
 <p className="text-xs text-ink-subtle">加载中...</p>
 ) : constraintsData ? (
 <>
 <p className="text-xs text-ink-subtle">
 第{constraintsData.next_chapter}章约束 · {constraintsData.hard_count}硬/{constraintsData.soft_count}软
 </p>
 {constraintsData.preview ? (
 <p className="text-[10px] text-ink-subtle whitespace-pre-wrap max-h-24 overflow-y-auto leading-relaxed">
 {constraintsData.preview.length > 300
 ? `${constraintsData.preview.slice(0, 300)}...`
 : constraintsData.preview}
 </p>
 ) : (
 <p className="text-xs text-ink-subtle">(暂无约束)</p>
 )}
 </>
 ) : (
 <p className="text-xs text-ink-subtle">(暂无约束)</p>
 )}
 </div>
 )}
 </div>

 {/* Consistency Card */}
 <div className="bg-card border border-border rounded-lg p-3">
 <button
 type="button"
 className="flex items-center justify-between w-full text-left"
 onClick={() => setConsistencyExpanded((v) => !v)}
 >
 <h3 className={CARD_TITLE_CLASSES}>一致性评分</h3>
 <span className="text-[10px] text-ink-subtle">
 {consistencyExpanded ? '收起' : '展开'}
 </span>
 </button>
 {consistencyExpanded && <ConsistencyScoreView novelId={novelId} />}
 </div>

 {/* Generation Status */}
 {genStatus && (
 <div className="bg-card border border-border rounded-lg p-3">
 <h3 className={CARD_TITLE_CLASSES}>生成状态</h3>
 <div className="space-y-2">
 <p className="text-xs text-ink">{genStatus.message}</p>
 {genStatus.progress > 0 && (
 <div className="h-2 bg-paper rounded-full overflow-hidden">
 <div
 className="h-full bg-info-soft0 rounded-full transition-all duration-500"
 style={{ width: `${Math.min(genStatus.progress, 100)}%` }}
 />
 </div>
 )}
 {genStatus.overall !== undefined && (
 <div className="flex items-center gap-2">
 <span className="text-xs text-ink-subtle">质量: {genStatus.overall}</span>
 {genStatus.grade && (
 <span className="text-[10px] px-1.5 py-0.5 rounded border border-warn/20 bg-warn-soft text-warn font-medium">
 {genStatus.grade}
 </span>
 )}
 </div>
 )}
 </div>
 </div>
 )}
 </aside>
 );
}
