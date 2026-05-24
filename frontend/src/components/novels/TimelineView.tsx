import { useEffect, useState } from 'react';
import type { ChapterMeta } from 'src/types';

interface TimelineEvent {
  chapterNum: number;
  chapterTitle: string;
  description: string;
  type: 'plot' | 'revelation' | 'cliffhanger' | 'other';
}

interface KeyEvent {
  event?: string;
  description?: string;
  type?: string;
  chapter?: number;
}

const EVENT_TYPE_COLORS: Record<string, { bg: string; dot: string; label: string }> = {
  plot: {
    bg: 'bg-blue-50 border-blue-200 dark:bg-blue-950/30 dark:border-blue-800',
    dot: 'bg-blue-500',
    label: '情节',
  },
  revelation: {
    bg: 'bg-amber-50 border-amber-200 dark:bg-amber-950/30 dark:border-amber-800',
    dot: 'bg-amber-500',
    label: '揭示',
  },
  cliffhanger: {
    bg: 'bg-red-50 border-red-200 dark:bg-red-950/30 dark:border-red-800',
    dot: 'bg-red-500',
    label: '悬念',
  },
  other: {
    bg: 'bg-gray-50 border-gray-200 dark:bg-gray-800/30 dark:border-gray-700',
    dot: 'bg-gray-400',
    label: '其他',
  },
};

function classifyEventType(event: KeyEvent, endingHook: string): 'plot' | 'revelation' | 'cliffhanger' | 'other' {
  const desc = (event.event || event.description || '').toLowerCase();
  const typeField = (event.type || '').toLowerCase();

  if (typeField.includes('plot') || desc.includes('战斗') || desc.includes('出发') || desc.includes('到达') || desc.includes('开始')) {
    return 'plot';
  }
  if (typeField.includes('revelation') || typeField.includes('revel') || desc.includes('发现') || desc.includes('揭示') || desc.includes('真相') || desc.includes('秘密')) {
    return 'revelation';
  }
  if (typeField.includes('cliffhanger') || typeField.includes('cliff') || desc.includes('悬念') || desc.includes('危机') || desc.includes('危险')) {
    return 'cliffhanger';
  }
  // Fallback: use ending_hook as cliffhanger
  if (endingHook && endingHook.trim()) {
    return 'cliffhanger';
  }
  return 'plot';
}

interface Props {
  chapters: ChapterMeta[];
  novelId: string;
}

