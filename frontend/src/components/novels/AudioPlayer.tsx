import { useState, useEffect, useRef, useCallback } from 'react';
import { toast } from 'sonner';

interface Props {
  novelId: string;
  chapters: { number: number; title: string; word_count: number }[];
  onChapterChange?: (num: number) => void;
}

export function AudioPlayer({ novelId, chapters, onChapterChange }: Props) {
  const [playing, setPlaying] = useState(false);
  const [currentCh, setCurrentCh] = useState<number | null>(null);
  const [speed, setSpeed] = useState(0.9);
  const [progress, setProgress] = useState(0);
  const [show, setShow] = useState(false);
  const [content, setContent] = useState('');
  const [contentLoaded, setContentLoaded] = useState(false);
  const utteranceRef = useRef<SpeechSynthesisUtterance | null>(null);
  const [paused, setPaused] = useState(false);

  const writable = chapters.filter(c => c.word_count > 0);

  const loadAndPlay = useCallback(async (chNum: number) => {
    if (!('speechSynthesis' in window)) {
      toast.error('浏览器不支持语音朗读');
      return;
    }
    speechSynthesis.cancel();
    setContentLoaded(false);
    try {
      const r = await fetch(`/api/novels/${novelId}/chapters/${chNum}`);
      const d = await r.json();
      const text = (d.content || '').replace(/[#*\->\_]/g, '').replace(/[「」]/g, '"');
      setContent(text);
      setCurrentCh(chNum);
      setContentLoaded(true);
      onChapterChange?.(chNum);
    } catch {
      toast.error('加载章节失败');
    }
  }, [novelId, onChapterChange]);

  // Pick best available Chinese voice
  function getBestVoice(): SpeechSynthesisVoice | null {
    const voices = speechSynthesis.getVoices();
    // Prefer Chinese voices in this order
    const preferred = ['Tingting', 'Sinji', 'Meijia', 'Yue', 'Hanhan', 'Zhiwei'];
    for (const name of preferred) {
      const v = voices.find(v => v.name.includes(name) && v.lang.startsWith('zh'));
      if (v) return v;
    }
    // Fallback: any Chinese voice
    return voices.find(v => v.lang.startsWith('zh')) || null;
  }

  // Play when content loads
  useEffect(() => {
    if (!contentLoaded || !content) return;
    const utter = new SpeechSynthesisUtterance(content);
    utter.lang = 'zh-CN';
    utter.rate = speed;
    utter.pitch = 1.0;
    const bestVoice = getBestVoice();
    if (bestVoice) utter.voice = bestVoice;
    utter.onboundary = (e) => {
      if (e.charIndex !== undefined) {
        setProgress(Math.round((e.charIndex / content.length) * 100));
      }
    };
    utter.onend = () => {
      setProgress(100);
      // Auto-play next chapter
      if (currentCh) {
        const idx = writable.findIndex(c => c.number === currentCh);
        const next = writable[idx + 1];
        if (next) {
          toast.info(`正在加载第${next.number}章...`, { duration: 1500 });
          setTimeout(() => loadAndPlay(next.number), 800);
        } else {
          setPlaying(false);
          toast.success('全书播放完毕');
        }
      }
    };
    utter.onerror = () => {
      setPlaying(false);
    };
    utteranceRef.current = utter;
    speechSynthesis.speak(utter);
    setPlaying(true);
    setPaused(false);
  }, [contentLoaded, content, speed, currentCh]);

  function togglePause() {
    if (paused) {
      speechSynthesis.resume();
      setPaused(false);
    } else {
      speechSynthesis.pause();
      setPaused(true);
    }
  }

  function stop() {
    speechSynthesis.cancel();
    setPlaying(false);
    setPaused(false);
    setProgress(0);
  }

  function skipChapter(dir: 1 | -1) {
    if (!currentCh) return;
    const idx = writable.findIndex(c => c.number === currentCh);
    const target = writable[idx + dir];
    if (target) loadAndPlay(target.number);
  }

  if (!show) {
    return (
      <button onClick={() => setShow(true)}
        className="text-[11px] text-ink-muted hover:text-accent px-2 py-1 rounded border border-border hover:border-accent/30 transition-colors">
        🎧 听书
      </button>
    );
  }

  return (
    <div className="fixed bottom-24 right-8 z-40 bg-card border border-border rounded-xl shadow-xl p-3 w-[280px] animate-[fadeSlideIn_0.2s_ease-out]">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-semibold text-ink">🎧 有声书</span>
        <button onClick={() => { stop(); setShow(false); }}
          className="text-xs text-ink-muted hover:text-ink">✕</button>
      </div>

      {/* Chapter selector */}
      <div className="mb-2">
        <select value={currentCh || ''} onChange={e => { const n = parseInt(e.target.value); if (n) loadAndPlay(n); }}
          className="w-full text-[10px] rounded border border-input bg-card px-2 py-1">
          <option value="">选择章节</option>
          {writable.map(c => (
            <option key={c.number} value={c.number}>第{c.number}章 {c.title}</option>
          ))}
        </select>
      </div>

      {/* Progress bar */}
      {playing && (
        <div className="mb-2">
          <div className="h-1 bg-border rounded-full overflow-hidden">
            <div className="h-full bg-accent rounded-full transition-all duration-300" style={{ width: `${progress}%` }} />
          </div>
          <div className="text-[9px] text-ink-subtle text-right mt-0.5">{progress}%</div>
        </div>
      )}

      {/* Controls */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1">
          <button onClick={() => skipChapter(-1)} disabled={!currentCh || !writable.find(c => c.number === currentCh)}
            className="text-xs p-1 text-ink-muted hover:text-ink disabled:opacity-30">⏮</button>
          {playing ? (
            <button onClick={togglePause}
              className="text-lg p-1 text-accent hover:scale-110 transition-transform">
              {paused ? '▶' : '⏸'}
            </button>
          ) : (
            <button onClick={currentCh ? () => loadAndPlay(currentCh) : undefined}
              className="text-lg p-1 text-accent hover:scale-110 transition-transform">
              ▶
            </button>
          )}
          <button onClick={() => skipChapter(1)} disabled={!currentCh}
            className="text-xs p-1 text-ink-muted hover:text-ink disabled:opacity-30">⏭</button>
          <button onClick={stop} className="text-xs p-1 text-red-400 hover:text-red-600">⏹</button>
        </div>

        {/* Speed control */}
        <div className="flex items-center gap-0.5">
          {[0.7, 0.9, 1.1, 1.4].map(s => (
            <button key={s} onClick={() => setSpeed(s)}
              className={`text-[9px] px-1 py-0.5 rounded ${speed === s ? 'bg-accent text-white' : 'text-ink-muted hover:text-ink'}`}>
              {s}x
            </button>
          ))}
        </div>
      </div>

      {/* Current chapter info */}
      {currentCh && (
        <p className="text-[9px] text-ink-subtle mt-2 truncate">
          正在播放：第{currentCh}章 {writable.find(c => c.number === currentCh)?.title || ''}
        </p>
      )}
    </div>
  );
}
