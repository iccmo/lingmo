import { useMemo } from 'react';
import type { ChapterMeta } from 'src/types';
import { Palette, AlertTriangle, CheckCircle2 } from 'lucide-react';

interface EmotionProfile {
 tension: number; // 紧张
 curiosity: number; // 好奇
 satisfaction: number;// 爽感/满足
 sadness: number; // 悲伤/感动
 humor: number; // 幽默
 fear: number; // 恐惧
}

const EMOTION_PATTERNS: Record<keyof EmotionProfile, RegExp> = {
 tension: /紧张|危机|危险|生死|倒计时|最后|来不及|突然|猛然|紧急|搏斗|激战/,
 curiosity: /秘密|真相|谜|谁|为什么|怎么|难道|竟然|原来|隐藏|发现|揭露/,
 satisfaction: /突破|升级|成功|赢了|击败|获得|奖励|突破|进步|成长|圆满/,
 sadness: /泪|哭|悲伤|死|失去|离别|回忆|遗憾|痛|伤|孤独|寂寞/,
 humor: /笑|搞笑|逗|吐槽|欢乐|囧|尴尬|滑稽|诙谐|调皮/,
 fear: /恐怖|鬼|尸|阴森|尖叫|毛骨悚然|诡异|黑暗|深渊|未知/,
};

function emotionLabel(key: string): string {
 const map: Record<string, string> = {
 tension: '紧张', curiosity: '好奇', satisfaction: '爽感',
 sadness: '感动', humor: '幽默', fear: '恐惧',
 };
 return map[key] || key;
}

function emotionColor(key: string): string {
 const map: Record<string, string> = {
 tension: 'bg-red-400', curiosity: 'bg-purple-400', satisfaction: 'bg-emerald-400',
 sadness: 'bg-blue-400', humor: 'bg-amber-400', fear: 'bg-zinc-500',
 };
 return map[key] || 'bg-zinc-400';
}

function analyzeEmotions(summary: string): EmotionProfile {
 const len = Math.max(1, summary.length);
 const result: any = {};
 for (const [key, pattern] of Object.entries(EMOTION_PATTERNS)) {
 const matches = (summary.match(pattern) || []).length;
 result[key] = Math.min(100, Math.round((matches / Math.min(len, 300)) * 100 * 3));
 }
 return result as EmotionProfile;
}

export function EmotionRecipe({ chapters }: { chapters?: ChapterMeta[] }) {
 const data = useMemo(() => {
 if (!chapters) return [];
 return chapters
 .filter(c => c.word_count > 0 && c.summary)
 .slice(-10)
 .map(ch => ({
 chapter: ch.number,
 title: ch.title,
 emotions: analyzeEmotions(ch.summary || ''),
 }));
 }, [chapters]);

 if (data.length < 2) return null;

 // Find dominant emotion per chapter
 const dominant = data.map(d => {
 const entries = Object.entries(d.emotions) as [keyof EmotionProfile, number][];
 const max = entries.reduce((a, b) => a[1] > b[1] ? a : b);
 return { ...d, dominant: max[0], dominantVal: max[1] };
 });

 return (
 <div className="p-4 bg-card border border-border rounded-xl">
 <h3 className="font-heading text-base font-semibold text-ink mb-3"><Palette size={16} className='mr-1.5 text-accent' /> 情绪配方</h3>
 <p className="text-[11px] text-ink-muted mb-3">最近 10 章的情绪构成分析</p>

 <div className="space-y-2">
 {dominant.map(d => (
 <div key={d.chapter} className="flex items-center gap-2 text-[11px]">
 <span className="text-ink-subtle w-10 tabular-nums shrink-0">Ch{d.chapter}</span>
 {/* Emotion bars */}
 <div className="flex-1 h-3 bg-border/50 rounded-full overflow-hidden flex">
 {(Object.entries(d.emotions) as [keyof EmotionProfile, number][]).map(([key, val]) => (
 <div key={key}
 className={`${emotionColor(key)} h-full transition-all`}
 style={{ width: `${val}%` }}
 title={`${emotionLabel(key)}: ${val}%`} />
 ))}
 </div>
 {/* Dominant label */}
 <span className="text-ink-muted w-12 text-right shrink-0">
 {emotionLabel(d.dominant)} {d.dominantVal}%
 </span>
 </div>
 ))}
 </div>

 {/* Legend */}
 <div className="flex gap-3 mt-3 pt-2 border-t border-border text-[9px] text-ink-subtle flex-wrap">
 {(Object.keys(EMOTION_PATTERNS) as (keyof EmotionProfile)[]).map(k => (
 <span key={k} className="flex items-center gap-1">
 <span className={`w-2 h-2 rounded-full ${emotionColor(k)}`} />
 {emotionLabel(k)}
 </span>
 ))}
 </div>

 {/* Tip */}
 {dominant.length >= 3 && (() => {
 const allDominant = dominant.map(d => d.dominant);
 const uniqueDom = new Set(allDominant);
 if (uniqueDom.size <= 2) {
 return (
 <p className="text-[10px] text-warn mt-2">
 <AlertTriangle size={12} className='mr-0.5' /> 情绪类型较单一，建议增加情绪变化以保持读者新鲜感
 </p>
 );
 }
 return (
 <p className="text-[10px] text-success mt-2">
 <CheckCircle2 size={12} className='mr-0.5 text-success' /> 情绪层次丰富，读者体验多样
 </p>
 );
 })()}
 </div>
 );
}
