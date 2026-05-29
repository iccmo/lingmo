import { useState, useEffect } from 'react';
import { toast } from 'sonner';

interface Props { novelId: string }

export function UnsaidPanel({ novelId }: Props) {
 const [entries, setEntries] = useState<Array<{ id: number; entry: string; created_at: string }>>([]);
 const [input, setInput] = useState('');
 const [loading, setLoading] = useState(true);

 useEffect(() => {
 fetch(`/api/novels/${novelId}/unsaid`)
 .then(r => r.json())
 .then(d => setEntries(d.entries || []))
 .catch(() => {})
 .finally(() => setLoading(false));
 }, [novelId]);

 async function addEntry() {
 const text = input.trim();
 if (!text || text.length < 2) return;
 const r = await fetch(`/api/novels/${novelId}/unsaid`, {
 method: 'POST',
 headers: { 'Content-Type': 'application/json' },
 body: JSON.stringify({ entry: text }),
 });
 if (r.ok) {
 const data = await r.json();
 if (data.ok) {
 setEntries(prev => [{ id: Date.now(), entry: text, created_at: new Date().toISOString() }, ...prev]);
 setInput('');
 toast.success('已添加隐藏设定');
 }
 } else {
 toast.error('添加失败');
 }
 }

 async function deleteEntry(id: number) {
 await fetch(`/api/novels/${novelId}/unsaid/${id}`, { method: 'DELETE' });
 setEntries(prev => prev.filter(e => e.id !== id));
 toast.success('已删除');
 }

 if (loading) return <div className="skeleton h-16 rounded-lg" />;

 return (
 <div className="space-y-3">
 <div className="flex items-center gap-2">
 <input
 value={input}
 onChange={e => setInput(e.target.value)}
 onKeyDown={e => { if (e.key === 'Enter') addEntry(); }}
 placeholder="写一个读者不知道但AI需要知道的真相…"
 className="flex-1 text-[11px] rounded border border-input bg-card px-2 py-1.5"
 />
 <button onClick={addEntry}
 className="text-[10px] px-3 py-1.5 rounded bg-accent text-white hover:bg-accent-hover transition-colors">
 添加
 </button>
 </div>

 {entries.length === 0 ? (
 <div className="text-center py-4">
 <p className="text-xs text-ink-subtle">暂无隐藏设定</p>
 <p className="text-[10px] text-ink-subtle mt-0.5">添加后，AI 生成时会知道这些真相但不在正文写出</p>
 </div>
 ) : (
 <div className="space-y-1.5 max-h-[300px] overflow-y-auto">
 {entries.map(e => (
 <div key={e.id} className="flex items-start gap-2 p-2 rounded bg-paper border border-border text-[10px] group">
 <span className="text-ink-muted shrink-0 mt-0.5">🔒</span>
 <span className="text-ink flex-1">{e.entry}</span>
 <button onClick={() => deleteEntry(e.id)}
 className="text-ink-subtle hover:text-destructive shrink-0 opacity-0 group-hover:opacity-100 transition-opacity">
 ×
 </button>
 </div>
 ))}
 </div>
 )}

 <p className="text-[9px] text-ink-subtle text-center">
 🧊 海明威冰山：AI 知道这些，但正文里不说。读者感觉到底下有东西。
 </p>
 </div>
 );
}
