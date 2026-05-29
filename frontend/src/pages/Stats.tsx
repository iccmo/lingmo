import { useEffect, useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, CardContent } from 'src/components/ui/card';
import { api } from 'src/lib/api';
import { toast } from 'sonner';
import type { NovelSummary } from 'src/types';
import { BookOpen, FileText, Star, Trophy, Zap } from 'lucide-react';

interface NovelStats {
 id: string; title: string; genre: string;
 chapters: number; words: number; avgQuality: number;
 firstGen?: string; lastGen?: string; streak: number;
 qualityTrend: 'rising' | 'falling' | 'stable';
}

export function Stats() {
 const navigate = useNavigate();
 const [novels, setNovels] = useState<NovelSummary[]>([]);
 const [loading, setLoading] = useState(true);

 useEffect(() => {
 api.novels.list().then(setNovels).catch(() => toast.error('加载失败')).finally(() => setLoading(false));
 }, []);

 const stats: NovelStats[] = useMemo(() => novels.filter(n => n.total_chapters > 0).map(n => {
 // Quality trend: fetch from localStorage or use heuristic
 let avgQ = 0.65; let trend: 'rising' | 'falling' | 'stable' = 'stable';
 try {
 const saved = localStorage.getItem(`quality-trend-${n.id}`);
 if (saved) { const d = JSON.parse(saved); avgQ = d.avg || 0.65; trend = d.trend || 'stable'; }
 } catch {}
 let streak = 0;
 try {
 const log = JSON.parse(localStorage.getItem('writing-daily-log') || '{}');
 const dates = Object.keys(log).sort().reverse();
 const now = new Date();
 for (let i = 0; i < dates.length; i++) {
 const d = new Date(dates[i]);
 const expected = new Date(now); expected.setDate(expected.getDate() - i);
 if (d.toISOString().slice(0,10) === expected.toISOString().slice(0,10) && log[dates[i]] > 0) streak++;
 else break;
 }
 } catch {}
 return {
 id: n.id, title: n.title, genre: n.genre,
 chapters: n.total_chapters, words: n.total_words || 0,
 avgQuality: avgQ, firstGen: '', lastGen: n.latest_chapter?.generated_at,
 streak, qualityTrend: trend,
 };
 }), [novels]);

 const totalWords = stats.reduce((s, n) => s + n.words, 0);
 const totalChapters = stats.reduce((s, n) => s + n.chapters, 0);
 const avgQualityAll = stats.length > 0 ? stats.reduce((s, n) => s + n.avgQuality, 0) / stats.length : 0;
 const bestNovel = stats.reduce((best, n) => n.avgQuality > (best?.avgQuality || 0) ? n : best, stats[0]);
 const mostProductive = stats.reduce((best, n) => n.words > (best?.words || 0) ? n : best, stats[0]);

 if (loading) return <div className="p-8 space-y-4"><div className="skeleton h-8 w-48" /><div className="skeleton h-40 rounded-lg" /></div>;

 return (
 <div className="page-enter">
 <h1 className="font-heading text-[28px] font-semibold text-ink mb-1">写作统计</h1>
 <p className="text-sm text-ink-muted mb-6">数据驱动的自我认知</p>

 {/* Global stats */}
 <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
 {[
 { v: novels.length, l: '总小说', Icon: BookOpen },
 { v: totalChapters, l: '总章节', Icon: FileText },
 { v: (totalWords/10000).toFixed(1) + '万', l: '总字数', Icon: FileText },
 { v: avgQualityAll.toFixed(2), l: '均质量', Icon: Star },
 ].map(s => (
 <Card key={s.l} className="border-border"><CardContent className="p-4 text-center">
 <s.Icon size={24} className="text-accent mb-1.5" />
 <div className="font-heading text-xl font-bold text-ink">{s.v}</div>
 <div className="text-[10px] text-ink-muted mt-0.5">{s.l}</div>
 </CardContent></Card>
 ))}
 </div>

 {/* Highlights */}
 <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-6">
 {bestNovel && (
 <Card className="border-success/20 bg-success-soft/30 ">
 <CardContent className="p-4">
 <p className="text-[10px] text-success font-medium uppercase tracking-wide"><Trophy size={12} className="text-success" /> 质量最高</p>
 <p className="text-sm font-semibold text-ink mt-1">{bestNovel.title}</p>
 <p className="text-xs text-ink-muted">{bestNovel.genre} · {bestNovel.chapters}章 · 均质{bestNovel.avgQuality.toFixed(2)}</p>
 </CardContent></Card>
 )}
 {mostProductive && (
 <Card className="border-accent/30 bg-accent-soft/10">
 <CardContent className="p-4">
 <p className="text-[10px] text-accent font-medium uppercase tracking-wide"><Zap size={12} className="text-accent" /> 字数最多</p>
 <p className="text-sm font-semibold text-ink mt-1">{mostProductive.title}</p>
 <p className="text-xs text-ink-muted">{mostProductive.genre} · {(mostProductive.words/10000).toFixed(1)}万字 · {mostProductive.chapters}章</p>
 </CardContent></Card>
 )}
 </div>

 {/* Per-novel stats */}
 {stats.length > 0 && (
 <div>
 <h2 className="font-heading text-lg font-semibold text-ink mb-3">各小说统计</h2>
 <div className="space-y-2">
 {stats.map(s => (
 <Card key={s.id} className="border-border hover:border-accent/20 cursor-pointer transition-colors"
 onClick={() => navigate(`/novels/${s.id}`)}>
 <CardContent className="p-4">
 <div className="flex items-center justify-between mb-2">
 <div className="flex items-center gap-2">
 <span className="font-heading text-sm font-semibold text-ink">{s.title}</span>
 <span className="text-[10px] text-ink-subtle">{s.genre}</span>
 </div>
 <span className={`text-[10px] font-medium ${
 s.qualityTrend === 'rising' ? 'text-success' : s.qualityTrend === 'falling' ? 'text-warn' : 'text-ink-subtle'
 }`}>
 {s.qualityTrend === 'rising' ? '<TrendingUp size={12} /> 上升' : s.qualityTrend === 'falling' ? '<TrendingDown size={12} /> 下降' : '<Minus size={12} /> 平稳'}
 </span>
 </div>

 {/* Mini bars */}
 <div className="grid grid-cols-4 gap-3 text-[10px]">
 <div>
 <span className="text-ink-subtle">章节</span>
 <div className="text-ink font-semibold">{s.chapters}</div>
 </div>
 <div>
 <span className="text-ink-subtle">字数</span>
 <div className="text-ink font-semibold">{(s.words/10000).toFixed(1)}万</div>
 </div>
 <div>
 <span className="text-ink-subtle">均质</span>
 <div className={`font-semibold ${s.avgQuality >= 0.7 ? 'text-success' : s.avgQuality >= 0.55 ? 'text-warn' : 'text-destructive'}`}>
 {s.avgQuality.toFixed(2)}
 </div>
 </div>
 <div>
 <span className="text-ink-subtle">连续天</span>
 <div className="text-ink font-semibold">{s.streak}</div>
 </div>
 </div>

 {/* Quality bar */}
 <div className="mt-2 h-1 bg-border rounded-full overflow-hidden">
 <div className={`h-full rounded-full ${s.avgQuality >= 0.7 ? 'bg-emerald-400' : s.avgQuality >= 0.55 ? 'bg-amber-400' : 'bg-red-400'}`}
 style={{ width: `${s.avgQuality * 100}%` }} />
 </div>
 </CardContent>
 </Card>
 ))}
 </div>
 </div>
 )}
 </div>
 );
}
