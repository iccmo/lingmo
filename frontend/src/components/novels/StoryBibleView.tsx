import { useState, useEffect } from 'react';
import { api } from 'src/lib/api';

interface StoryBibleData {
  characters: Array<{
    char_name: string; emotion: string; physical_state: string;
    goal: string; location: string; chapter_num: number;
  }>;
  foreshadowing: Array<{
    id: number; description: string; created_chapter: number;
    due_by_chapter: number | null; status: string;
  }>;
  timeline: Array<{
    chapter_num: number; absolute_time: string; event_summary: string;
  }>;
  consistency_log: Array<{
    chapter_num: number; check_type: string; severity: string;
    description: string; fix_suggestion: string;
  }>;
}

interface Props { novelId: string }

export function StoryBibleView({ novelId }: Props) {
  const [data, setData] = useState<StoryBibleData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`/api/novels/${novelId}/story-bible`)
      .then(r => r.json())
      .then(setData)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [novelId]);

  if (loading) return <div className="skeleton h-20 rounded-lg" />;
  if (!data) return <p className="text-xs text-ink-subtle py-4">暂无数据，生成新章后自动填充</p>;

  const hasData = data.characters.length > 0 || data.foreshadowing.length > 0 || data.timeline.length > 0;

  if (!hasData) {
    return (
      <div className="text-center py-8">
        <p className="text-2xl mb-2">📖</p>
        <p className="text-xs text-ink-subtle">故事圣经为空</p>
        <p className="text-[10px] text-ink-subtle mt-1">生成下一章后自动从正文提取</p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {/* Character States */}
      {data.characters.length > 0 && (
        <div>
          <h4 className="text-xs font-semibold text-ink mb-2">👤 角色状态</h4>
          <div className="space-y-1.5">
            {data.characters.slice(-10).reverse().map((c, i) => (
              <div key={i} className="p-2 rounded-lg bg-paper border border-border text-[10px]">
                <div className="flex items-center justify-between mb-0.5">
                  <span className="font-medium text-ink">{c.char_name}</span>
                  <span className="text-ink-subtle">Ch{c.chapter_num}</span>
                </div>
                <div className="text-ink-muted space-y-0.5">
                  {c.emotion && <span>情绪：{c.emotion}</span>}
                  {c.physical_state && <span className="ml-2">身体：{c.physical_state}</span>}
                  {c.location && <span className="ml-2">📍{c.location}</span>}
                </div>
                {c.goal && <div className="text-ink-subtle mt-0.5">目标：{c.goal}</div>}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Active Foreshadowing */}
      {data.foreshadowing.length > 0 && (
        <div>
          <h4 className="text-xs font-semibold text-ink mb-2">🔮 伏笔追踪</h4>
          <div className="space-y-1">
            {data.foreshadowing.map(f => (
              <div key={f.id} className={`p-1.5 rounded text-[10px] flex items-center justify-between ${
                f.status === 'overdue' ? 'bg-red-50 dark:bg-red-950/20 border border-red-200 dark:border-red-800' : 'bg-paper'
              }`}>
                <span className="text-ink truncate flex-1">{f.description}</span>
                <span className={`text-ink-subtle ml-2 shrink-0 ${
                  f.status === 'overdue' ? 'text-red-500' : ''
                }`}>
                  {f.status === 'overdue' ? '⚠️ 过期' : `Ch${f.created_chapter} → ${f.due_by_chapter || '?'}`}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Timeline */}
      {data.timeline.length > 0 && (
        <div>
          <h4 className="text-xs font-semibold text-ink mb-2">⏱ 时间线</h4>
          <div className="space-y-0.5">
            {data.timeline.slice(-5).reverse().map((t, i) => (
              <div key={i} className="flex items-center gap-2 text-[10px] py-0.5">
                <span className="text-ink-subtle w-8 shrink-0">Ch{t.chapter_num}</span>
                <span className="text-ink-muted w-16 shrink-0">{t.absolute_time || '?'}</span>
                <span className="text-ink truncate">{t.event_summary}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Consistency Issues */}
      {data.consistency_log.length > 0 && (
        <div>
          <h4 className="text-xs font-semibold text-ink mb-2">
            🛡 一致性校验
            {data.consistency_log.filter(c => c.severity === 'error').length > 0 &&
              <span className="text-red-500 ml-1">({data.consistency_log.filter(c => c.severity === 'error').length} 错误)</span>
            }
          </h4>
          <div className="space-y-1">
            {data.consistency_log.slice(0, 10).map((c, i) => (
              <div key={i} className={`p-1.5 rounded text-[10px] ${
                c.severity === 'error' ? 'bg-red-50 dark:bg-red-950/20 border border-red-200 dark:border-red-800'
                : c.severity === 'warning' ? 'bg-amber-50 dark:bg-amber-950/20 border border-amber-200 dark:border-amber-800'
                : 'bg-paper'
              }`}>
                <div className="flex items-center gap-1.5">
                  <span className={`font-medium ${
                    c.severity === 'error' ? 'text-red-500' : c.severity === 'warning' ? 'text-amber-500' : 'text-sky-500'
                  }`}>
                    {c.severity === 'error' ? '🔴' : c.severity === 'warning' ? '🟡' : '🔵'}
                  </span>
                  <span className="text-ink-subtle">{c.check_type}</span>
                  <span className="text-ink-subtle">Ch{c.chapter_num}</span>
                </div>
                <p className="text-ink mt-0.5">{c.description}</p>
                {c.fix_suggestion && <p className="text-ink-subtle mt-0.5">💡 {c.fix_suggestion}</p>}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