export function TimelineView({ chapters, novelId }: Props) {
  const [events, setEvents] = useState<TimelineEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeFilters, setActiveFilters] = useState<Set<string>>(new Set(['plot', 'revelation', 'cliffhanger', 'other']));
  const [hoveredEvent, setHoveredEvent] = useState<number | null>(null);

  useEffect(() => {
    setLoading(true);
    const loadTimeline = async () => {
      const loadedEvents: TimelineEvent[] = [];
      const genChapters = chapters.filter(c => c.word_count > 0);

      for (const ch of genChapters) {
        try {
          const res = await fetch(`/api/novels/${novelId}/chapters/${ch.number}`);
          const data = await res.json();
          const keyEvents: KeyEvent[] = data.key_events || [];

          if (keyEvents.length > 0) {
            for (const event of keyEvents) {
              loadedEvents.push({
                chapterNum: ch.number,
                chapterTitle: ch.title,
                description: event.event || event.description || '(未命名事件)',
                type: classifyEventType(event, data.ending_hook || ''),
              });
            }
          } else {
            // Fallback: use chapter title + ending_hook
            loadedEvents.push({
              chapterNum: ch.number,
              chapterTitle: ch.title,
              description: ch.title || `第${ch.number}章`,
              type: data.ending_hook ? 'cliffhanger' : 'plot',
            });
          }
        } catch {
          // Skip chapters that fail to load
          loadedEvents.push({
            chapterNum: ch.number,
            chapterTitle: ch.title,
            description: ch.title || `第${ch.number}章`,
            type: ch.ending_hook ? 'cliffhanger' : 'plot',
          });
        }
      }

      setEvents(loadedEvents);
      setLoading(false);
    };

    loadTimeline();
  }, [chapters, novelId]);

  const toggleFilter = (type: string) => {
    setActiveFilters(prev => {
      const next = new Set(prev);
      if (next.has(type)) next.delete(type);
      else next.add(type);
      return next;
    });
  };

  const filteredEvents = events.filter(e => activeFilters.has(e.type));

  if (loading) {
    return (
      <div className="p-4">
        <div className="space-y-2">
          {[80, 60, 90, 40].map((w, i) => (
            <div key={i} className="skeleton h-4 rounded" style={{ width: `${w}%`, animationDelay: `${i * 0.1}s` }} />
          ))}
        </div>
      </div>
    );
  }

  if (events.length === 0) {
    return (
      <div className="text-center py-8 text-xs text-ink-muted">
        暂无时间线数据。生成章节后自动创建。
      </div>
    );
  }

  return (
    <div className="animate-[fadeSlideIn_0.2s_ease-out]">
      {/* Filter buttons */}
      <div className="flex items-center gap-2 mb-4 flex-wrap">
        <span className="text-[10px] text-ink-muted">筛选:</span>
        {Object.entries(EVENT_TYPE_COLORS).map(([key, { dot, label }]) => (
          <button
            key={key}
            onClick={() => toggleFilter(key)}
            className={`text-[10px] px-2 py-1 rounded-full border transition-colors flex items-center gap-1 ${
              activeFilters.has(key)
                ? 'border-border bg-card text-ink'
                : 'border-transparent bg-paper text-ink-subtle opacity-50'
            }`}
          >
            <span className={`w-2 h-2 rounded-full ${dot}`} />
            {label}
          </button>
        ))}
        <span className="text-[10px] text-ink-subtle ml-auto">
          {filteredEvents.length} 个事件
        </span>
      </div>

      {/* Horizontal timeline */}
      <div className="overflow-x-auto pb-4">
        <div className="flex items-start gap-0 min-w-max relative">
          {/* Timeline line */}
          <div className="absolute top-6 left-0 right-0 h-0.5 bg-border" />

          {filteredEvents.map((event, index) => {
            const colors = EVENT_TYPE_COLORS[event.type];
            const isHovered = hoveredEvent === index;

            return (
              <div
                key={index}
                className="relative flex flex-col items-center group"
                style={{ minWidth: '120px', maxWidth: '200px' }}
                onMouseEnter={() => setHoveredEvent(index)}
                onMouseLeave={() => setHoveredEvent(null)}
              >
                {/* Chapter label above dot */}
                <span className="text-[9px] text-ink-subtle mb-2 whitespace-nowrap tabular-nums">
                  Ch{event.chapterNum}
                </span>

                {/* Dot on timeline */}
                <div
                  className={`w-3 h-3 rounded-full border-2 border-card z-10 ${colors.dot} ring-2 ring-transparent transition-all ${
                    isHovered ? 'ring-accent/30 scale-125' : ''
                  }`}
                />

                {/* Event card below dot */}
                <div
                  className={`mt-3 p-2 rounded-lg border text-[10px] leading-relaxed transition-all ${
                    colors.bg
                  } ${
                    isHovered ? 'shadow-md scale-105 z-20' : ''
                  }`}
                >
                  <div className="font-medium text-ink mb-0.5 truncate max-w-[160px]">
                    {event.description.length > 30
                      ? event.description.slice(0, 30) + '...'
                      : event.description}
                  </div>
                  <span className="text-[9px] text-ink-subtle">{event.chapterTitle.slice(0, 20)}</span>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Legend */}
      <div className="flex items-center gap-4 mt-2 pt-2 border-t border-border text-[10px] text-ink-subtle">
        {Object.entries(EVENT_TYPE_COLORS).map(([key, { dot, label }]) => (
          <span key={key} className="flex items-center gap-1">
            <span className={`w-2 h-2 rounded-full ${dot}`} />
            {label}
          </span>
        ))}
      </div>
    </div>
  );
}
