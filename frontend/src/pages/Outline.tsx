import { useEffect, useState, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Button } from 'src/components/ui/button';
import { Input } from 'src/components/ui/input';
import { Textarea } from 'src/components/ui/textarea';
import { Card, CardContent } from 'src/components/ui/card';
import { Badge } from 'src/components/ui/badge';
import { toast } from 'sonner';

interface OutlineItem {
  number: number;
  title: string;
  summary: string;
}

interface ChapterRef {
  number: number;
  title: string;
  summary: string;
}

interface OutlineData {
  outline: OutlineItem[];
  recent_chapters: ChapterRef[];
  next_number: number;
}

export function Outline() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [data, setData] = useState<OutlineData | null>(null);
  const [loading, setLoading] = useState(true);
  const [items, setItems] = useState<OutlineItem[]>([]);
  const [form, setForm] = useState({ title: '', summary: '' });

  const loadData = useCallback(async () => {
    if (!id) return;
    try {
      const r = await fetch(`/api/novels/${id}/outline`);
      const d: OutlineData = await r.json();
      setData(d);
      setItems(d.outline || []);
    } catch { toast.error('加载大纲失败'); }
    finally { setLoading(false); }
  }, [id]);

  useEffect(() => { setLoading(true); loadData(); }, [loadData]);

  async function saveAll() {
    if (!id) return;
    try {
      await fetch(`/api/novels/${id}/outline`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ items }),
      });
      toast.success('大纲已保存');
      loadData();
    } catch { toast.error('保存失败'); }
  }

  function addItem() {
    if (!form.title.trim()) { toast.error('请输入章节标题'); return; }
    const nextNum = items.length > 0 ? Math.max(...items.map(i => i.number)) + 1 : (data?.next_number || 1);
    setItems([...items, { number: nextNum, title: form.title.trim(), summary: form.summary.trim() }]);
    setForm({ title: '', summary: '' });
  }

  function updateItem(idx: number, field: string, value: string) {
    const next = [...items];
    next[idx] = { ...next[idx], [field]: value };
    setItems(next);
  }

  function moveItem(idx: number, dir: -1 | 1) {
    const target = idx + dir;
    if (target < 0 || target >= items.length) return;
    const next = [...items];
    [next[idx], next[target]] = [next[target], next[idx]];
    setItems(next);
  }

  function removeItem(idx: number) {
    setItems(items.filter((_, i) => i !== idx));
  }


  if (loading) {
    return <div className="space-y-4 p-8"><div className="skeleton h-6 w-24" /><div className="skeleton h-8 w-48" /></div>;
  }

  return (
    <div className="max-w-[720px] page-enter">
      <button onClick={() => navigate(`/novels/${id}`)} className="text-xs text-ink-muted hover:text-ink mb-2 block">
        ← 返回小说详情
      </button>
      <h1 className="font-heading text-[28px] font-semibold text-ink leading-tight mb-1">章节大纲</h1>
      <p className="text-sm text-ink-muted mb-4">规划后续章节，AI 生成时将参考大纲方向</p>

      {/* Recent Chapters Context */}
      {data?.recent_chapters && data.recent_chapters.length > 0 && (
        <Card className="mb-5 border-border bg-muted/30">
          <CardContent className="p-4">
            <div className="flex items-center gap-2 mb-2">
              <Badge variant="outline" className="text-xs">最近章节</Badge>
            </div>
            <div className="space-y-1.5">
              {data.recent_chapters.map(c => (
                <div key={c.number} className="flex items-start gap-3 text-sm">
                  <span className="text-ink-subtle shrink-0 w-14 text-right">第{c.number}章</span>
                  <span className="text-ink font-medium">{c.title}</span>
                  {c.summary && <span className="text-ink-muted truncate hidden sm:inline">— {c.summary}</span>}
                </div>
              ))}
              <div className="mt-2 pt-2 border-t border-border">
                <span className="text-xs text-ink-muted">下一章编号：</span>
                <Badge className="ml-1 text-xs bg-accent text-primary-foreground">{data.next_number}</Badge>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Add Outline Item */}
      <Card className="mb-4 border-dashed border-accent/40 hover:border-accent/70 transition-colors">
        <CardContent className="p-4">
          <p className="text-xs font-semibold text-ink-muted uppercase tracking-wide mb-3">添加大纲条目</p>
          <div className="flex gap-3 mb-3 items-start flex-wrap sm:flex-nowrap">
            <div className="flex-1 min-w-0">
              <Input
                placeholder="章节标题，如：秘境奇遇"
                value={form.title}
                onChange={e => setForm({ ...form, title: e.target.value })}
                onKeyDown={e => e.key === 'Enter' && addItem()}
                className="text-sm"
              />
            </div>
            <div className="flex-[2] min-w-0">
              <Textarea
                placeholder="本章概要，如：主角在秘境中发现上古丹方，却遭遇守护兽..."
                value={form.summary}
                onChange={e => setForm({ ...form, summary: e.target.value })}
                rows={2}
                className="text-sm"
              />
            </div>
            <div className="shrink-0 pt-0.5">
              <Button size="sm" className="bg-accent hover:bg-accent-hover" onClick={addItem}>添加</Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Outline List — timeline style */}
      {items.length === 0 ? (
        <div className="text-center py-16">
          <p className="text-ink-muted text-sm mb-2">暂无大纲条目</p>
          <p className="text-ink-subtle text-xs">在上方添加章节标题和概要，AI 生成时将参考这些方向</p>
        </div>
      ) : (
        <>
          <div className="relative pl-8 mb-4">
            {/* Timeline line */}
            <div className="absolute left-[19px] top-3 bottom-3 w-0.5 bg-border rounded" />
            {items.map((item, i) => {
              const generated = data?.recent_chapters?.some(c => c.number === item.number);
              return (
              <div key={i} className="relative mb-3 last:mb-0 group">
                {/* Timeline dot */}
                <div className={`absolute -left-8 top-3 w-4 h-4 rounded-full border-2 transition-all ${
                  generated
                    ? 'bg-emerald-500 border-emerald-500'
                    : 'bg-card border-accent group-hover:scale-125'
                }`}>
                  {generated && <span className="absolute inset-0 flex items-center justify-center text-[8px] text-white">✓</span>}
                </div>

                <Card className={`border-border transition-all hover:shadow-sm ${
                  generated ? 'opacity-70' : ''
                }`}>
                  <CardContent className="p-3">
                    <div className="flex gap-3 items-start">
                      <div className={`shrink-0 w-10 h-10 rounded-full flex items-center justify-center text-xs font-bold ${
                        generated
                          ? 'bg-emerald-50 text-emerald-600 dark:bg-emerald-900/30 dark:text-emerald-400'
                          : 'bg-accent-soft text-accent'
                      }`}>
                        {item.number}
                      </div>
                      <div className="flex-1 min-w-0 space-y-2">
                        <Input
                          value={item.title}
                          onChange={e => updateItem(i, 'title', e.target.value)}
                          placeholder="章节标题"
                          className="text-sm font-medium border-0 border-b border-transparent hover:border-border focus:border-accent rounded-none px-0"
                        />
                        <Textarea
                          value={item.summary}
                          onChange={e => updateItem(i, 'summary', e.target.value)}
                          placeholder="本章概要..."
                          rows={1}
                          className="text-xs border-0 border-b border-transparent hover:border-border focus:border-accent rounded-none px-0 resize-none min-h-0"
                        />
                      </div>
                      <div className="shrink-0 flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity">
                        {generated && <Badge className="text-[9px] bg-emerald-50 dark:bg-emerald-950/30 text-emerald-600 dark:text-emerald-400 border-emerald-200 dark:border-emerald-800">已生成</Badge>}
                        <button className="text-xs h-7 px-2 text-ink-subtle hover:text-ink transition-colors"
                          onClick={() => moveItem(i, -1)} disabled={i === 0}>↑</button>
                        <button className="text-xs h-7 px-2 text-ink-subtle hover:text-ink transition-colors"
                          onClick={() => moveItem(i, 1)} disabled={i === items.length - 1}>↓</button>
                        <button className="text-xs h-7 px-2 text-red-400 hover:text-red-600 dark:hover:text-red-400 transition-colors"
                          onClick={() => removeItem(i)}>×</button>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              </div>
            );
          })}
          </div>

          {/* Stats + save */}
          <div className="flex items-center gap-4 flex-wrap">
            <button
              className="px-5 py-2.5 rounded-lg bg-accent text-white hover:bg-accent-hover transition-colors font-medium text-sm"
              onClick={saveAll}>💾 保存大纲</button>
            <span className="text-xs text-ink-muted">
              {items.length} 条待规划
              {data?.recent_chapters && (
                <span className="ml-2">
                  · {items.filter(i => data.recent_chapters?.some(c => c.number === i.number)).length} 条已生成
                </span>
              )}
            </span>
            <span className="text-xs text-ink-subtle ml-auto">
              AI 生成时将参考大纲方向，写完自动跳过已有章节
            </span>
          </div>
        </>
      )}
    </div>
  );
}
