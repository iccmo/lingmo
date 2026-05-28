import { useState, useEffect, useRef, useCallback } from 'react';
import { toast } from 'sonner';

interface Props {
  novelId: string;
  chapters: { number: number; title: string }[];
}

interface ProduceStatus {
  status: string;
  message: string;
  progress: number;
}

interface ShotInfo {
  shot_id: string;
  duration_sec: number;
  start_time: number;
  subject: string;
  image_path: string;
  shot_type: string;
  emotion: string;
}

const STEPS = [
  { key: 'image', label: '画面', icon: '🎨' },
  { key: 'voice', label: '配音', icon: '🎙' },
  { key: 'music', label: '配乐', icon: '🎵' },
  { key: 'compose', label: '合成', icon: '🎬' },
];

export function ProducePanel({ novelId, chapters }: Props) {
  const [chapterNum, setChapterNum] = useState(chapters.length > 0 ? chapters[0].number : 1);
  const [producing, setProducing] = useState(false);
  const [status, setStatus] = useState<ProduceStatus | null>(null);
  const [videoUrl, setVideoUrl] = useState<string | null>(null);
  const [shots, setShots] = useState<ShotInfo[]>([]);
  const videoRef = useRef<HTMLVideoElement>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const [batchStart, setBatchStart] = useState(1);
  const [batchEnd, setBatchEnd] = useState(Math.min(chapters.length, 3));
  const [batchMode, setBatchMode] = useState(false);

  // Cleanup polling on unmount
  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  const fetchShots = useCallback(async (chNum: number) => {
    try {
      const res = await fetch(`/api/novels/${novelId}/chapters/${chNum}/shots`);
      if (res.ok) {
        const data = await res.json();
        setShots(data.shots || []);
      }
    } catch {
      setShots([]);
    }
  }, [novelId]);

  const pollStatus = useCallback(() => {
    if (pollRef.current) clearInterval(pollRef.current);
    pollRef.current = setInterval(async () => {
      try {
        const res = await fetch(`/api/novels/${novelId}/generate/status`);
        if (res.ok) {
          const s: ProduceStatus = await res.json();
          setStatus(s);
          if (s.status === 'idle' || s.status === 'error') {
            if (pollRef.current) clearInterval(pollRef.current);
            setProducing(false);
            if (s.status === 'idle') {
              toast.success(s.message || '制片完成');
              setVideoUrl(`/data/video/${novelId}/ch${String(chapterNum).padStart(3, '0')}_video.mp4`);
              fetchShots(chapterNum);
            } else {
              toast.error(s.message || '制片失败');
            }
          }
        }
      } catch {
        // silent
      }
    }, 2000);
  }, [novelId, chapterNum, fetchShots]);

  const handleProduce = async () => {
    setProducing(true);
    setVideoUrl(null);
    setStatus({ status: 'producing', message: '启动中...', progress: 0 });
    try {
      const res = await fetch(`/api/novels/${novelId}/chapters/${chapterNum}/produce`, { method: 'POST' });
      if (res.ok) {
        toast.success('制片已启动');
        pollStatus();
      } else {
        const err = await res.json();
        toast.error(err.detail || '启动失败');
        setProducing(false);
      }
    } catch {
      toast.error('请求失败');
      setProducing(false);
    }
  };

  const handleBatchProduce = async () => {
    setProducing(true);
    setVideoUrl(null);
    setStatus({ status: 'batch_producing', message: '批量制片启动中...', progress: 0 });
    try {
      const res = await fetch(
        `/api/novels/${novelId}/produce/batch?start_chapter=${batchStart}&end_chapter=${batchEnd}`,
        { method: 'POST' },
      );
      if (res.ok) {
        toast.success('批量制片已启动');
        pollStatus();
      } else {
        const err = await res.json();
        toast.error(err.detail || '启动失败');
        setProducing(false);
      }
    } catch {
      toast.error('请求失败');
      setProducing(false);
    }
  };

  // Determine current step from status message
  const currentStep = (() => {
    if (!status) return -1;
    const msg = status.message || '';
    if (msg.includes('画面') || msg.includes('1/4')) return 0;
    if (msg.includes('配音') || msg.includes('2/4')) return 1;
    if (msg.includes('配乐') || msg.includes('3/4')) return 2;
    if (msg.includes('合成') || msg.includes('4/4')) return 3;
    if (status.status === 'idle') return 4;
    return producing ? 0 : -1;
  })();

  return (
    <div className="space-y-4">
      {/* Controls */}
      <div className="flex items-center gap-3 flex-wrap">
        <select
          value={chapterNum}
          onChange={e => setChapterNum(Number(e.target.value))}
          disabled={producing}
          className="px-2 py-1.5 text-xs border border-border rounded-md bg-card text-ink disabled:opacity-50"
        >
          {chapters.map(ch => (
            <option key={ch.number} value={ch.number}>
              第{ch.number}章 {ch.title}
            </option>
          ))}
        </select>
        <button
          onClick={handleProduce}
          disabled={producing}
          className="px-4 py-1.5 text-xs font-medium bg-accent text-white rounded-md hover:bg-accent/80 disabled:opacity-50 transition flex items-center gap-1.5"
        >
          {producing && <span className="w-3 h-3 border-2 border-white/30 border-t-white rounded-full animate-spin" />}
          {producing ? '制片中...' : '一键制片'}
        </button>
        <button
          onClick={() => setBatchMode(!batchMode)}
          disabled={producing}
          className="px-3 py-1.5 text-xs font-medium border border-border rounded-md text-ink hover:bg-card disabled:opacity-50 transition"
        >
          {batchMode ? '收起批量' : '批量制片'}
        </button>
      </div>

      {/* Batch controls */}
      {batchMode && (
        <div className="flex items-center gap-3 p-3 bg-card border border-border rounded-lg">
          <span className="text-xs text-ink-muted">章节范围：</span>
          <select
            value={batchStart}
            onChange={e => setBatchStart(Number(e.target.value))}
            disabled={producing}
            className="px-2 py-1 text-xs border border-border rounded bg-paper text-ink"
          >
            {chapters.map(ch => (
              <option key={ch.number} value={ch.number}>第{ch.number}章</option>
            ))}
          </select>
          <span className="text-xs text-ink-muted">至</span>
          <select
            value={batchEnd}
            onChange={e => setBatchEnd(Number(e.target.value))}
            disabled={producing}
            className="px-2 py-1 text-xs border border-border rounded bg-paper text-ink"
          >
            {chapters.filter(ch => ch.number >= batchStart).map(ch => (
              <option key={ch.number} value={ch.number}>第{ch.number}章</option>
            ))}
          </select>
          <button
            onClick={handleBatchProduce}
            disabled={producing}
            className="px-3 py-1 text-xs font-medium bg-accent text-white rounded-md hover:bg-accent/80 disabled:opacity-50 transition"
          >
            {producing ? '制片中...' : `开始批量 (${batchEnd - batchStart + 1}章)`}
          </button>
        </div>
      )}

      {/* Step progress */}
      {(producing || status?.status === 'idle') && (
        <div className="space-y-2">
          <div className="flex items-center gap-1">
            {STEPS.map((step, i) => (
              <div key={step.key} className="flex items-center gap-1 flex-1">
                <div className={`flex items-center gap-1.5 px-2 py-1.5 rounded text-xs font-medium transition-all ${
                  i < currentStep
                    ? 'bg-emerald-500/10 text-emerald-600 border border-emerald-500/20'
                    : i === currentStep
                      ? 'bg-accent/10 text-accent border border-accent/20 animate-pulse'
                      : 'bg-card text-ink-muted border border-border'
                }`}>
                  <span>{step.icon}</span>
                  <span className="hidden sm:inline">{step.label}</span>
                </div>
                {i < STEPS.length - 1 && (
                  <div className={`h-px flex-1 ${i < currentStep ? 'bg-emerald-400' : 'bg-border'}`} />
                )}
              </div>
            ))}
          </div>
          {/* Progress bar */}
          {producing && (
            <div className="h-1 bg-border rounded-full overflow-hidden">
              <div
                className="h-full bg-accent transition-all duration-500 ease-out rounded-full"
                style={{ width: `${Math.max(5, (currentStep / STEPS.length) * 100)}%` }}
              />
            </div>
          )}
        </div>
      )}

      {/* Status message */}
      {status && producing && (
        <div className="flex items-center justify-center gap-2 py-2">
          <div className="w-1.5 h-1.5 rounded-full bg-accent animate-pulse" />
          <span className="text-xs text-ink-muted">{status.message}</span>
        </div>
      )}

      {/* Error state with retry */}
      {status?.status === 'error' && !producing && (
        <div className="flex items-center justify-center gap-3 py-3 bg-red-500/5 border border-red-500/10 rounded-lg">
          <span className="text-xs text-red-500">{status.message}</span>
          <button
            onClick={handleProduce}
            className="px-2 py-1 text-[10px] font-medium text-red-600 border border-red-500/20 rounded hover:bg-red-500/10 transition"
          >
            重试
          </button>
        </div>
      )}

      {/* Video preview */}
      {videoUrl && !producing && (
        <div className="border border-border rounded-lg overflow-hidden bg-black">
          <video
            ref={videoRef}
            controls
            className="w-full max-h-[500px]"
            src={videoUrl}
          >
            您的浏览器不支持视频播放
          </video>
          {/* Shot thumbnail timeline */}
          {shots.length > 0 && (
            <div className="flex gap-1 p-2 overflow-x-auto bg-zinc-900 scrollbar-thin">
              {shots.map(shot => (
                <button
                  key={shot.shot_id}
                  onClick={() => {
                    if (videoRef.current) {
                      videoRef.current.currentTime = shot.start_time;
                      videoRef.current.play().catch(() => {});
                    }
                  }}
                  className="shrink-0 group relative rounded overflow-hidden border border-zinc-700 hover:border-accent transition-colors"
                  style={{ width: 64, height: 80 }}
                  title={`${shot.shot_id} (${shot.duration_sec}s) - ${shot.subject}`}
                >
                  {shot.image_path ? (
                    <img
                      src={`/${shot.image_path}`}
                      alt={shot.shot_id}
                      className="w-full h-full object-cover"
                      loading="lazy"
                    />
                  ) : (
                    <div className="w-full h-full bg-zinc-800 flex items-center justify-center text-[10px] text-zinc-500">
                      {shot.shot_type === 'close-up' ? '🔍' : shot.shot_type === 'wide' ? '🏞' : '📹'}
                    </div>
                  )}
                  <div className="absolute bottom-0 inset-x-0 bg-black/70 px-1 py-0.5">
                    <span className="text-[8px] text-white font-mono">{shot.shot_id}</span>
                    <span className="text-[8px] text-zinc-400 ml-0.5">{shot.duration_sec}s</span>
                  </div>
                </button>
              ))}
            </div>
          )}
          <div className="flex items-center justify-between p-2 bg-card">
            <span className="text-xs text-ink-muted">第{chapterNum}章视频</span>
            <div className="flex items-center gap-2">
              {shots.length > 0 && (
                <span className="text-[10px] text-ink-subtle">{shots.length} 个镜头</span>
              )}
              <a
                href={videoUrl}
                download
                className="text-[10px] text-accent hover:underline"
              >
                下载视频
              </a>
            </div>
          </div>
        </div>
      )}

      {/* Empty state */}
      {!producing && !videoUrl && status?.status !== 'error' && (
        <div className="text-center py-10">
          <div className="text-3xl mb-3">🎬</div>
          <p className="text-sm text-ink-muted">
            选择章节后点击"一键制片"
          </p>
          <p className="text-xs text-ink-subtle mt-1">
            自动生成画面 → 配音 → 配乐 → 合成视频
          </p>
          <p className="text-[10px] text-ink-subtle mt-2 opacity-60">
            需要先生成分镜脚本
          </p>
        </div>
      )}
    </div>
  );
}
