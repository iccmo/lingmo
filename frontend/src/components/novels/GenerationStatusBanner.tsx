import { useState, useEffect } from 'react';
import { CheckCircle2, XCircle, Loader2, Clock, Eye, RefreshCw } from 'lucide-react';
import { isActiveGenerationStatus, isCompletedGenerationStatus, isFailedGenerationStatus } from 'src/lib/generation-status';

interface GenStatus {
  status: string;
  message: string;
  progress: number;
  overall?: number;
  grade?: string;
}

interface Props {
  genStatus: GenStatus | null;
  onViewChapter: () => void;
  onRetry: () => void;
}

/** 管道阶段中文映射 */
const STAGE_LABELS: Record<string, string> = {
  generating: '构思生成',
  reviewing: '定向修复',
  editing: '精修润色',
  judging: 'AI 评估',
  complete: '已完成',
  error: '生成失败',
  idle: '空闲',
};

/** 管道阶段到假名顺序 */
const STAGE_ORDER = ['generating', 'reviewing', 'editing', 'judging', 'complete'];

export function GenerationStatusBanner({ genStatus, onViewChapter, onRetry }: Props) {
  const [visible, setVisible] = useState(false);
  const [startTime] = useState(Date.now());
  const [elapsed, setElapsed] = useState(0);

  // Auto-show when genStatus appears, keep visible for completion/error
  useEffect(() => {
    if (genStatus && !visible) setVisible(true);
  }, [genStatus]);

  // Elapsed timer
  useEffect(() => {
    if (!isActiveGenerationStatus(genStatus)) return;
    const t = setInterval(() => setElapsed(Math.round((Date.now() - startTime) / 1000)), 1000);
    return () => clearInterval(t);
  }, [genStatus?.status, startTime]);

  if (!genStatus || !visible) return null;

  const { status, message, progress, overall, grade } = genStatus;
  const isDone = isCompletedGenerationStatus(genStatus);
  const isError = isFailedGenerationStatus(genStatus);
  const isRunning = isActiveGenerationStatus(genStatus);

  // Find current stage index
  const stageIdx = STAGE_ORDER.indexOf(status);

  return (
    <div className="mx-4 mt-3 mb-1">
      <div className={`
        rounded-xl border-2 px-4 py-3 shadow-lg transition-all duration-300
        ${isDone ? 'border-emerald-400/60 bg-emerald-50 dark:bg-emerald-950/30' : ''}
        ${isError ? 'border-red-400/60 bg-red-50 dark:bg-red-950/30' : ''}
        ${isRunning ? 'border-accent/30 bg-accent-soft/10 dark:bg-accent-soft/5' : ''}
      `}>
        {/* Header row */}
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            {isDone && <CheckCircle2 size={18} className="text-emerald-500" />}
            {isError && <XCircle size={18} className="text-red-500" />}
            {isRunning && <Loader2 size={18} className="text-accent animate-spin" />}
            <span className={`text-sm font-semibold ${
              isDone ? 'text-emerald-700 dark:text-emerald-300' :
              isError ? 'text-red-700 dark:text-red-300' :
              'text-ink'
            }`}>
              {isDone ? '生成完成' : isError ? '生成失败' : '正在生成...'}
            </span>
          </div>
          <div className="flex items-center gap-2">
            {isRunning && (
              <span className="text-xs text-ink-muted flex items-center gap-1">
                <Clock size={12} />
                {elapsed > 60 ? `${Math.floor(elapsed / 60)}分${elapsed % 60}秒` : `${elapsed}秒`}
              </span>
            )}
            {isDone && (
              <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${
                grade === 'A' ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300' :
                grade === 'B' ? 'bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300' :
                'bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300'
              }`}>
                Q:{grade || '?'} ({overall != null ? overall.toFixed(2) : '?'})
              </span>
            )}
            <button
              onClick={() => setVisible(false)}
              className="text-ink-subtle hover:text-ink text-xs px-1"
            >
              ✕
            </button>
          </div>
        </div>

        {/* Pipeline stages */}
        {isRunning && (
          <div className="flex items-center gap-1 mb-2">
            {STAGE_ORDER.map((stage) => {
              const idx = STAGE_ORDER.indexOf(stage);
              const currentIdx = stageIdx >= 0 ? stageIdx : 0;
              const isPast = idx < currentIdx;
              const isCurrent = idx === currentIdx;
              return (
                <div key={stage} className="flex items-center gap-1 flex-1 last:flex-[0.5]">
                  <div className={`
                    flex-1 h-1.5 rounded-full transition-all duration-500
                    ${isPast ? 'bg-emerald-400' : isCurrent ? 'bg-accent animate-pulse' : 'bg-border'}
                  `} />
                  {idx < STAGE_ORDER.length - 1 && (
                    <div className={`w-1 h-1 rounded-full ${isPast ? 'bg-emerald-400' : 'bg-border'}`} />
                  )}
                </div>
              );
            })}
            <span className="text-[10px] text-ink-muted shrink-0 ml-1">
              {STAGE_LABELS[status] || status}
            </span>
          </div>
        )}

        {/* Progress bar + message (running) */}
        {isRunning && (
          <>
            <div className="h-2 bg-border rounded-full overflow-hidden mb-1.5">
              <div
                className="h-full bg-gradient-to-r from-accent to-amber-400 rounded-full transition-all duration-700"
                style={{ width: `${progress}%` }}
              />
            </div>
            <p className="text-xs text-ink-muted leading-relaxed">{message}</p>
          </>
        )}

        {/* Done: quality message */}
        {isDone && overall != null && (
          <>
            <p className="text-xs text-ink-muted leading-relaxed mb-2">
              {message}
            </p>
            <button
              onClick={() => { onViewChapter(); setVisible(false); }}
              className="w-full py-2 rounded-lg bg-emerald-500 hover:bg-emerald-600 text-white text-sm font-medium
                flex items-center justify-center gap-1.5 transition-colors"
            >
              <Eye size={15} /> 查看新章节
            </button>
          </>
        )}

        {/* Error: show message + retry */}
        {isError && (
          <>
            <p className="text-xs text-red-600 dark:text-red-400 leading-relaxed mb-2">{message}</p>
            <button
              onClick={onRetry}
              className="w-full py-2 rounded-lg bg-red-500 hover:bg-red-600 text-white text-sm font-medium
                flex items-center justify-center gap-1.5 transition-colors"
            >
              <RefreshCw size={15} /> 重试
            </button>
          </>
        )}
      </div>
    </div>
  );
}
