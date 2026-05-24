import { useState, useEffect, useRef, useCallback } from 'react';
import { toast } from 'sonner';

const VOICES = [
  { id: 'zh-CN-XiaoxiaoNeural', name: '晓晓', gender: '女', style: '温柔' },
  { id: 'zh-CN-YunxiNeural', name: '云希', gender: '男', style: '沉稳' },
  { id: 'zh-CN-XiaoyiNeural', name: '晓伊', gender: '女', style: '活泼' },
  { id: 'zh-CN-YunyangNeural', name: '云扬', gender: '男', style: '新闻' },
  { id: 'zh-CN-XiaochenNeural', name: '晓辰', gender: '女', style: '自然' },
  { id: 'zh-CN-YunjianNeural', name: '云健', gender: '男', style: '运动' },
];

interface ChapterInfo { number: number; title: string; word_count: number; novelId: string; novelTitle: string; }

export function AudioPlayer() {
  const [show, setShow] = useState(false);
  const [mini, setMini] = useState(false);
  const [playing, setPlaying] = useState(false);
  const [paused, setPaused] = useState(false);
  const [current, setCurrent] = useState<ChapterInfo | null>(null);
  const [speed, setSpeed] = useState(1.0);
  const [progress, setProgress] = useState(0);
  const [voice, setVoice] = useState(() => localStorage.getItem('tts-voice') || 'zh-CN-XiaoxiaoNeural');
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const sleepTimerRef = useRef<ReturnType<typeof setTimeout>>();
  const [sleepTimer, setSleepTimer] = useState(0); // minutes, 0 = off

  // Draggable
  const [pos, setPos] = useState({ x: typeof window !== 'undefined' ? window.innerWidth - 320 : 900, y: 200 });
  const dragRef = useRef({ dragging: false, startX: 0, startY: 0, origX: 0, origY: 0 });

  // Load playlist from localStorage
  const [playlist, setPlaylist] = useState<ChapterInfo[]>(() => {
    try { return JSON.parse(localStorage.getItem('audio-playlist') || '[]'); } catch { return []; }
  });

  // Resume position
  const [resumePos, setResumePos] = useState<number>(() => {
    try { return JSON.parse(localStorage.getItem('audio-resume') || 'null')?.position || 0; } catch { return 0; }
  });

  function saveResume(ch: ChapterInfo, pos: number) {
    localStorage.setItem('audio-resume', JSON.stringify({ chapter: ch.number, novelId: ch.novelId, position: pos, time: Date.now() }));
    setResumePos(pos);
  }

  function addToPlaylist(ch: ChapterInfo) {
    setPlaylist(prev => {
      if (prev.find(p => p.number === ch.number && p.novelId === ch.novelId)) return prev;
      const next = [...prev, ch];
      localStorage.setItem('audio-playlist', JSON.stringify(next));
      return next;
    });
    toast.success(`已加入播放列表`);
  }

  function removeFromPlaylist(idx: number) {
    setPlaylist(prev => {
      const next = prev.filter((_, i) => i !== idx);
      localStorage.setItem('audio-playlist', JSON.stringify(next));
      return next;
    });
  }

  function playChapter(ch: ChapterInfo, seekTo = 0) {
    if (audioRef.current) { audioRef.current.pause(); audioRef.current = null; }
    const rateParam = speed === 1.0 ? '+0%' : speed > 1 ? `+${Math.round((speed-1)*100)}%` : `${Math.round((speed-1)*100)}%`;
    const audio = new Audio(`/api/novels/${ch.novelId}/chapters/${ch.number}/tts?voice=${voice}&rate=${rateParam}`);
    audioRef.current = audio;
    audio.currentTime = seekTo;
    audio.onloadedmetadata = () => { setCurrent(ch); setPlaying(true); setPaused(false); };
    audio.ontimeupdate = () => {
      if (audio.duration) {
        setProgress(Math.round((audio.currentTime / audio.duration) * 100));
        saveResume(ch, audio.currentTime);
      }
    };
    audio.onended = () => {
      setProgress(100);
      const idx = playlist.findIndex(p => p.number === ch.number && p.novelId === ch.novelId);
      const next = playlist[idx + 1];
      if (next) { toast.info(`${next.novelTitle} · 第${next.number}章`, { duration: 2000 }); setTimeout(() => playChapter(next), 500); }
      else { setPlaying(false); toast.success('播放列表结束'); }
    };
    audio.onerror = () => { toast.error('播放失败'); setPlaying(false); };
    audio.play().catch(() => toast.error('播放失败'));
  }

  function togglePause() {
    if (!audioRef.current) return;
    if (paused) { audioRef.current.play(); setPaused(false); }
    else { audioRef.current.pause(); setPaused(true); if (current) saveResume(current, audioRef.current.currentTime); }
  }

  function stop() {
    if (audioRef.current) { audioRef.current.pause(); audioRef.current = null; }
    setPlaying(false); setPaused(false); setProgress(0);
    cancelSleepTimer();
  }

  function startSleepTimer(mins: number) {
    if (sleepTimerRef.current) clearTimeout(sleepTimerRef.current);
    setSleepTimer(mins);
    sleepTimerRef.current = setTimeout(() => {
      toast.info('⏰ 定时结束，已暂停');
      if (audioRef.current) audioRef.current.pause();
      setPaused(true); setSleepTimer(0);
    }, mins * 60000);
  }
  function cancelSleepTimer() {
    if (sleepTimerRef.current) clearTimeout(sleepTimerRef.current);
    setSleepTimer(0);
  }

  function skipChapter(dir: 1 | -1) {
    if (!current) return;
    const idx = playlist.findIndex(p => p.number === current.number && p.novelId === current.novelId);
    const target = playlist[idx + dir];
    if (target) playChapter(target);
  }

  function playRandom() {
    if (playlist.length === 0) return;
    const random = playlist[Math.floor(Math.random() * playlist.length)];
    playChapter(random);
  }

  function changeVoice(v: string) {
    setVoice(v); localStorage.setItem('tts-voice', v);
    if (current && audioRef.current) {
      const pos = audioRef.current.currentTime;
      playChapter(current, pos);
    }
  }

  function changeSpeed(s: number) {
    setSpeed(s);
    if (current && audioRef.current) {
      const pos = audioRef.current.currentTime;
      playChapter(current, pos);
    }
  }

  // Drag handlers
  function onDragStart(e: React.MouseEvent) {
    dragRef.current = { dragging: true, startX: e.clientX, startY: e.clientY, origX: pos.x, origY: pos.y };
  }
  useEffect(() => {
    const move = (e: MouseEvent) => {
      if (!dragRef.current.dragging) return;
      setPos({ x: dragRef.current.origX + (e.clientX - dragRef.current.startX), y: dragRef.current.origY + (e.clientY - dragRef.current.startY) });
    };
    const up = () => { dragRef.current.dragging = false; };
    window.addEventListener('mousemove', move);
    window.addEventListener('mouseup', up);
    return () => { window.removeEventListener('mousemove', move); window.removeEventListener('mouseup', up); };
  }, []);

  if (!show && !mini) {
    return (
      <button onClick={() => { setShow(true); setMini(false); }}
        className="text-[11px] text-ink-muted hover:text-accent px-2 py-1 rounded border border-border hover:border-accent/30 transition-colors">
        🎧 听书
      </button>
    );
  }

  // Mini mode — just current track info
  if (mini && current) {
    return (
      <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 bg-card border border-border rounded-full shadow-xl px-4 py-2 flex items-center gap-3 text-xs animate-[fadeSlideIn_0.2s_ease-out]"
        style={{ userSelect: 'none' }}>
        <span className="text-ink-muted">🎧</span>
        <div className="flex flex-col min-w-0">
          <span className="text-ink font-medium truncate max-w-[180px]">{current.novelTitle} · Ch{current.number}</span>
          <div className="h-0.5 bg-border rounded-full mt-0.5 w-full">
            <div className="h-full bg-accent rounded-full transition-all" style={{ width: `${progress}%` }} />
          </div>
        </div>
        <button onClick={togglePause} className="text-accent shrink-0">{paused ? '▶' : '⏸'}</button>
        <button onClick={() => setMini(false)} className="text-ink-muted shrink-0">展开</button>
      </div>
    );
  }

  return (
    <div className="fixed z-50 bg-card border border-border rounded-xl shadow-2xl w-[340px] animate-[fadeSlideIn_0.2s_ease-out]"
      style={{ left: pos.x, top: pos.y, userSelect: 'none' }}>
      {/* Drag handle */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-border cursor-move"
        onMouseDown={onDragStart}>
        <span className="text-xs font-semibold text-ink">🎧 有声书</span>
        <div className="flex items-center gap-1">
          <button onClick={() => setMini(true)} className="text-[10px] text-ink-muted hover:text-ink px-1">—</button>
          <button onClick={() => { stop(); setShow(false); setMini(false); }}
            className="text-[10px] text-ink-muted hover:text-ink px-1">✕</button>
        </div>
      </div>

      <div className="p-3 space-y-2.5 max-h-[500px] overflow-y-auto">
        {/* Voice + Speed */}
        <div className="flex gap-2">
          <select value={voice} onChange={e => changeVoice(e.target.value)}
            className="flex-1 text-[10px] rounded border border-input bg-card px-2 py-1">
            {VOICES.map(v => <option key={v.id} value={v.id}>{v.name} · {v.gender} {v.style}</option>)}
          </select>
          <div className="flex gap-0.5">
            {[0.8, 1.0, 1.2, 1.5].map(s => (
              <button key={s} onClick={() => changeSpeed(s)}
                className={`text-[9px] px-1.5 py-0.5 rounded ${speed === s ? 'bg-accent text-white' : 'text-ink-muted hover:text-ink'}`}>
                {s}x
              </button>
            ))}
          </div>
        </div>

        {/* Now playing */}
        {current && (
          <div className="p-2 rounded-lg bg-accent-soft/20 border border-accent/10">
            <div className="flex items-center justify-between">
              <div className="flex-1 min-w-0">
                <p className="text-[11px] font-medium text-ink truncate">{current.novelTitle}</p>
                <p className="text-[10px] text-ink-muted">第{current.number}章 {current.title}</p>
              </div>
              <span className="text-[9px] text-ink-subtle tabular-nums shrink-0 ml-2">{progress}%</span>
            </div>
            <div className="h-1 bg-border rounded-full mt-1.5 overflow-hidden">
              <div className="h-full bg-accent rounded-full transition-all duration-300" style={{ width: `${progress}%` }} />
            </div>
          </div>
        )}

        {/* Sleep timer */}
        <div className="flex items-center gap-1 justify-center">
          <span className="text-[9px] text-ink-muted">⏰</span>
          {[15, 30, 45, 60].map(m => (
            <button key={m} onClick={() => sleepTimer === m ? cancelSleepTimer() : startSleepTimer(m)}
              className={`text-[9px] px-1.5 py-0.5 rounded ${sleepTimer === m ? 'bg-accent text-white' : 'text-ink-muted hover:text-ink'}`}>
              {m}min
            </button>
          ))}
          {sleepTimer > 0 && <span className="text-[9px] text-amber-500">{sleepTimer}分钟后暂停</span>}
        </div>

        {/* Controls */}
        <div className="flex items-center justify-center gap-2">
          <button onClick={() => skipChapter(-1)} disabled={!current}
            className="text-sm p-1 text-ink-muted hover:text-ink disabled:opacity-20">⏮</button>
          <button onClick={playRandom} disabled={playlist.length === 0}
            className="text-sm p-1 text-ink-muted hover:text-accent disabled:opacity-20">🔀</button>
          <button onClick={current ? togglePause : undefined}
            className="text-2xl p-1 text-accent hover:scale-110 transition-transform">
            {playing && !paused ? '⏸' : '▶'}
          </button>
          <button onClick={stop} disabled={!playing}
            className="text-sm p-1 text-red-400 hover:text-red-600 disabled:opacity-20">⏹</button>
          <button onClick={() => skipChapter(1)} disabled={!current}
            className="text-sm p-1 text-ink-muted hover:text-ink disabled:opacity-20">⏭</button>
        </div>

        {/* Playlist */}
        <div className="border-t border-border pt-2">
          <div className="flex items-center justify-between mb-1">
            <span className="text-[10px] text-ink-muted">播放列表 ({playlist.length})</span>
            {playlist.length > 0 && (
              <button onClick={() => { setPlaylist([]); localStorage.removeItem('audio-playlist'); }}
                className="text-[9px] text-red-400 hover:text-red-600">清空</button>
            )}
          </div>
          {playlist.length === 0 ? (
            <p className="text-[10px] text-ink-subtle text-center py-3">
              打开小说 → 🎧 听书 → 选章节 → 自动加入列表
            </p>
          ) : (
            <div className="space-y-0.5 max-h-[200px] overflow-y-auto">
              {playlist.map((ch, i) => {
                const isCurrent = current?.number === ch.number && current?.novelId === ch.novelId;
                return (
                  <div key={`${ch.novelId}-${ch.number}`}
                    onClick={() => playChapter(ch)}
                    className={`flex items-center gap-2 px-2 py-1.5 rounded text-[10px] cursor-pointer transition-colors ${
                      isCurrent ? 'bg-accent-soft/30 text-accent' : 'hover:bg-paper text-ink'}`}>
                    <span className="text-ink-subtle shrink-0">{isCurrent && playing ? '🔊' : '🎵'}</span>
                    <span className="flex-1 truncate">{ch.novelTitle} · 第{ch.number}章</span>
                    <button onClick={e => { e.stopPropagation(); removeFromPlaylist(i); }}
                      className="text-ink-subtle hover:text-red-500 shrink-0">×</button>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

/** Hook for chapter list integration */
export function useAddToPlaylist() {
  return (novelId: string, novelTitle: string, ch: { number: number; title: string; word_count: number }) => {
    const item: ChapterInfo = { ...ch, novelId, novelTitle };
    const prev = JSON.parse(localStorage.getItem('audio-playlist') || '[]');
    if (prev.find((p: ChapterInfo) => p.number === item.number && p.novelId === item.novelId)) {
      toast.info('已在播放列表');
      return;
    }
    localStorage.setItem('audio-playlist', JSON.stringify([...prev, item]));
    toast.success(`已加入播放列表`);
  };
}
