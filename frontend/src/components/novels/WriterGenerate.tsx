import { Sparkles, ChevronDown, ChevronUp, Swords, Heart, RefreshCw, Coffee, Search, Telescope, Zap } from 'lucide-react';

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

const DIRECTION_PRESETS = [
  { icon: Swords, label: '打斗', hint: '战斗场面，动作描写，招式对决', color: 'hover:bg-destructive-soft/30 hover:border-destructive/30' },
  { icon: Heart, label: '感情', hint: '情感互动，关系发展，内心独白', color: 'hover:bg-pink-100/30 hover:border-pink-200/50' },
  { icon: RefreshCw, label: '反转', hint: '剧情反转，出人意料，打破常规', color: 'hover:bg-purple-100 dark:bg-purple-900/30 hover:border-purple-200/50' },
  { icon: Coffee, label: '日常', hint: '日常互动，角色塑造，氛围营造', color: 'hover:bg-teal-100/30 hover:border-teal-200/50' },
  { icon: Search, label: '悬疑', hint: '悬疑氛围，线索推进，谜题展开', color: 'hover:bg-warn-soft/30 hover:border-warn/30' },
  { icon: Telescope, label: '伏笔', hint: '埋下伏笔，回收旧线，前后呼应', color: 'hover:bg-blue-100/30 hover:border-blue-200/50' },
  { icon: Zap, label: '高潮', hint: '高燃剧情，极限爆发，情绪顶点', color: 'hover:bg-accent-soft/30 hover:border-accent/30' },
];

const IDLE_STATUSES = new Set(['complete', 'error', 'idle']);

export function WriterGenerate({
  chapterCount, onGenerate, genStatus,
  direction, setDirection, showDirection, setShowDirection,
}: Props) {
  const isGenerating = genStatus && !IDLE_STATUSES.has(genStatus.status);

  function addDirection(hint: string) {
    const current = direction.trim();
    setDirection(current ? `${current}；${hint}` : hint);
    if (!showDirection) setShowDirection(true);
  }

  return (
    <div className="shrink-0 border-t border-border bg-card/80 backdrop-blur-sm px-4 py-3">
      {/* Direction panel */}
      {showDirection && (
        <div className="mb-3 max-w-xl mx-auto space-y-2 animate-[fadeSlideIn_0.15s_ease-out]">
          {/* Quick preset chips */}
          <div className="flex flex-wrap gap-1.5">
            {DIRECTION_PRESETS.map(p => (
              <button key={p.label} type="button"
                onClick={() => addDirection(p.hint)}
                title={p.hint}
                className={`inline-flex items-center gap-1 text-[11px] px-2 py-1 rounded-md border border-border bg-paper text-ink-muted transition-colors ${p.color}`}>
                <p.icon size={11} />
                {p.label}
              </button>
            ))}
          </div>
          {/* Direction textarea */}
          <div className="flex gap-2">
            <textarea
              value={direction}
              onChange={(e) => setDirection(e.target.value)}
              placeholder="输入写作方向，或点击上方标签快速添加…"
              rows={2}
              className="flex-1 text-xs rounded-md border border-input bg-paper px-3 py-2 resize-none outline-none focus:ring-1 focus:ring-accent"
            />
            {direction && (
              <button onClick={() => setDirection('')} className="text-[10px] text-ink-muted hover:text-destructive shrink-0 self-start mt-1">
                清空
              </button>
            )}
          </div>
        </div>
      )}

      <div className="flex items-center gap-3">
        {/* Chapter counter */}
        <span className="tabular-nums text-xs text-ink-muted shrink-0 w-16 text-right">
          第{chapterCount + 1}章
        </span>

        {/* Center: generate button or progress */}
        <div className="flex-1 flex items-center justify-center gap-2 min-w-0">
          {isGenerating ? (
            <div className="flex items-center gap-3 flex-1 max-w-lg">
              <div className="flex-1 h-2 bg-border rounded-full overflow-hidden">
                <div className="h-full bg-gradient-to-r from-accent to-amber-400 rounded-full transition-all duration-700"
                  style={{ width: `${genStatus!.progress}%` }} />
              </div>
              <span className="text-xs text-ink-muted whitespace-nowrap shrink-0">{genStatus!.message}</span>
            </div>
          ) : (
            <div className="flex items-center gap-2">
              <button onClick={onGenerate}
                className="bg-accent text-white rounded-xl shadow-lg px-6 py-2 active:scale-95 transition-transform font-medium text-sm flex items-center gap-1.5">
                <Sparkles size={14} /> 生成下一章
              </button>
              <button onClick={() => setShowDirection(!showDirection)}
                className="relative text-ink-muted hover:text-ink transition-colors p-1 rounded-md hover:bg-surface"
                title={showDirection ? '收起方向面板' : '展开方向面板'}>
                {showDirection ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                {!showDirection && direction && (
                  <span className="absolute -top-1 -right-1 w-2 h-2 bg-accent rounded-full" />
                )}
              </button>
            </div>
          )}
        </div>

        {/* Right: estimated time / word goal */}
        <div className="shrink-0 w-16 text-right">
          {isGenerating ? (
            <span className="text-[10px] text-ink-subtle">约5-10分钟</span>
          ) : (
            <span className="text-[10px] text-ink-subtle">目标2500字</span>
          )}
        </div>
      </div>
    </div>
  );
}
