import { useState, useEffect, useCallback } from 'react';
import { toast } from 'sonner';

interface Shot {
 shot_id: string;
 shot_type: string;
 camera_angle: string;
 camera_move: string;
 subject: string;
 background: string;
 lighting: string;
 emotion: string;
 dialogue: string;
 subtext: string;
 duration_sec: number;
 transition: string;
}

interface StoryboardData {
 title: string;
 overall_mood: string;
 pacing: string;
 color_grade: string;
 music_theme: string;
 shots: Shot[];
 total_duration_sec?: number;
}

interface Props {
 novelId: string;
 chapters: { number: number; title: string }[];
}

const SHOT_TYPE_LABELS: Record<string, string> = {
 'close-up': '特写',
 'medium': '中景',
 'wide': '全景',
 'extreme-wide': '远景',
};

const SHOT_TYPE_COLORS: Record<string, string> = {
 'close-up': 'bg-rose-500/10 text-rose-600 border-rose-500/20',
 'medium': 'bg-info-soft0/10 text-info border-blue-500/20',
 'wide': 'bg-success-soft0/10 text-success border-emerald-500/20',
 'extreme-wide': 'bg-purple-500/10 text-purple-600 border-purple-500/20',
};

export function StoryboardPanel({ novelId, chapters }: Props) {
 const [chapterNum, setChapterNum] = useState(chapters.length > 0 ? chapters[0].number : 1);
 const [storyboard, setStoryboard] = useState<StoryboardData | null>(null);
 const [loading, setLoading] = useState(false);
 const [generating, setGenerating] = useState(false);

 const fetchStoryboard = useCallback(async () => {
 setLoading(true);
 try {
 const res = await fetch(`/api/novels/${novelId}/chapters/${chapterNum}/storyboard`);
 if (res.ok) {
 setStoryboard(await res.json());
 } else {
 setStoryboard(null);
 }
 } catch {
 setStoryboard(null);
 } finally {
 setLoading(false);
 }
 }, [novelId, chapterNum]);

 useEffect(() => { fetchStoryboard(); }, [fetchStoryboard]);

 const handleGenerate = async () => {
 setGenerating(true);
 try {
 const res = await fetch(`/api/novels/${novelId}/chapters/${chapterNum}/storyboard/generate`, { method: 'POST' });
 if (res.ok) {
 toast.success('分镜生成已启动');
 const poll = setInterval(async () => {
 const sRes = await fetch(`/api/novels/${novelId}/generate/status`);
 if (sRes.ok) {
 const s = await sRes.json();
 if (s.status === 'idle' || s.status === 'error') {
 clearInterval(poll);
 setGenerating(false);
 if (s.status === 'idle') {
 toast.success(s.message || '分镜完成');
 fetchStoryboard();
 } else {
 toast.error(s.message || '生成失败');
 }
 }
 }
 }, 2000);
 }
 } catch {
 setGenerating(false);
 toast.error('请求失败');
 }
 };

 return (
 <div className="space-y-4">
 {/* Controls */}
 <div className="flex items-center gap-3 flex-wrap">
 <select
 value={chapterNum}
 onChange={e => setChapterNum(Number(e.target.value))}
 className="px-2 py-1.5 text-xs border border-border rounded-md bg-card text-ink"
 >
 {chapters.map(ch => (
 <option key={ch.number} value={ch.number}>
 第{ch.number}章 {ch.title}
 </option>
 ))}
 </select>
 <button
 onClick={handleGenerate}
 disabled={generating}
 className="px-3 py-1.5 text-xs font-medium bg-accent text-white rounded-md hover:bg-accent/80 disabled:opacity-50 transition flex items-center gap-1.5"
 >
 {generating && <span className="w-3 h-3 border-2 border-white/30 border-t-white rounded-full animate-spin" />}
 {generating ? '生成中...' : '生成分镜'}
 </button>
 {storyboard && storyboard.shots.length > 0 && (
 <button
 onClick={() => {
 const url = `/api/novels/${novelId}/chapters/${chapterNum}/storyboard/export`;
 const a = document.createElement('a');
 a.href = url;
 a.download = `storyboard_ch${String(chapterNum).padStart(3, '0')}.zip`;
 document.body.appendChild(a);
 a.click();
 document.body.removeChild(a);
 toast.success('分镜导出中...');
 }}
 className="px-3 py-1.5 text-xs font-medium border border-border rounded-md text-ink hover:bg-card transition flex items-center gap-1.5"
 >
 📦 导出分镜
 </button>
 )}
 </div>

 {loading && (
 <div className="space-y-2">
 {[1, 2, 3].map(i => (
 <div key={i} className="border border-border rounded-lg p-3 bg-card">
 <div className="flex items-start gap-3">
 <div className="flex flex-col items-center gap-1 shrink-0">
 <div className="skeleton h-4 w-8 rounded" />
 <div className="skeleton h-5 w-10 rounded" />
 </div>
 <div className="flex-1 space-y-1.5">
 <div className="skeleton h-4 w-3/4 rounded" />
 <div className="skeleton h-3 w-1/2 rounded" />
 </div>
 <div className="skeleton h-3 w-8 rounded" />
 </div>
 </div>
 ))}
 </div>
 )}

 {!loading && !storyboard && (
 <div className="text-center py-10">
 <div className="text-3xl mb-3">🎞</div>
 <p className="text-sm text-ink-muted">暂无分镜数据</p>
 <p className="text-xs text-ink-subtle mt-1">点击"生成分镜"为本章创建镜头脚本</p>
 </div>
 )}

 {/* Storyboard metadata */}
 {storyboard && (
 <>
 <div className="flex flex-wrap gap-2 text-xs">
 {storyboard.title && (
 <span className="px-2 py-1 bg-card border border-border rounded text-ink font-medium">
 {storyboard.title}
 </span>
 )}
 {storyboard.overall_mood && (
 <span className="px-2 py-1 bg-warn-soft0/10 border border-amber-500/20 rounded text-amber-700 dark:text-amber-300">
 {storyboard.overall_mood}
 </span>
 )}
 {storyboard.pacing && (
 <span className="px-2 py-1 bg-info-soft0/10 border border-sky-500/20 rounded text-sky-700 dark:text-sky-300">
 {storyboard.pacing}
 </span>
 )}
 {storyboard.music_theme && (
 <span className="px-2 py-1 bg-violet-500/10 border border-violet-500/20 rounded text-violet-700">
 {storyboard.music_theme}
 </span>
 )}
 </div>

 {/* Shots timeline */}
 <div className="space-y-2">
 {storyboard.shots.map((shot, _i) => (
 <div
 key={shot.shot_id}
 className="border border-border rounded-lg p-3 bg-card hover:shadow-sm transition"
 >
 <div className="flex items-start gap-3">
 {/* Shot number + type badge */}
 <div className="flex flex-col items-center gap-1 shrink-0">
 <span className="text-xs font-mono text-ink-muted">{shot.shot_id}</span>
 <span className={`px-1.5 py-0.5 text-[10px] font-medium rounded border ${SHOT_TYPE_COLORS[shot.shot_type] || 'bg-card'}`}>
 {SHOT_TYPE_LABELS[shot.shot_type] || shot.shot_type}
 </span>
 </div>

 {/* Content */}
 <div className="flex-1 min-w-0">
 <p className="text-sm text-ink font-medium">{shot.subject}</p>
 {shot.background && (
 <p className="text-xs text-ink-muted mt-0.5">{shot.background}</p>
 )}
 {shot.dialogue && (
 <p className="text-xs text-accent mt-1 italic">"{shot.dialogue}"</p>
 )}
 {shot.subtext && (
 <p className="text-[10px] text-ink-muted mt-0.5">潜台词：{shot.subtext}</p>
 )}
 </div>

 {/* Meta */}
 <div className="flex flex-col items-end gap-1 shrink-0 text-[10px] text-ink-muted">
 <span>{shot.duration_sec}s</span>
 {shot.emotion && <span>{shot.emotion}</span>}
 <span>{shot.camera_move}</span>
 </div>
 </div>
 </div>
 ))}
 </div>
 </>
 )}
 </div>
 );
}
