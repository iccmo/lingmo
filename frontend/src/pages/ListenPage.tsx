import { useState, useEffect, useCallback } from 'react';
import { useAudio, type PlaylistItem, type Bookmark } from 'src/lib/AudioContext';
import { toast } from 'sonner';
import { api } from 'src/lib/api';
import type { NovelSummary, NovelDetail, ChapterMeta } from 'src/types';
import { RefreshCw, Volume2, Music, BookOpen, Bookmark as BookmarkIcon } from 'lucide-react';

function formatTime(sec: number): string {
 const m = Math.floor(sec / 60);
 const s = Math.floor(sec % 60);
 return `${m}:${s.toString().padStart(2, '0')}`;
}

function formatDate(ts: number): string {
 const d = new Date(ts);
 return `${d.getMonth() + 1}/${d.getDate()} ${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}`;
}

interface ResumeData {
 novelId: string;
 chapterNum: number;
 position: number;
 time: number;
}

type Tab = 'shelf' | 'bookmarks';

export function ListenPage() {
 const [novels, setNovels] = useState<NovelSummary[]>([]);
 const [expandedId, setExpandedId] = useState<string | null>(null);
 const [expandedChapters, setExpandedChapters] = useState<ChapterMeta[]>([]);
 const [loading, setLoading] = useState(true);
 const [chaptersLoading, setChaptersLoading] = useState(false);
 const [resume, setResume] = useState<ResumeData | null>(null);
 const [bookmarks, setBookmarks] = useState<Bookmark[]>([]);
 const [bookmarkNote, setBookmarkNote] = useState('');
 const [tab, setTab] = useState<Tab>('shelf');

 const {
 playing, paused, loading: audioLoading, current, progress, positionSec, speed, voice, playlist, sleepTimer, voices, autoContinue,
 playChapter, togglePause, stop, skipChapter, playRandom,
 addToPlaylist, removeFromPlaylist, clearPlaylist,
 changeVoice, changeSpeed, startSleepTimer, cancelSleepTimer,
 getResume, isListened,
 addBookmark, removeBookmark, getBookmarks,
 toggleAutoContinue,
 } = useAudio();

 // Load novels
 useEffect(() => {
 api.novels.list()
 .then(novels => {
 try {
 const starred: string[] = JSON.parse(localStorage.getItem('starred-novels') || '[]');
 novels.sort((a, b) => {
 const aStar = starred.includes(a.id) ? 0 : 1;
 const bStar = starred.includes(b.id) ? 0 : 1;
 return aStar - bStar;
 });
 } catch {}
 setNovels(novels);
 })
 .catch(() => {})
 .finally(() => setLoading(false));

 setResume(getResume());
 setBookmarks(getBookmarks());
 }, [getResume, getBookmarks]);

 // Expand novel — load chapters
 const toggleExpand = useCallback(async (id: string) => {
 if (expandedId === id) {
 setExpandedId(null);
 setExpandedChapters([]);
 } else {
 setExpandedId(id);
 setChaptersLoading(true);
 try {
 const detail: NovelDetail = await api.novels.get(id);
 setExpandedChapters(detail.chapters.filter(c => c.word_count > 0));
 } catch {
 setExpandedChapters([]);
 } finally {
 setChaptersLoading(false);
 }
 }
 }, [expandedId]);

 function handlePlayChapter(novelId: string, novelTitle: string, num: number, title: string) {
 const item: PlaylistItem = { novelId, novelTitle, chapterNum: num, chapterTitle: title };
 addToPlaylist(item);
 playChapter(item);
 }

 function handlePlayAll(novelId: string, novelTitle: string, chapters: ChapterMeta[]) {
 if (chapters.length === 0) return;
 for (const ch of chapters) {
 addToPlaylist({ novelId, novelTitle, chapterNum: ch.number, chapterTitle: ch.title });
 }
 playChapter({ novelId, novelTitle, chapterNum: chapters[0].number, chapterTitle: chapters[0].title });
 }

 function handleResumePlay() {
 if (!resume) return;
 const novel = novels.find(n => n.id === resume.novelId);
 const title = novel?.title || '未知';
 playChapter({ novelId: resume.novelId, novelTitle: title, chapterNum: resume.chapterNum, chapterTitle: '' }, resume.position);
 }

 function handleJumpBookmark(bm: Bookmark) {
 handlePlayChapter(bm.novelId, bm.novelTitle, bm.chapterNum, bm.chapterTitle);
 // Seek will happen via the playChapter with position
 setTimeout(() => {
 const item: PlaylistItem = { novelId: bm.novelId, novelTitle: bm.novelTitle, chapterNum: bm.chapterNum, chapterTitle: bm.chapterTitle };
 playChapter(item, bm.position);
 }, 500);
 }

 function handleBookmark() {
 addBookmark(bookmarkNote.trim() || undefined);
 setBookmarkNote('');
 setBookmarks(getBookmarks());
 }

 const listenedIcon = (novelId: string, num: number): string | null => {
 const s = isListened(novelId, num);
 if (s === 'done') return 'done';
 if (s === 'partial') return '⏳';
 return null;
 };

 if (loading) {
 return (
 <div className="space-y-6 animate-pulse">
 <div className="h-32 bg-card rounded-xl" />
 <div className="h-12 bg-card rounded-lg" />
 <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
 {[1, 2, 3, 4, 5, 6].map(i => <div key={i} className="h-24 bg-card rounded-lg" />)}
 </div>
 </div>
 );
 }

 return (
 <div className="space-y-6 pb-32">
 {/* Page header */}
 <div className="flex items-center justify-between">
 <div>
 <h2 className="text-lg font-semibold text-ink">🎧 听书</h2>
 <p className="text-xs text-ink-muted mt-0.5">AI 语音朗读 · 预加载连续播放</p>
 </div>
 <div className="flex items-center gap-2">
 {/* Tabs */}
 <div className="flex rounded-lg border border-border overflow-hidden text-xs">
 <button
 onClick={() => setTab('shelf')}
 className={`px-3 py-1.5 transition-colors ${tab === 'shelf' ? 'bg-accent text-white' : 'text-ink-muted hover:text-ink'}`}
 >📚 书架</button>
 <button
 onClick={() => { setTab('bookmarks'); setBookmarks(getBookmarks()); }}
 className={`px-3 py-1.5 transition-colors ${tab === 'bookmarks' ? 'bg-accent text-white' : 'text-ink-muted hover:text-ink'}`}
 >🔖 标记 {bookmarks.length > 0 ? `(${bookmarks.length})` : ''}</button>
 </div>
 <button onClick={playRandom} disabled={playlist.length === 0}
 className="text-xs px-3 py-1.5 rounded-lg border border-border hover:border-accent/30 text-ink-muted hover:text-accent transition-colors disabled:opacity-30">
 🔀 随机
 </button>
 </div>
 </div>

 {/* Continue Listening */}
 {resume && tab === 'shelf' && (
 <button
 onClick={handleResumePlay}
 className="w-full text-left p-4 rounded-xl bg-gradient-to-r from-accent-soft/30 to-card border border-accent/20 hover:border-accent/40 transition-colors"
 >
 <p className="text-[10px] text-ink-subtle mb-1 uppercase tracking-wider">继续收听</p>
 <div className="flex items-center justify-between">
 <div className="flex-1 min-w-0">
 <p className="text-sm font-medium text-ink truncate">{novels.find(n => n.id === resume.novelId)?.title || '未知作品'}</p>
 <p className="text-xs text-ink-muted">
 第{resume.chapterNum}章
 <span className="ml-2 text-ink-subtle">进度 {formatTime(resume.position)}</span>
 </p>
 </div>
 <span className="shrink-0 px-4 py-2 bg-accent text-white text-xs font-medium rounded-full">继续 ▶</span>
 </div>
 </button>
 )}

 {/* Now Playing */}
 {current && (audioLoading || playing) && tab === 'shelf' && (
 <div className="p-4 rounded-xl bg-accent-soft/20 border border-accent/10">
 <div className="flex items-center justify-between">
 <div className="flex-1 min-w-0">
 <p className="text-sm font-medium text-ink truncate">{current.novelTitle}</p>
 <p className="text-xs text-ink-muted">
 第{current.chapterNum}章 {current.chapterTitle}
 {audioLoading && <span className="ml-2 inline-flex items-center gap-1 text-accent"><span className="animate-spin">⏳</span> 生成语音中…</span>}
 </p>
 </div>
 {!audioLoading && (
 <span className="text-xs text-ink-subtle tabular-nums shrink-0 ml-3">{formatTime(positionSec)} · {progress}%</span>
 )}
 </div>
 {audioLoading ? (
 <div className="mt-2">
 <div className="h-1.5 bg-border rounded-full overflow-hidden">
 <div className="h-full bg-accent/40 rounded-full animate-[loadingBar_2s_ease-in-out_infinite]" style={{ width: '70%' }} />
 </div>
 <p className="text-[10px] text-ink-subtle text-center mt-1">首次生成约需 15 秒，后续播放秒开</p>
 </div>
 ) : (
 <>
 <div className="h-1.5 bg-border rounded-full mt-2 overflow-hidden">
 <div className="h-full bg-accent rounded-full transition-all duration-300" style={{ width: `${progress}%` }} />
 </div>

 {/* Controls */}
 <div className="flex items-center justify-center gap-3 mt-3">
 <button onClick={() => skipChapter(-1)} className="text-sm p-1 text-ink-muted hover:text-ink">⏮</button>
 <button onClick={togglePause} className="text-2xl p-1 text-accent hover:scale-110 transition-transform">
 {paused ? '▶' : '⏸'}
 </button>
 <button onClick={stop} className="text-sm p-1 text-destructive hover:text-destructive dark:hover:text-destructive">⏹</button>
 <button onClick={() => skipChapter(1)} className="text-sm p-1 text-ink-muted hover:text-ink">⏭</button>
 <button onClick={() => addBookmark()} className="text-sm p-1 text-warn hover:text-warn dark:hover:text-warn transition-colors" title="标记当前位置">
 🔖
 </button>
 </div>

 {/* Voice + Speed + Auto-continue */}
 <div className="flex items-center gap-3 mt-3">
 <select value={voice} onChange={e => changeVoice(e.target.value)}
 className="text-[10px] rounded border border-input bg-card px-2 py-1 min-w-0">
 {voices.map(v => <option key={v.id} value={v.id}>{v.name}</option>)}
 </select>
 <div className="flex items-center gap-1.5 flex-1 min-w-0">
 <span className="text-[9px] text-ink-subtle shrink-0">语速</span>
 <input type="range" min="0.5" max="2.0" step="0.05" value={speed}
 onChange={e => changeSpeed(parseFloat(e.target.value))}
 className="flex-1 h-1 accent-accent" />
 <span className="text-[10px] text-ink tabular-nums w-8 shrink-0">{speed.toFixed(2)}x</span>
 </div>
 <button onClick={toggleAutoContinue}
 className={`text-[9px] px-2 py-1 rounded whitespace-nowrap shrink-0 border transition-colors ${
 autoContinue ? 'bg-accent/10 border-accent/30 text-accent' : 'border-border text-ink-muted'
 }`}>
 {autoContinue ? <><RefreshCw size={12} className='mr-1' /> 连播</> : <><RefreshCw size={12} className='mr-1' /> 单章</>}
 </button>
 </div>

 {/* Sleep timer */}
 <div className="flex items-center gap-1 justify-center mt-2">
 <span className="text-[9px] text-ink-muted">⏰</span>
 {[15, 30, 45, 60].map(m => (
 <button key={m} onClick={() => sleepTimer === m ? cancelSleepTimer() : startSleepTimer(m)}
 className={`text-[9px] px-1.5 py-0.5 rounded ${sleepTimer === m ? 'bg-accent text-white' : 'text-ink-muted hover:text-ink'}`}>
 {m}min
 </button>
 ))}
 {sleepTimer > 0 && <span className="text-[9px] text-warn">{sleepTimer}分钟后暂停</span>}
 </div>
 </>
 )}
 </div>
 )}

 {/* ── Shelf tab ── */}
 {tab === 'shelf' && (
 <>
 {novels.length > 0 ? (
 <div>
 <div className="flex items-center justify-between mb-3">
 <h3 className="text-sm font-semibold text-ink">我的书架</h3>
 <span className="text-[10px] text-ink-subtle">{novels.length} 部作品</span>
 </div>
 <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
 {novels.map(novel => {
 const isExpanded = expandedId === novel.id;
 const isCurrentlyPlaying = current?.novelId === novel.id && playing;
 return (
 <div key={novel.id}
 className={`rounded-xl border transition-colors ${
 isExpanded ? 'border-accent/30 bg-accent-soft/5' : 'border-border bg-card hover:border-accent/20'
 }`}>
 <button className="w-full text-left p-3" onClick={() => toggleExpand(novel.id)}>
 <div className="flex items-start justify-between">
 <div className="flex-1 min-w-0">
 <div className="flex items-center gap-1.5">
 {isCurrentlyPlaying && <span className="text-[10px] animate-pulse">🔊</span>}
 <p className="text-sm font-medium text-ink truncate">{novel.title}</p>
 </div>
 <p className="text-[10px] text-ink-muted mt-0.5">
 {novel.genre} · {novel.total_chapters}章 · {(novel.total_words || 0).toLocaleString()}字
 </p>
 </div>
 <span className="text-[10px] text-ink-subtle shrink-0 ml-2">{isExpanded ? '▴' : '▾'}</span>
 </div>
 </button>

 {isExpanded && (
 <div className="border-t border-border px-3 py-2 space-y-1">
 {chaptersLoading ? (
 <div className="space-y-1 py-2">
 {[1, 2, 3].map(i => <div key={i} className="h-6 bg-paper rounded animate-pulse" />)}
 </div>
 ) : expandedChapters.length === 0 ? (
 <p className="text-[10px] text-ink-subtle text-center py-2">暂无已生成章节</p>
 ) : (
 <>
 <button
 onClick={(e) => { e.stopPropagation(); handlePlayAll(novel.id, novel.title, expandedChapters); }}
 className="w-full text-[10px] text-accent hover:text-accent/80 font-medium py-1"
 >
 ▶ 播放全部 ({expandedChapters.length}章)
 </button>
 <div className="max-h-[200px] overflow-y-auto space-y-0.5">
 {expandedChapters.map(ch => {
 const isCurrent = current?.novelId === novel.id && current?.chapterNum === ch.number;
 const icon = listenedIcon(novel.id, ch.number);
 return (
 <button key={ch.number}
 onClick={(e) => { e.stopPropagation(); handlePlayChapter(novel.id, novel.title, ch.number, ch.title); }}
 className={`flex items-center gap-2 w-full px-2 py-1 rounded text-[10px] text-left transition-colors ${
 isCurrent ? 'bg-accent-soft/30 text-accent' : 'hover:bg-paper text-ink'
 }`}
 >
 <span className="shrink-0">{isCurrent && playing ? <Volume2 size={14} /> : <Music size={14} />}</span>
 <span className="flex-1 truncate">第{ch.number}章 {ch.title}</span>
 {icon && <span className="text-[9px] shrink-0">{icon}</span>}
 <span className="text-ink-subtle shrink-0">{(ch.word_count || 0).toLocaleString()}字</span>
 </button>
 );
 })}
 </div>
 </>
 )}
 </div>
 )}
 </div>
 );
 })}
 </div>
 </div>
 ) : (
 <div className="text-center py-16">
 <BookOpen size={48} className="text-accent mb-4" />
 <p className="text-sm text-ink font-medium">还没有小说</p>
 <p className="text-xs text-ink-muted mt-1">创建一本小说，生成章节后就能在这里听书</p>
 </div>
 )}

 {/* Playlist */}
 {playlist.length > 0 && (
 <div className="border-t border-border pt-4">
 <div className="flex items-center justify-between mb-2">
 <h3 className="text-sm font-semibold text-ink">播放列表 ({playlist.length})</h3>
 <button onClick={clearPlaylist} className="text-[10px] text-destructive hover:text-destructive dark:hover:text-destructive">清空</button>
 </div>
 <div className="space-y-0.5 max-h-[300px] overflow-y-auto">
 {playlist.map((item, i) => {
 const isCurrent = current?.novelId === item.novelId && current?.chapterNum === item.chapterNum;
 return (
 <div key={`${item.novelId}-${item.chapterNum}`}
 onClick={() => playChapter(item)}
 className={`flex items-center gap-2 px-3 py-2 rounded text-xs cursor-pointer transition-colors ${
 isCurrent ? 'bg-accent-soft/30 text-accent' : 'hover:bg-paper text-ink'
 }`}
 >
 <span className="shrink-0">{isCurrent && playing ? <Volume2 size={14} /> : <Music size={14} />}</span>
 <span className="flex-1 truncate">{item.novelTitle} · 第{item.chapterNum}章</span>
 <button onClick={e => { e.stopPropagation(); removeFromPlaylist(i); }}
 className="text-ink-subtle hover:text-destructive shrink-0">×</button>
 </div>
 );
 })}
 </div>
 </div>
 )}
 </>
 )}

 {/* ── Bookmarks tab ── */}
 {tab === 'bookmarks' && (
 <div className="space-y-4">
 {/* Quick bookmark input */}
 {current && playing && (
 <div className="p-3 rounded-xl bg-card border border-border flex items-center gap-2">
 <input
 type="text"
 value={bookmarkNote}
 onChange={e => setBookmarkNote(e.target.value)}
 onKeyDown={e => { if (e.key === 'Enter') handleBookmark(); }}
 placeholder="标记当前时刻：这里写得好..."
 className="flex-1 text-xs rounded border border-input bg-paper px-2 py-1.5"
 />
 <button onClick={handleBookmark}
 className="text-xs px-3 py-1.5 bg-accent text-white rounded-lg shrink-0 whitespace-nowrap">
 <BookmarkIcon size={12} className='mr-1' /> 标记
 </button>
 </div>
 )}

 {bookmarks.length === 0 ? (
 <div className="text-center py-16">
 <BookmarkIcon size={40} className="text-accent mb-4" />
 <p className="text-sm text-ink font-medium">还没有标记</p>
 <p className="text-xs text-ink-muted mt-1">播放中点标记按钮，标记精彩片段</p>
 </div>
 ) : (
 <div className="space-y-2">
 <div className="flex items-center justify-between">
 <h3 className="text-sm font-semibold text-ink">我的标记 ({bookmarks.length})</h3>
 <button onClick={() => { localStorage.removeItem('audio-bookmarks'); setBookmarks([]); toast.success('已清空'); }}
 className="text-[10px] text-destructive hover:text-destructive dark:hover:text-destructive">清空</button>
 </div>
 {bookmarks.map(bm => (
 <div key={bm.id} className="p-3 rounded-lg bg-card border border-border hover:border-accent/20 transition-colors">
 <div className="flex items-start justify-between">
 <button className="flex-1 text-left min-w-0" onClick={() => handleJumpBookmark(bm)}>
 <p className="text-xs font-medium text-ink truncate">{bm.novelTitle}</p>
 <p className="text-[10px] text-ink-muted mt-0.5">
 第{bm.chapterNum}章 · {formatTime(bm.position)}
 {bm.note && <span className="ml-2 text-accent">「{bm.note}」</span>}
 </p>
 </button>
 <div className="flex items-center gap-1 shrink-0 ml-2">
 <span className="text-[9px] text-ink-subtle">{formatDate(bm.createdAt)}</span>
 <button onClick={() => { removeBookmark(bm.id); setBookmarks(getBookmarks()); }}
 className="text-[10px] text-ink-subtle hover:text-destructive">×</button>
 </div>
 </div>
 </div>
 ))}
 </div>
 )}
 </div>
 )}
 </div>
 );
}
