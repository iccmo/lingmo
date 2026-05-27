import { useState } from 'react';

interface GenStatus {
  status: string;
  message: string;
  progress: number;
  overall?: number;
  grade?: string;
}

interface Props {
  chapterCount: number;
  onGenerate: () => void;
  genStatus: GenStatus | null;
  direction: string;
  setDirection: (d: string) => void;
  showDirection: boolean;
  setShowDirection: (v: boolean) => void;
}

const IDLE_STATUSES = new Set(['complete', 'error', 'idle']);

export function WriterGenerate({
  chapterCount,
  onGenerate,
  genStatus,
  direction,
  setDirection,
  showDirection,
  setShowDirection,
}: Props) {
  const isGenerating = genStatus && !IDLE_STATUSES.has(genStatus.status);

  return (
    <div className="shrink-0 border-t border-border bg-card/80 backdrop-blur-sm px-4 py-3">
      {/* Direction textarea — appears above the main bar */}
      {showDirection && (
        <div className="mb-3 max-w-lg mx-auto animate-fadeSlideIn">
          <textarea
            value={direction}
            onChange={(e) => setDirection(e.target.value)}
            placeholder="可选：给生成方向提示（留空则自动构思）..."
            rows={2}
            className="w-full text-xs rounded-md border border-input bg-paper px-3 py-2 resize-none outline-none focus:ring-1 focus:ring-accent"
          />
        </div>
      )}

      <div className="flex items-center gap-3">
        {/* Left: chapter counter */}
        <span className="tabular-nums text-xs text-ink-muted shrink-0">
          第{chapterCount}章/共{chapterCount}章
        </span>

        {/* Center: generate button + direction toggle, or progress bar */}
        <div className="flex-1 flex items-center justify-center gap-2 min-w-0">
          {isGenerating ? (
            <>
              <div className="flex-1 h-1.5 bg-border rounded-full overflow-hidden">
                <div
                  className="h-full bg-accent rounded-full transition-all duration-500"
                  style={{ width: `${genStatus!.progress}%` }}
                />
              </div>
              <span className="text-xs text-ink-muted whitespace-nowrap shrink-0">
                {genStatus!.message}
              </span>
            </>
          ) : (
            <>
              <button
                onClick={onGenerate}
                className="bg-accent text-white rounded-xl shadow-lg px-6 py-2 active:scale-95 transition-transform"
              >
                ✨ 生成下一章
              </button>
              <button
                onClick={() => setShowDirection(!showDirection)}
                className="text-ink-muted text-xs hover:text-ink transition-colors"
                aria-label={showDirection ? '收起方向提示' : '展开方向提示'}
              >
                {showDirection ? '▲' : '▼'}
              </button>
            </>
          )}
        </div>

        {/* Right: spacer for balance */}
        <div className="shrink-0 w-20" />
      </div>
    </div>
  );
}
