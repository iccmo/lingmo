import { useState, useEffect, useRef, useCallback } from 'react';
import { useAudio } from 'src/lib/AudioContext';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { BarChart3, BookOpen, ClipboardList, Headphones, Music, Palette, RefreshCw } from 'lucide-react';

const MODE_LABELS: Record<string, string> = { sequential: '🔁', shuffle: '🔀', 'repeat-one': '🔂' };

export function MiniPlayer() {
 const {
 playing, paused, loading, current, progress, positionSec, speed, voice, volume, playlist,
 togglePause, skipChapter, addBookmark, autoContinue, stop,
 changeVoice, changeSpeed, seekTo, setVolume, skip15s, cycleSkip, skipSeconds, rewind30s, undoSkip,
 startSleepTimer, cancelSleepTimer, sleepTimer, sleepRemaining, sleepAtChapterEnd, setSleepAtChapterEnd, voices,
 playMode: pm, cyclePlayMode,
 playChapter, removeFromPlaylist, getHistory,
 showRemaining, toggleTimeDisplay,
 ambient, setAmbient, ambientVolume, setAmbientVolume,
 music, setMusic, musicVolume, setMusicVolume,
 sleepStory, toggleSleepStory,
 speedTrain, toggleSpeedTrain, speedTrainLevel,
 achievements, radioMode, toggleRadioMode,
 dramaticMode, toggleDramaticMode,
 eqPreset, cycleEQ,
 } = useAudio();
 const navigate = useNavigate();

 const [expanded, setExpanded] = useState(false);
 const [collapsed, setCollapsed] = useState(false);
 const [showPlaylist, setShowPlaylist] = useState(false);
 const [showHistory, setShowHistory] = useState(false);
 const [showCreative, setShowCreative] = useState(false);
 const [customTimer, setCustomTimer] = useState('');
 const [vizTheme, setVizTheme] = useState(0);
 const [focusMode, setFocusMode] = useState(false);
 const idleRef = useRef(Date.now());
 const idleCheckRef = useRef<ReturnType<typeof setInterval>>(undefined);

 // Swipe gesture tracking
 const touchStartX = useRef(0);
 const touchStartY = useRef(0);

 // Sound profiles
 const [profiles, setProfiles] = useState<Array<{name: string; voice: string; speed: number; ambient: string | null; music: string | null}>>(() => {
 try { return JSON.parse(localStorage.getItem('audio-profiles') || '[]'); } catch { return []; }
 });
 const [pos, setPos] = useState(() => {
 try {
 const saved = JSON.parse(localStorage.getItem('audio-player-pos') || 'null');
 if (saved && saved.x >= 0 && saved.y >= 0) return saved;
 } catch {}
 return { x: Math.max(0, window.innerWidth - 400), y: Math.max(0, window.innerHeight - 520) };
 });
 const dragRef = useRef({ dragging: false, startX: 0, startY: 0, origX: 0, origY: 0 });
 const [isMobile, setIsMobile] = useState(() => window.innerWidth < 640);

 useEffect(() => {
 const onResize = () => setIsMobile(window.innerWidth < 640);
 window.addEventListener('resize', onResize);
 return () => window.removeEventListener('resize', onResize);
 }, []);

 const [visible, setVisible] = useState(true);
 const seekBarRef = useRef<HTMLDivElement>(null);
 const [duration, setDuration] = useState(0);

 const onDragStart = useCallback((e: React.MouseEvent | React.TouchEvent) => {
 e.preventDefault();
 const clientX = 'touches' in e ? (e as React.TouchEvent).touches[0].clientX : (e as React.MouseEvent).clientX;
 const clientY = 'touches' in e ? (e as React.TouchEvent).touches[0].clientY : (e as React.MouseEvent).clientY;
 dragRef.current = { dragging: true, startX: clientX, startY: clientY, origX: pos.x, origY: pos.y };
 }, [pos]);

 useEffect(() => {
 const move = (e: MouseEvent | TouchEvent) => {
 if (!dragRef.current.dragging) return;
 const clientX = 'touches' in e ? (e as TouchEvent).touches[0].clientX : (e as MouseEvent).clientX;
 const clientY = 'touches' in e ? (e as TouchEvent).touches[0].clientY : (e as MouseEvent).clientY;
 setPos({
 x: Math.max(0, Math.min(window.innerWidth - 380, dragRef.current.origX + (clientX - dragRef.current.startX))),
 y: Math.max(0, Math.min(window.innerHeight - 80, dragRef.current.origY + (clientY - dragRef.current.startY))),
 });
 };
 const up = () => {
 dragRef.current.dragging = false;
 localStorage.setItem('audio-player-pos', JSON.stringify(pos));
 };
 window.addEventListener('mousemove', move);
 window.addEventListener('mouseup', up);
 window.addEventListener('touchmove', move, { passive: false });
 window.addEventListener('touchend', up);
 return () => {
 window.removeEventListener('mousemove', move);
 window.removeEventListener('mouseup', up);
 window.removeEventListener('touchmove', move);
 window.removeEventListener('touchend', up);
 };
 }, [pos]);

 useEffect(() => {
 if (progress > 0 && positionSec > 0) setDuration(Math.round(positionSec / (progress / 100)));
 }, [positionSec, progress]);

 // Idle detection: track last user interaction
 useEffect(() => {
 const update = () => { idleRef.current = Date.now(); };
 window.addEventListener('mousemove', update);
 window.addEventListener('keydown', update);
 window.addEventListener('click', update);
 window.addEventListener('touchstart', update);
 return () => {
 window.removeEventListener('mousemove', update);
 window.removeEventListener('keydown', update);
 window.removeEventListener('click', update);
 window.removeEventListener('touchstart', update);
 };
 }, []);

 // Auto-pause after 30min inactivity at night (22:00-06:00)
 useEffect(() => {
 if (!playing || paused) return;
 idleCheckRef.current = setInterval(() => {
 const hour = new Date().getHours();
 const isNight = hour >= 22 || hour < 6;
 const idleMin = (Date.now() - idleRef.current) / 60000;
 if (isNight && idleMin > 30 && !paused) {
 togglePause();
 toast.info('🌙 检测到你可能睡着了，已自动暂停');
 }
 }, 60000);
 return () => { if (idleCheckRef.current) clearInterval(idleCheckRef.current); };
 }, [playing, paused]);

 function fmtTime(sec: number): string {
 if (sec <= 0 || !isFinite(sec)) return '--:--';
 const m = Math.floor(sec / 60); const s = Math.floor(sec % 60);
 return `${m}:${s.toString().padStart(2, '0')}`;
 }
 function fmtCountdown(sec: number): string {
 if (sec <= 0) return '';
 const m = Math.floor(sec / 60); const s = sec % 60;
 return `${m}:${s.toString().padStart(2, '0')}`;
 }
 function handleSeek(e: React.MouseEvent<HTMLDivElement>) {
 if (loading || !seekBarRef.current) return;
 const rect = seekBarRef.current.getBoundingClientRect();
 seekTo(Math.max(0, Math.min(100, Math.round(((e.clientX - rect.left) / rect.width) * 100))));
 }
 function handleCustomTimer(e: React.FormEvent) {
 e.preventDefault();
 const mins = parseInt(customTimer);
 if (mins > 0 && mins <= 180) { startSleepTimer(mins); setCustomTimer(''); }
 }

 // Swipe: left=next, right=prev
 function onTouchStart(e: React.TouchEvent) {
 touchStartX.current = e.touches[0].clientX;
 touchStartY.current = e.touches[0].clientY;
 }
 function onTouchEnd(e: React.TouchEvent) {
 const dx = e.changedTouches[0].clientX - touchStartX.current;
 const dy = e.changedTouches[0].clientY - touchStartY.current;
 if (Math.abs(dx) > Math.abs(dy) && Math.abs(dx) > 60) {
 if (dx > 0) skipChapter(-1);
 else skipChapter(1);
 }
 }

 // Voice preview
 function previewVoice(vId: string) {
 const audio = new Audio(`/api/novels/1998-love/chapters/1/tts?voice=${vId}&rate=%2B0%25`);
 audio.volume = 0.5;
 audio.play();
 setTimeout(() => { audio.pause(); audio.src = ''; }, 3000);
 toast.info('试听 3 秒…');
 }

 // Save sound profile
 function saveProfile() {
 const name = prompt('输入预设名称：');
 if (!name) return;
 const profile = { name, voice, speed, ambient, music };
 const updated = [...profiles.filter(p => p.name !== name), profile].slice(0, 10);
 setProfiles(updated);
 localStorage.setItem('audio-profiles', JSON.stringify(updated));
 toast.success(`已保存预设「${name}」`);
 }

 function loadProfile(p: typeof profiles[0]) {
 changeVoice(p.voice);
 changeSpeed(p.speed);
 setAmbient(p.ambient);
 setMusic(p.music);
 toast.info(`已加载预设「${p.name}」`);
 }


 // Reopen FAB — always show if closed, regardless of current
 if (!visible) {
 return (
 <button onClick={() => setVisible(true)}
 className="fixed z-50 bottom-6 right-6 w-10 h-10 rounded-full bg-accent text-white shadow-lg flex items-center justify-center text-lg hover:bg-accent-hover hover:scale-105 transition-all">
 <Headphones size={12} className="inline" />
 </button>
 );
 }

 // Need a current track for anything else
 if (!current) return null;

 // Collapsed pill
 if (collapsed && visible) {
 return (
 <div className="fixed z-50 bg-card border border-border rounded-full shadow-xl px-3 py-1.5 flex items-center gap-2 text-xs cursor-move max-sm:left-2 max-sm:right-2"
 style={{ left: isMobile ? undefined : pos.x, top: pos.y, userSelect: 'none' }}
 onMouseDown={onDragStart} onTouchStart={onDragStart} onDoubleClick={() => setCollapsed(false)}>
 <span>{loading ? '⏳' : paused ? '⏸' : ''}</span>
 <span className="text-ink truncate max-w-[120px]">{current.novelTitle} · {current.chapterNum}</span>
 {!loading && <><div className="h-0.5 w-10 bg-border rounded-full overflow-hidden"><div className="h-full bg-accent" style={{ width: `${progress}%` }} /></div>
 <button onClick={(e) => { e.stopPropagation(); togglePause(); }} className="text-accent shrink-0">{paused ? '▶' : '⏸'}</button></>}
 <button onClick={(e) => { e.stopPropagation(); setVisible(false); }} className="text-[9px] text-ink-subtle hover:text-destructive">✕</button>
 </div>
 );
 }

 const unlockedCount = achievements.filter(a => a.unlocked).length;

 return (
 <div className="fixed z-50 bg-card border border-border rounded-xl shadow-2xl w-[360px] max-md:w-[320px] max-sm:w-[calc(100vw-16px)] max-sm:left-2 max-sm:right-2 animate-[fadeSlideIn_0.2s_ease-out]"
 style={{ left: isMobile ? undefined : pos.x, top: pos.y, userSelect: 'none' }}
 onTouchStart={onTouchStart} onTouchEnd={onTouchEnd}>
 {/* Title bar */}
 <div className="flex items-center justify-between px-3 py-2 border-b border-border cursor-move"
 onMouseDown={onDragStart} onTouchStart={onDragStart}>
 <div className="flex items-center gap-1.5 min-w-0 flex-1">
 <span className="text-xs shrink-0">{loading ? '⏳' : playing && !paused ? '' : paused ? '⏸' : ''}</span>
 <div className="min-w-0">
 <div className="text-[11px] font-medium text-ink truncate">
 {radioMode && '📻 '}{current.novelTitle}
 </div>
 <div className="text-[9px] text-ink-muted truncate">第{current.chapterNum}章 {current.chapterTitle || ''}</div>
 </div>
 </div>
 <div className="flex items-center gap-0.5 shrink-0 ml-1">
 {radioMode && <span className="text-[9px] text-destructive dark:text-red-300 animate-pulse">📻</span>}
 {autoContinue && !radioMode && <span className="text-[8px] text-accent"><RefreshCw size={12} className="inline" /></span>}
 <button onClick={() => setCollapsed(true)} className="text-[10px] text-ink-muted hover:text-ink px-1" title="收起">—</button>
 <button onClick={() => setExpanded(!expanded)} className="text-[10px] text-ink-muted hover:text-ink px-1">{expanded ? '▾' : '▸'}</button>
 <button onClick={() => { stop(); setVisible(false); }} className="text-[10px] text-ink-muted hover:text-destructive px-1">✕</button>
 </div>
 </div>

 {/* Seek bar */}
 {!loading ? (
 <div ref={seekBarRef} className="h-5 mx-3 mt-2 rounded-full bg-border/30 cursor-pointer relative group" onClick={handleSeek}>
 <div className="absolute inset-y-0 left-0 bg-accent/20 rounded-full" style={{ width: `${progress}%` }} />
 <div className="absolute top-1/2 -translate-y-1/2 w-3 h-3 bg-accent rounded-full shadow-md opacity-0 group-hover:opacity-100 transition-opacity"
 style={{ left: `calc(${progress}% - 6px)` }} />
 </div>
 ) : (
 <div className="px-3 pt-2 space-y-1.5">
 <div className="h-1.5 bg-border rounded-full overflow-hidden">
 <div className="h-full bg-accent/40 rounded-full animate-[loadingBar_2s_ease-in-out_infinite]" style={{ width: '70%' }} />
 </div>
 <p className="text-[10px] text-ink-subtle text-center">AI 正在朗读… 首次约 15 秒</p>
 </div>
 )}
 {/* Focus mode: minimal view */}
 {focusMode && !loading && (
 <div className="px-3 py-2 text-center">
 <p className="text-[10px] text-ink-subtle">🧘 专注模式 · 点击暂停键退出</p>
 </div>
 )}

 {/* Spectrum visualizer */}
 {!loading && playing && !paused && !focusMode && (
 <button onClick={() => setVizTheme((vizTheme + 1) % 3)}
 className="block w-full mx-0 mt-1 cursor-pointer" title="点击切换可视化主题">
 {vizTheme === 0 && (
 <div className="flex items-end justify-center gap-[1.5px] h-4 mx-3">
 {Array.from({ length: 24 }).map((_, i) => {
 const h = 3 + Math.abs(Math.sin(i * 0.4 + positionSec * 2 + i * 1.3)) * 10
 + Math.abs(Math.cos(i * 0.7 + positionSec * 3.5)) * 4;
 return <div key={i} className="w-[2px] bg-accent/40 rounded-full transition-all duration-200"
 style={{ height: `${h}px`, opacity: 0.3 + (h / 16) * 0.7 }} />;
 })}
 </div>
 )}
 {vizTheme === 1 && (
 <svg className="w-full h-4 mx-3" viewBox="0 0 320 16" preserveAspectRatio="none">
 <path d={Array.from({ length: 64 }).map((_, i) => {
 const x = i * 5;
 const y = 8 + Math.sin(i * 0.3 + positionSec * 3) * 6 + Math.cos(i * 0.7 + positionSec * 1.5) * 3;
 return `${i === 0 ? 'M' : 'L'} ${x} ${y}`;
 }).join(' ')} fill="none" stroke="currentColor" strokeWidth="1.5"
 className="text-accent/40" strokeLinecap="round" />
 </svg>
 )}
 {vizTheme === 2 && (
 <div className="flex items-center justify-center gap-1 h-4 mx-3">
 {Array.from({ length: 16 }).map((_, i) => {
 const r = 1.5 + Math.abs(Math.sin(i * 0.6 + positionSec * 2.5)) * 3;
 return <div key={i} className="rounded-full bg-accent/50"
 style={{ width: `${r * 2}px`, height: `${r * 2}px`,
 opacity: 0.3 + Math.abs(Math.sin(i * 0.5 + positionSec * 3)) * 0.7 }} />;
 })}
 </div>
 )}
 </button>
 )}

 {!loading && (
 <button onClick={toggleTimeDisplay} className="flex justify-between items-center px-3 mt-1 w-full text-left">
 <span className="text-[9px] text-ink-subtle tabular-nums">
 {showRemaining ? `-${fmtTime(duration - positionSec)}` : fmtTime(positionSec)}
 </span>
 <span className="text-[9px] text-ink-subtle tabular-nums">{progress}%</span>
 </button>
 )}

 {/* Voice + Play mode (center) */}
 {!loading && (
 <div className="flex items-center gap-2 px-3 mt-1">
 <select value={voice} onChange={e => changeVoice(e.target.value)}
 className="flex-1 text-[10px] rounded border border-input bg-card px-2 py-1 min-w-0">
 {voices.map(v => <option key={v.id} value={v.id}>{v.name} · {v.style}</option>)}
 </select>
 <button onClick={() => previewVoice(voice)}
 className="text-[9px] px-1.5 py-1 rounded border border-border text-ink-muted hover:text-accent shrink-0">▶</button>
 <button onClick={cyclePlayMode}
 className="text-[11px] px-1.5 py-1 rounded border border-border hover:bg-paper shrink-0"
 title={pm}>{MODE_LABELS[pm]}</button>
 </div>
 )}

 {/* Chapter context + mode badges */}
 {!loading && current && (
 <div className="px-3 text-[8px] text-ink-subtle text-center mt-0.5">
 {dramaticMode && '多角色 · '}
 {radioMode && '📻 电台 · '}
 {speedTrain && `🏃 Lv${speedTrainLevel} · `}
 第{current.chapterNum}章
 </div>
 )}

 {/* Controls: main row */}
 <div className="flex items-center justify-center gap-1.5 sm:gap-2 px-3 pt-1.5">
 <button onClick={() => skipChapter(-1)} disabled={loading}
 className="text-xs sm:text-sm p-1 text-ink-muted hover:text-ink disabled:opacity-20">⏮</button>
 <button onClick={() => skip15s(-1)} disabled={loading || !playing}
 className="text-[9px] w-11 h-6 rounded border border-border text-ink-muted hover:text-ink disabled:opacity-20 flex items-center justify-center"
 onContextMenu={e => { e.preventDefault(); cycleSkip(); }}
 title="快退，右键切换间隔">-{skipSeconds}s</button>
 <button onClick={cyclePlayMode}
 className="text-[10px] w-6 h-6 rounded-full border border-border flex items-center justify-center text-ink-muted hover:text-accent hover:border-accent/30 shrink-0"
 title={pm}>{MODE_LABELS[pm]}</button>

 {loading ? (
 <div className="w-12 h-12 flex items-center justify-center"><span className="text-xl animate-spin">⏳</span></div>
 ) : (
 <button aria-label="播放/暂停" onClick={togglePause} className="relative w-12 h-12 flex items-center justify-center group mx-1">
 <svg className="absolute inset-0 -rotate-90" width={48} height={48}>
 <circle cx={24} cy={24} r={21} fill="none" stroke="currentColor" strokeWidth="2.5" className="text-border" />
 <circle cx={24} cy={24} r={21} fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"
 className="text-accent" strokeDasharray={2 * Math.PI * 21}
 strokeDashoffset={2 * Math.PI * 21 - (progress / 100) * 2 * Math.PI * 21}
 style={{ transition: 'stroke-dashoffset 0.3s ease' }} />
 </svg>
 <span className="relative text-lg sm:text-xl group-hover:scale-110 transition-transform">{paused ? '▶' : '⏸'}</span>
 </button>
 )}

 <button onClick={() => skip15s(1)} disabled={loading || !playing}
 className="text-[9px] w-11 h-6 rounded border border-border text-ink-muted hover:text-ink disabled:opacity-20 flex items-center justify-center"
 onContextMenu={e => { e.preventDefault(); cycleSkip(); }}
 title="快进，右键切换间隔">+{skipSeconds}s</button>
 <button onClick={() => skipChapter(1)} disabled={loading}
 className="text-xs sm:text-sm p-1 text-ink-muted hover:text-ink disabled:opacity-20">⏭</button>
 </div>

 {/* Controls: secondary row */}
 <div className="flex items-center justify-center gap-1.5 px-3 pb-1.5">
 <button onClick={() => rewind30s()} disabled={loading || !playing}
 className="text-[9px] px-2 py-0.5 rounded border border-border text-ink-muted hover:text-ink disabled:opacity-20" title="回退30秒">↩30s</button>
 <button onClick={() => undoSkip()}
 className="text-[9px] px-2 py-0.5 rounded border border-border text-ink-muted hover:text-ink" title="回到切歌前位置">↶返回</button>
 <button aria-label="停止" onClick={stop} className="text-[9px] px-2 py-0.5 rounded border border-destructive/20 text-destructive hover:text-destructive ">⏹ 停止</button>
 <button onClick={() => addBookmark()} disabled={loading}
 className="text-[9px] px-2 py-0.5 rounded border border-warn/20 text-warn hover:text-warn disabled:opacity-20">🔖 标记</button>
 {autoContinue && !radioMode && <span className="text-[8px] text-accent/60 ml-1">连播中</span>}
 </div>

 {/* ── Creative features (collapsible) ── */}
 <div className="border-t border-border">
 <button onClick={() => setShowCreative(!showCreative)}
 className="w-full flex items-center justify-between px-3 py-1.5 text-[10px] text-ink-muted hover:text-ink transition-colors">
 <span>🎛 音效与模式 {unlockedCount > 0 ? `🏅${unlockedCount}` : ''}</span>
 <span className="text-[9px]">{showCreative ? '▾' : '▸'}</span>
 </button>

 {showCreative && (
 <div className="px-3 pb-2 space-y-2">
 {/* Radio + Dramatic + Sleep + Train */}
 <div className="flex items-center gap-1 flex-wrap">
 <button onClick={toggleRadioMode} title="跨书随机连播 · 像听广播"
 className={`text-[9px] px-2 py-0.5 rounded border ${radioMode ? 'bg-destructive-soft dark:bg-red-950/30 text-destructive border-destructive/20 ' : 'border-border text-ink-muted hover:text-ink'}`}>📻 电台</button>
 <button onClick={toggleDramaticMode} title="单人多声线 · 自动变调演绎角色"
 className={`text-[9px] px-2 py-0.5 rounded border ${dramaticMode ? 'bg-purple-100 dark:bg-purple-950/30 text-purple-600 dark:text-purple-400 border-purple-200 dark:border-purple-800' : 'border-border text-ink-muted hover:text-ink'}`}><Palette size={12} className="inline" /> 角色</button>
 <button onClick={toggleSleepStory} title="自动30min定时+渐弱 · 伴你入眠"
 className={`text-[9px] px-2 py-0.5 rounded border ${sleepStory ? 'bg-indigo-100 dark:bg-indigo-950/30 text-indigo-600 dark:text-indigo-400 border-indigo-200 dark:border-indigo-800' : 'border-border text-ink-muted hover:text-ink'}`}>🌙 睡前</button>
 <button onClick={toggleSpeedTrain} title="每章自动加速0.05x · 挑战听速极限"
 className={`text-[9px] px-2 py-0.5 rounded border ${speedTrain ? 'bg-orange-100 dark:bg-orange-950/30 text-orange-600 dark:text-orange-400 border-orange-200 dark:border-orange-800' : 'border-border text-ink-muted hover:text-ink'}`}>🏃 训练{speedTrain && speedTrainLevel > 0 ? ` Lv${speedTrainLevel}` : ''}</button>
 </div>

 {/* Focus + EQ + Viz */}
 <div className="flex items-center gap-1 flex-wrap">
 <button onClick={() => setFocusMode(!focusMode)}
 className={`text-[9px] px-2 py-0.5 rounded border ${focusMode ? 'bg-ink text-white dark:text-black' : 'border-border text-ink-muted hover:text-ink'}`}
 title="专注模式：隐藏所有控件，只留暂停">🧘 {focusMode ? '专注中' : '专注'}</button>
 <button onClick={cycleEQ}
 className={`text-[9px] px-2 py-0.5 rounded border ${eqPreset !== 'flat' ? 'bg-accent/10 border-accent/30 text-accent' : 'border-border text-ink-muted hover:text-ink'}`}
 title={eqPreset === 'voice' ? '语音增强：2.5kHz提6dB+高频提3dB，人声更清晰' : eqPreset === 'bass' ? '低音增强：200Hz提6dB，深沉氛围' : '原声直出'}>
 🎛 {eqPreset === 'voice' ? '语音' : eqPreset === 'bass' ? '低音' : '原声'}
 </button>
 <span className="text-[8px] text-ink-subtle">可视: {['柱', '波', '点'][vizTheme]}</span>
 </div>

 {/* Ambient */}
 <div>
 <span className="text-[9px] text-ink-subtle">🌿 环境音</span>
 <div className="flex items-center gap-1 mt-0.5 flex-wrap">
 {([ [null, '关'], ['rain', '雨声'], ['thunder', '雷声'], ['campfire', '火'], ['ocean', '海浪'], ['forest', '森林'], ['wind', '💨风'], ['cafe', '☕厅'], ['white', '⬜白'] ] as const).map(([key, label]) => {
 const tips: Record<string, string> = {
 rain: '淅沥雨声 · 安静阅读', thunder: '暴雨雷鸣 · 紧张氛围',
 campfire: '篝火噼啪 · 温暖放松', ocean: '海浪拍岸 · 舒缓入眠',
 forest: '鸟鸣风吟 · 自然漫步', wind: '呼啸风声 · 孤独沉思',
 cafe: '咖啡厅 murmur · 专注工作', white: '纯白噪音 · 屏蔽干扰',
 };
 return (
 <button key={label} onClick={() => setAmbient(key)}
 title={key ? tips[key] : '关闭环境音'}
 className={`text-[9px] px-1.5 py-0.5 rounded border ${ambient === key ? 'bg-accent/10 border-accent/30 text-accent' : 'border-border text-ink-muted hover:text-ink'}`}>{label}</button>
 );
 })}
 {ambient && (
 <input type="range" min="0" max="1" step="0.05" value={ambientVolume}
 onChange={e => setAmbientVolume(parseFloat(e.target.value))} className="w-12 h-1 accent-accent" />
 )}
 </div>
 </div>

 {/* Background Music */}
 <div>
 <span className="text-[9px] text-ink-subtle"><Music size={12} className="inline" /> 背景音乐</span>
 <div className="flex items-center gap-1 mt-0.5 flex-wrap">
 {([ [null, '关'], ['peaceful', '宁静'], ['tense', '紧张'], ['epic', '史诗'], ['melancholy', '忧伤'] ] as const).map(([key, label]) => {
 const tips: Record<string, string> = {
 peaceful: '大调和弦 · 平静放松', tense: '不协和音 · 悬疑氛围',
 epic: '深沉贝斯 · 宏大叙事', melancholy: '小九和弦 · 淡淡哀愁',
 };
 return (
 <button key={label} onClick={() => setMusic(key)}
 title={key ? tips[key] : '关闭背景音乐'}
 className={`text-[9px] px-1.5 py-0.5 rounded border ${music === key ? 'bg-accent/10 border-accent/30 text-accent' : 'border-border text-ink-muted hover:text-ink'}`}>{label}</button>
 );
 })}
 {music && (
 <input type="range" min="0" max="1" step="0.05" value={musicVolume}
 onChange={e => setMusicVolume(parseFloat(e.target.value))} className="w-12 h-1 accent-accent" />
 )}
 </div>
 </div>
 </div>
 )}
 </div>

 {/* Sleep countdown */}
 {sleepTimer > 0 && sleepRemaining > 0 && (
 <div className="mx-3 px-2 py-1 mb-1 rounded bg-warn-soft dark:bg-amber-950/30 border border-warn/20 flex items-center justify-between text-[9px]">
 <span className="text-warn ">⏰ {sleepRemaining <= 30 ? '🔉 渐弱… ' : ''}{fmtCountdown(sleepRemaining)}后暂停</span>
 <button onClick={cancelSleepTimer} className="text-warn hover:text-amber-700 dark:hover:text-amber-300 ml-2 shrink-0">取消</button>
 </div>
 )}

 {/* Playlist / History panel */}
 {(showPlaylist || showHistory) && (
 <div className="mx-3 mb-2 border border-border rounded-lg max-h-[200px] overflow-y-auto divide-y divide-border/50">
 {showPlaylist && (playlist.length === 0 ? <p className="text-[10px] text-ink-subtle text-center py-4">播放列表为空</p> :
 playlist.map((item, i) => {
 const isCurrent = current.novelId === item.novelId && current.chapterNum === item.chapterNum;
 return (
 <div key={`${item.novelId}-${item.chapterNum}`} onClick={() => playChapter(item)}
 className={`flex items-center gap-2 px-2 py-1.5 text-[10px] cursor-pointer ${isCurrent ? 'bg-accent-soft/20 text-accent' : 'hover:bg-paper text-ink'}`}>
 <span className="shrink-0">{isCurrent ? '' : ''}</span>
 <span className="flex-1 truncate">{item.novelTitle.slice(0, 6)} · {item.chapterNum}</span>
 <button onClick={e => { e.stopPropagation(); removeFromPlaylist(i); }} className="text-ink-subtle hover:text-destructive shrink-0">×</button>
 </div>
 );
 })
 )}
 {showHistory && (() => {
 const history = getHistory().filter(h => !(current.novelId === h.novelId && current.chapterNum === h.chapterNum));
 return history.length === 0 ? <p className="text-[10px] text-ink-subtle text-center py-4">暂无播放记录</p> :
 history.map((item, i) => (
 <div key={`hist-${item.novelId}-${item.chapterNum}-${i}`} onClick={() => playChapter(item)}
 className="flex items-center gap-2 px-2 py-1.5 text-[10px] cursor-pointer hover:bg-paper text-ink">
 <span className="shrink-0">🕐</span>
 <span className="flex-1 truncate">{item.novelTitle.slice(0, 8)} · 第{item.chapterNum}章</span>
 </div>
 ));
 })()}
 </div>
 )}

 {/* Bottom bar */}
 <div className="flex items-center justify-between px-3 py-1 border-t border-border">
 <div className="flex items-center gap-1">
 <button onClick={() => { setShowPlaylist(!showPlaylist); setShowHistory(false); }}
 className={`text-[9px] px-2 py-0.5 rounded border ${showPlaylist ? 'bg-accent/10 border-accent/30 text-accent' : 'border-border text-ink-muted hover:text-ink'}`}><ClipboardList size={12} className="inline" /> ({playlist.length})</button>
 <button onClick={() => { setShowHistory(!showHistory); setShowPlaylist(false); }}
 className={`text-[9px] px-2 py-0.5 rounded border ${showHistory ? 'bg-accent/10 border-accent/30 text-accent' : 'border-border text-ink-muted hover:text-ink'}`}>🕐</button>
 </div>
 <button onClick={() => navigate('/listen')} className="text-[9px] text-ink-subtle hover:text-accent">完整页 →</button>
 </div>

 {/* Expanded panel */}
 {expanded && (
 <div className="px-3 pb-3 space-y-2 border-t border-border pt-2">
 <div className="flex items-center gap-2">
 <span className="text-[9px] text-ink-subtle shrink-0">语速</span>
 <button onClick={() => changeSpeed(Math.max(0.5, +(speed - 0.05).toFixed(2)))}
 className="text-[10px] w-5 h-5 rounded border border-border flex items-center justify-center text-ink-muted hover:text-ink shrink-0">−</button>
 <input type="range" min="0.5" max="2.0" step="0.05" value={speed}
 onChange={e => changeSpeed(parseFloat(e.target.value))} className="flex-1 h-1 accent-accent" />
 <button onClick={() => changeSpeed(Math.min(2.0, +(speed + 0.05).toFixed(2)))}
 className="text-[10px] w-5 h-5 rounded border border-border flex items-center justify-center text-ink-muted hover:text-ink shrink-0">+</button>
 <span className="text-[10px] text-ink tabular-nums w-8 text-right shrink-0">{speed.toFixed(2)}x</span>
 </div>
 <div className="flex items-center gap-2">
 <span className="text-[9px] text-ink-subtle shrink-0">音量</span>
 <input type="range" min="0" max="1" step="0.05" value={volume}
 onChange={e => setVolume(parseFloat(e.target.value))} className="flex-1 h-1 accent-accent" />
 <span className="text-[10px] text-ink tabular-nums w-6 text-right shrink-0">{Math.round(volume * 100)}%</span>
 </div>
 <div className="flex items-center gap-2 flex-wrap">
 <span className="text-[9px] text-ink-muted">⏰</span>
 {[15, 30, 45, 60].map(m => (
 <button key={m} onClick={() => sleepTimer === m ? cancelSleepTimer() : startSleepTimer(m)}
 className={`text-[9px] px-1.5 py-0.5 rounded ${sleepTimer === m ? 'bg-accent text-white' : 'text-ink-muted hover:text-ink'}`}>{m}min</button>
 ))}
 <form onSubmit={handleCustomTimer} className="flex items-center gap-0.5">
 <input type="number" min="1" max="180" placeholder="自定义" value={customTimer} onChange={e => setCustomTimer(e.target.value)}
 className="w-10 text-[9px] rounded border border-input bg-card px-1 py-0.5 text-center" />
 <button type="submit" className="text-[9px] text-accent px-0.5">✓</button>
 </form>
 {sleepTimer > 0 && (
 <button onClick={() => setSleepAtChapterEnd(!sleepAtChapterEnd)}
 className={`text-[9px] px-1.5 py-0.5 rounded border ${sleepAtChapterEnd ? 'bg-accent/10 border-accent/30 text-accent' : 'border-border text-ink-muted'}`}
 title="本章结束后停止，不会在句子中间断开">
 章尾停
 </button>
 )}
 </div>
 {/* Sound profiles */}
 {profiles.length > 0 && (
 <div className="border-t border-border pt-2">
 <span className="text-[9px] text-ink-subtle">💾 预设</span>
 <div className="flex gap-1 mt-0.5 flex-wrap">
 {profiles.map(p => (
 <button key={p.name} onClick={() => loadProfile(p)}
 className="text-[9px] px-2 py-0.5 rounded border border-border text-ink-muted hover:text-accent"
 title={`${p.voice.slice(-4)} ${p.speed}x`}>{p.name}</button>
 ))}
 </div>
 </div>
 )}
 <button onClick={saveProfile}
 className="w-full text-[9px] text-ink-muted hover:text-accent py-0.5 border-t border-border">
 💾 保存当前设置
 </button>

 {/* Jump to chapter */}
 <button onClick={() => {
 navigate(`/novels/${current.novelId}?chapter=${current.chapterNum}`);
 sessionStorage.setItem(`auto-expand-${current.novelId}`, String(current.chapterNum));
 }}
 className="w-full text-[9px] text-accent hover:text-accent/80 text-center py-1 border-t border-border">
 <BookOpen size={12} className="inline" /> 打开《{current.novelTitle.slice(0, 8)}》第{current.chapterNum}章 →
 </button>

 {(() => {
 try {
 const s = JSON.parse(localStorage.getItem('audio-stats') || '{}');
 const h = Math.round((s.seconds || 0) / 3600 * 10) / 10;
 const ch = s.chapters || 0;
 const days = (s.days || []).length;
 if (h === 0 && ch === 0) return null;
 return (
 <div className="text-[8px] text-ink-subtle text-center border-t border-border pt-2">
 <BarChart3 size={12} className="inline" /> 累计 {h}小时 · {ch}章 · {days}天
 </div>
 );
 } catch { return null; }
 })()}
 <div className="text-[8px] text-ink-subtle text-center border-t border-border pt-2">
 左右滑动切歌 · <kbd className="px-1 py-0.5 rounded bg-paper border border-border font-mono">Space</kbd> 暂停 · <kbd className="px-1 py-0.5 rounded bg-paper border border-border font-mono">←→</kbd> ±15s
 </div>
 </div>
 )}
 </div>
 );
}
