import { useState, useEffect, useRef, useCallback } from 'react';
import { api } from 'src/lib/api';
import type { ChapterMeta } from 'src/types';

interface Device {
 name: string;
 width: number;
 height: number;
 notch: boolean;
 ratio: string;
 icon: string;
}

const DEVICES: Device[] = [
 { name: 'iPhone SE', width: 375, height: 667, notch: false, ratio: '16:9', icon: '' },
 { name: 'iPhone 14 Pro', width: 393, height: 852, notch: true, ratio: '19.5:9', icon: '' },
 { name: 'iPhone 14 Pro Max', width: 430, height: 932, notch: true, ratio: '19.5:9', icon: '' },
 { name: 'Pixel 7', width: 412, height: 915, notch: false, ratio: '20:9', icon: '' },
 { name: 'iPad Mini', width: 744, height: 1024, notch: false, ratio: '4:3', icon: '📟' },
];

const FONT_SIZES = [15, 17, 19, 22];
const FONT_LABELS = ['小', '中', '大', '特大'];

interface Props {
 novelId: string;
 chapters: ChapterMeta[];
 initialChapter: number;
 onClose: () => void;
}

export function MobileReadingMode({ novelId, chapters, initialChapter, onClose }: Props) {
 const writable = chapters.filter(c => c.word_count > 0);
 const startIdx = writable.findIndex(c => c.number === initialChapter);
 const [currentIdx, setCurrentIdx] = useState(startIdx >= 0 ? startIdx : 0);
 const [content, setContent] = useState('');
 const [loading, setLoading] = useState(true);
 const [phoneDark, setPhoneDark] = useState(true);
 const [readProgress, setReadProgress] = useState(0);
 const [fontSizeIdx, setFontSizeIdx] = useState(1); // default "中" = 17px
 const [deviceIdx, setDeviceIdx] = useState(1); // default iPhone 14 Pro
 const contentRef = useRef<HTMLDivElement>(null);
 const progressRef = useRef<HTMLDivElement>(null);
 const progressTextRef = useRef<HTMLSpanElement>(null);
 const touchStartX = useRef(0);

 const device = DEVICES[deviceIdx];
 const fontSize = FONT_SIZES[fontSizeIdx];
 const currentChapter = writable[currentIdx];
 const hasPrev = currentIdx > 0;
 const hasNext = currentIdx < writable.length - 1;

 // Scale phone frame to fit viewport
 const vh = typeof window !== 'undefined' ? window.innerHeight : 900;
 const maxPhoneH = vh * 0.9;
 const scale = Math.min(1, maxPhoneH / device.height);
 const displayW = Math.round(device.width * scale);
 const displayH = Math.round(device.height * scale);

 const loadChapter = useCallback(async (idx: number) => {
 const ch = writable[idx];
 if (!ch) return;
 setLoading(true);
 setContent('');
 setReadProgress(0);
 try {
 const data = await api.novels.chapter(novelId, ch.number);
 setContent(data.content || '(暂无正文)');
 } catch { setContent('正文尚未生成'); }
 finally { setLoading(false); }
 }, [novelId, writable]);

 useEffect(() => { loadChapter(currentIdx); }, [currentIdx, loadChapter]);

 // Save reading position on close
 useEffect(() => {
 return () => {
 if (currentChapter) {
 const el = contentRef.current;
 const scrollPos = el ? el.scrollTop : 0;
 localStorage.setItem(`reading-pos-${novelId}`, JSON.stringify({
 chapter: currentChapter.number, scroll: scrollPos, timestamp: Date.now(),
 }));
 }
 };
 }, []);

 // Restore reading position
 useEffect(() => {
 if (!content || loading) return;
 try {
 const saved = JSON.parse(localStorage.getItem(`reading-pos-${novelId}`) || 'null');
 if (saved && saved.chapter === currentChapter?.number) {
 setTimeout(() => {
 const el = contentRef.current;
 if (el) el.scrollTop = saved.scroll || 0;
 }, 100);
 }
 } catch {}
 }, [content, loading]);

 // Keyboard
 useEffect(() => {
 const handler = (e: KeyboardEvent) => {
 if (e.key === 'Escape') onClose();
 if (e.key === 'ArrowLeft' && hasPrev) setCurrentIdx(i => i - 1);
 if (e.key === 'ArrowRight' && hasNext) setCurrentIdx(i => i + 1);
 };
 window.addEventListener('keydown', handler);
 return () => window.removeEventListener('keydown', handler);
 }, [onClose, hasPrev, hasNext]);

 // Scroll progress — direct DOM update, zero lag
 useEffect(() => {
 const el = contentRef.current;
 const bar = progressRef.current;
 const text = progressTextRef.current;
 if (!el || !bar) return;

 const handler = () => {
 const { scrollTop, scrollHeight, clientHeight } = el;
 const pct = scrollHeight <= clientHeight
 ? 100
 : Math.round((scrollTop / (scrollHeight - clientHeight)) * 100);
 bar.style.width = `${pct}%`;
 if (text) text.textContent = `${pct}%`;
 };

 // Slow state update for remaining-time display
 let timer: ReturnType<typeof setTimeout>;
 const debouncedState = () => {
 clearTimeout(timer);
 timer = setTimeout(() => {
 const { scrollTop, scrollHeight, clientHeight } = el;
 setReadProgress(scrollHeight <= clientHeight ? 100 : Math.round((scrollTop / (scrollHeight - clientHeight)) * 100));
 }, 1000);
 };

 el.addEventListener('scroll', handler, { passive: true });
 el.addEventListener('scroll', debouncedState, { passive: true });
 return () => {
 el.removeEventListener('scroll', handler);
 el.removeEventListener('scroll', debouncedState);
 clearTimeout(timer);
 };
 }, [content]);

 // Touch swipe
 function handleTouchStart(e: React.TouchEvent<HTMLDivElement>) {
 touchStartX.current = e.touches[0].clientX;
 }
 function handleTouchEnd(e: React.TouchEvent<HTMLDivElement>) {
 const diff = touchStartX.current - e.changedTouches[0].clientX;
 if (Math.abs(diff) > 80) {
 if (diff > 0 && hasNext) setCurrentIdx(i => i + 1);
 else if (diff < 0 && hasPrev) setCurrentIdx(i => i - 1);
 }
 }

 // Estimated remaining reading time
 const totalChars = content.replace(/\s/g, '').length;
 const charsRead = Math.round(totalChars * (readProgress / 100));
 const charsRemaining = totalChars - charsRead;
 const remainingMin = Math.max(0, Math.ceil(charsRemaining / 400));

 // Estimated screens for mobile reading
 const [totalScreens, setTotalScreens] = useState(1);
 useEffect(() => {
 const el = contentRef.current;
 if (!el) return;
 const h = el.clientHeight || 600;
 setTotalScreens(Math.max(1, Math.ceil(el.scrollHeight / h)));
 }, [content]);
 const currentScreen = Math.max(1, Math.min(totalScreens, Math.ceil((readProgress / 100) * totalScreens)));

 if (!currentChapter) return null;

 return (
 <div className="fixed inset-0 z-[80] flex items-center justify-center bg-black/60 backdrop-blur-sm"
 onClick={onClose}>
 {/* Device selector panel */}
 <div className="absolute top-4 left-1/2 -translate-x-1/2 z-[85] bg-card/90 backdrop-blur border border-border rounded-xl px-2 py-1.5 flex items-center gap-1 shadow-lg animate-[fadeSlideIn_0.15s_ease-out]">
 {DEVICES.map((d, i) => (
 <button key={d.name}
 onClick={e => { e.stopPropagation(); setDeviceIdx(i); }}
 className={`text-[11px] px-2 py-1 rounded-md transition-colors whitespace-nowrap ${
 i === deviceIdx ? 'bg-accent text-white' : 'text-ink-muted hover:text-ink hover:bg-paper'
 }`}
 title={`${d.name} ${d.width}×${d.height}`}>
 {d.icon} {d.name}
 </button>
 ))}
 </div>

 {/* Phone Frame */}
 <div className="relative bg-black rounded-[3rem] border-[4px] border-zinc-700 shadow-2xl overflow-hidden flex flex-col"
 style={{ width: displayW, height: displayH }}
 onClick={e => e.stopPropagation()}
 onTouchStart={handleTouchStart}
 onTouchEnd={handleTouchEnd}>

 {/* Notch */}
 {device.notch && (
 <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[120px] h-[30px] bg-black rounded-b-2xl z-10" />
 )}

 {/* Status bar */}
 <div className="h-8 bg-black flex items-center justify-between px-6 pt-1 shrink-0">
 <span className="text-[10px] text-white/70 font-medium">9:41</span>
 <span className="text-[10px] text-white/70">●●●●○</span>
 </div>

 {/* Reading app */}
 <div className={`flex-1 min-h-0 flex flex-col ${phoneDark ? 'bg-zinc-900' : 'bg-warn-soft'}`}>
 {/* App header */}
 <div className="flex items-center justify-between px-3 py-1.5 shrink-0">
 <button onClick={onClose}
 className={`text-[11px] px-2 py-1 rounded-full transition-colors ${phoneDark ? 'text-white/50 hover:text-white/80 hover:bg-white/5' : 'text-zinc-500 hover:text-zinc-700'}`}>
 ← 退出
 </button>
 <div className="flex items-center gap-0.5">
 {FONT_SIZES.map((_, i) => (
 <button key={i}
 onClick={() => setFontSizeIdx(i)}
 className={`text-[10px] px-2 py-1 rounded transition-colors ${
 i === fontSizeIdx
 ? phoneDark ? 'text-white bg-white/10' : 'text-zinc-700 bg-zinc-100'
 : phoneDark ? 'text-white/40 hover:text-white/70' : 'text-zinc-400 hover:text-zinc-600'
 }`}>
 {FONT_LABELS[i]}
 </button>
 ))}
 </div>
 <button onClick={() => setPhoneDark(!phoneDark)}
 className={`text-[11px] px-2 py-1 rounded-full transition-colors ${phoneDark ? 'text-white/50 hover:text-white/80' : 'text-zinc-500 hover:text-zinc-700'}`}>
 {phoneDark ? '☀' : '☾'}
 </button>
 </div>

 {/* Reading stats bar */}
 <div className={`flex items-center gap-3 px-4 py-1 text-[10px] ${phoneDark ? 'text-white/30' : 'text-zinc-400'} border-b border-white/5`}>
 <span ref={progressTextRef}>0%</span>
 {remainingMin > 0 && readProgress < 100 && (
 <span>剩约{remainingMin}分钟</span>
 )}
 <span>{currentScreen}/{totalScreens}屏</span>
 <span className="ml-auto">{currentChapter.word_count.toLocaleString()}字</span>
 </div>

 {/* Progress bar */}
 <div className="h-px bg-white/5">
 <div ref={progressRef} className="h-full bg-accent"
 style={{ width: '0%' }} />
 </div>

 {/* Content */}
 <div ref={contentRef}
 className={`flex-1 min-h-0 px-4 py-4 font-[KaiTi,STKaiti,serif] leading-[2.2] tracking-wide ${
 phoneDark ? 'text-zinc-200' : 'text-zinc-800'
 }`}
 style={{ fontSize: `${fontSize}px`, scrollbarGutter: 'stable', overflowY: 'scroll' }}>
 {loading ? (
 <div className="space-y-3 py-8">
 {[90, 75, 85, 50, 92, 68].map((w, i) => (
 <div key={i} className="skeleton h-3 rounded"
 style={{ width: `${w}%`, animationDelay: `${i * 0.1}s`,
 background: phoneDark ? '#3f3f46' : '#d4d4d8' }} />
 ))}
 </div>
 ) : (
 <div>
 <h1 className={`text-[1.3em] font-bold mb-6 text-center ${phoneDark ? 'text-white' : 'text-zinc-900'}`}>
 第{currentChapter.number}章<br/>
 <span className="text-[1em] font-normal opacity-80">{currentChapter.title}</span>
 </h1>
 {content.split('\n').map((line, i) => {
 const trimmed = line.trim();
 if (!trimmed) return <br key={i} />;
 if (trimmed === '---' || trimmed === '***' || trimmed === '___')
 return <div key={i} className="text-center my-6 opacity-30 tracking-[0.5em]">✦ ✦ ✦</div>;
 if (trimmed.startsWith('# ')) return null;
 if (trimmed.startsWith('## '))
 return <h2 key={i} className={`text-[1.1em] font-semibold my-4 ${phoneDark ? 'text-white/90' : 'text-zinc-800'}`}>{trimmed.replace(/^## /, '')}</h2>;
 if (trimmed.startsWith('> '))
 return <blockquote key={i} className={`border-l-2 border-accent/40 pl-3 my-3 italic ${phoneDark ? 'text-white/40' : 'text-zinc-500'}`}>{trimmed.replace(/^> /, '')}</blockquote>;
 return <p key={i} className="mb-[0.6em] text-justify">{trimmed}</p>;
 })}

 {/* Chapter end marker */}
 <div className={`text-center my-8 text-[12px] ${phoneDark ? 'text-white/20' : 'text-zinc-300'}`}>
 — 第{currentChapter.number}章完 —
 </div>
 </div>
 )}
 </div>

 {/* Bottom nav */}
 <div className={`flex items-center justify-between px-5 py-3 shrink-0 border-t ${phoneDark ? 'border-white/5' : 'border-zinc-200'}`}>
 <button
 onClick={() => setCurrentIdx(i => i - 1)}
 disabled={!hasPrev}
 className={`text-[12px] px-3 py-2 rounded-full transition-colors ${
 hasPrev
 ? phoneDark ? 'text-white/60 hover:bg-white/10 active:bg-white/20' : 'text-zinc-500 hover:bg-zinc-100'
 : 'text-white/15 cursor-not-allowed'
 }`}>
 ← 上一章
 </button>
 <span className={`text-[10px] ${phoneDark ? 'text-white/25' : 'text-zinc-400'} tabular-nums font-mono`}>
 {currentIdx + 1}/{writable.length}
 </span>
 <button
 onClick={() => setCurrentIdx(i => i + 1)}
 disabled={!hasNext}
 className={`text-[12px] px-3 py-2 rounded-full transition-colors ${
 hasNext
 ? phoneDark ? 'text-white/60 hover:bg-white/10 active:bg-white/20' : 'text-zinc-500 hover:bg-zinc-100'
 : 'text-white/15 cursor-not-allowed'
 }`}>
 下一章 →
 </button>
 </div>
 </div>

 {/* Home indicator */}
 <div className="h-7 bg-black flex items-center justify-center shrink-0">
 <div className="w-28 h-1 bg-zinc-700 rounded-full" />
 </div>
 </div>
 </div>
 );
}
