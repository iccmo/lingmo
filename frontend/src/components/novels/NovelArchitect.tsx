import { useState, useEffect } from 'react';
import { toast } from 'sonner';
import type { ChapterMeta } from 'src/types';

interface Act {
  id: string; name: string; range: [number, number]; goal: string; status: 'planned' | 'writing' | 'done';
}
interface ArcMilestone { character: string; chapter: number; description: string; }
interface KeyBeat { chapter: number; event: string; type: 'hook' | 'climax' | 'reveal' | 'turning' | 'ending'; }

interface NovelPlan {
  acts: Act[];
  arcMilestones: ArcMilestone[];
  keyBeats: KeyBeat[];
  totalChapters: number;
}

function loadPlan(novelId: string): NovelPlan | null {
  try { return JSON.parse(localStorage.getItem(`novel-plan-${novelId}`) || 'null'); }
  catch { return null; }
}
function savePlan(novelId: string, plan: NovelPlan) {
  localStorage.setItem(`novel-plan-${novelId}`, JSON.stringify(plan));
}

/* ─── Hierarchical Context Builder ─── */
function buildHierarchicalContext(
  novelId: string,
  currentChapter: number,
  plan: NovelPlan | null,
  chapters?: ChapterMeta[],
): { level1: string; level2: string; level3: string } {
  // Level 1: Always in context (soul, main chars, core conflict)
  let level1 = '';
  try {
    const fp = JSON.parse(localStorage.getItem(`soul-fingerprint-${novelId}`) || 'null');
    if (fp?.answer) level1 += `【全书灵魂】${fp.answer}\n`;
    const chars = JSON.parse(localStorage.getItem(`characters-soul-${novelId}`) || '[]');
    if (chars.length > 0) {
      level1 += `【核心角色】${chars.map((c: any) => `${c.name}(${c.role})`).join('、')}\n`;
    }
    const laws = JSON.parse(localStorage.getItem(`world-laws-${novelId}`) || '{"laws":[]}');
    if (laws.laws?.length) {
      level1 += `【世界法则】${laws.laws.map((l: any) => l.rule).join('；')}\n`;
    }
  } catch {}

  // Level 2: Current act context
  let level2 = '';
  if (plan) {
    const currentAct = plan.acts.find(a => currentChapter >= a.range[0] && currentChapter <= a.range[1]);
    if (currentAct) {
      level2 = `【当前卷】${currentAct.name}（第${currentAct.range[0]}-${currentAct.range[1]}章）\n目标：${currentAct.goal}\n进度：第${currentChapter}章 / ${currentAct.range[1]}章`;
    }
    const upcomingBeats = plan.keyBeats.filter(b => b.chapter >= currentChapter && b.chapter <= currentChapter + 5);
    if (upcomingBeats.length > 0) {
      level2 += `\n【即将到来】${upcomingBeats.map(b => `第${b.chapter}章·${b.type}：${b.event}`).join('\n')}`;
    }
  }

  // Level 3: Recent chapters summary
  let level3 = '';
  if (chapters) {
    const recent = chapters.filter(c => c.word_count > 0).slice(-3);
    if (recent.length > 0) {
      level3 = `【前情】${recent.map(c => `第${c.number}章：${c.summary || c.title}`).join('\n')}`;
    }
  }

  return { level1, level2, level3 };
}

export function NovelArchitect({ novelId, chapters, totalChapters }: {
  novelId: string; chapters?: ChapterMeta[]; totalChapters: number;
  onContextReady?: (context: string) => void;
}) {
  const [plan, setPlan] = useState<NovelPlan | null>(() => loadPlan(novelId));
  const [editing, setEditing] = useState(false);
  const [newAct, setNewAct] = useState({ name: '', start: 1, end: 10, goal: '' });
  const [newBeat, setNewBeat] = useState({ chapter: 1, event: '', type: 'hook' as KeyBeat['type'] });
  const [showContext, setShowContext] = useState(false);

  // Auto-calc total chapters from last act
  useEffect(() => {
    if (!plan || plan.acts.length === 0) return;
    const lastAct = plan.acts[plan.acts.length - 1];
    const total = lastAct.range[1];
    if (plan.totalChapters !== total) {
      setPlan(prev => prev ? { ...prev, totalChapters: total } : null);
    }
  }, [plan?.acts]);

  // Save plan to localStorage (debounced)
  useEffect(() => {
    if (!plan) return;
    const timer = setTimeout(() => savePlan(novelId, plan), 500);
    return () => clearTimeout(timer);
  }, [plan, novelId]);

  const currentChapter = totalChapters + 1;
  const context = buildHierarchicalContext(novelId, currentChapter, plan, chapters);

  // Find upcoming beats within 3 chapters
  const upcomingBeats = (plan?.keyBeats || []).filter(b => b.chapter >= currentChapter && b.chapter <= currentChapter + 3);
  // Find current act
  const currentAct = plan?.acts.find(a => currentChapter >= a.range[0] && currentChapter <= a.range[1]);
  const actProgress = currentAct ? Math.round(((currentChapter - currentAct.range[0] + 1) / (currentAct.range[1] - currentAct.range[0] + 1)) * 100) : 0;

  function addAct() {
    if (!newAct.name.trim()) return;
    if (newAct.start < 1 || newAct.end < newAct.start) {
      toast.error('章节范围无效'); return;
    }
    const base = plan || { acts: [], arcMilestones: [], keyBeats: [], totalChapters: 100 };
    // Check for overlap
    const overlap = base.acts.find(a =>
      (newAct.start >= a.range[0] && newAct.start <= a.range[1]) ||
      (newAct.end >= a.range[0] && newAct.end <= a.range[1])
    );
    if (overlap) { toast.error(`与「${overlap.name}」章节范围重叠`); return; }
    setPlan({ ...base, acts: [...base.acts, { id: `act-${Date.now()}`, name: newAct.name, range: [newAct.start, newAct.end] as [number, number], goal: newAct.goal, status: 'planned' as const }] });
    setNewAct({ name: '', start: newAct.end + 1, end: newAct.end + 10, goal: '' });
    toast.success('卷已添加');
  }

  function addBeat() {
    if (!newBeat.event.trim()) return;
    setPlan(prev => {
      const base = prev || { acts: [], arcMilestones: [], keyBeats: [], totalChapters: 100 };
      return { ...base, keyBeats: [...base.keyBeats, { ...newBeat }].sort((a, b) => a.chapter - b.chapter) };
    });
    setNewBeat({ chapter: newBeat.chapter + 1, event: '', type: 'hook' });
    toast.success('关键情节点已添加');
  }

  function removeAct(id: string) { setPlan(prev => prev ? { ...prev, acts: prev.acts.filter(a => a.id !== id) } : null); }
  function removeBeat(idx: number) { setPlan(prev => prev ? { ...prev, keyBeats: prev.keyBeats.filter((_, i) => i !== idx) } : null); }

  const beatEmojis: Record<string, string> = { hook: '🎣', climax: '🔥', reveal: '💡', turning: '🔄', ending: '🏁' };

  return (
    <div className="p-4 bg-card border border-border rounded-xl">
      <div className="flex items-center justify-between mb-3">
        <div>
          <h3 className="font-heading text-base font-semibold text-ink">🏗️ 长篇架构</h3>
          <p className="text-[11px] text-ink-muted">
            {plan ? `${plan.acts.length} 卷 · ${plan.keyBeats.length} 个关键情节点` : '规划百万字小说的结构'}
          </p>
        </div>
        <button onClick={() => setEditing(!editing)}
          className={`text-xs px-3 py-1.5 rounded-lg border transition-colors ${editing ? 'bg-accent text-white border-accent' : 'border-border text-ink-muted hover:text-ink'}`}>
          {editing ? '完成' : plan ? '编辑' : '开始规划'}
        </button>
      </div>

      {/* Editing mode */}
      {editing && (
        <div className="space-y-4 mb-4 animate-[fadeSlideIn_0.2s_ease-out]">
          {/* Act planner */}
          <div className="p-3 rounded-lg bg-paper border border-border">
            <p className="text-[10px] font-semibold text-ink-muted uppercase tracking-wide mb-2">添加卷/篇章</p>
            <div className="grid grid-cols-4 gap-2 mb-2">
              <input value={newAct.name} onChange={e => setNewAct({ ...newAct, name: e.target.value })} placeholder="卷名" className="text-xs rounded border border-input bg-card px-2 py-1.5" />
              <input type="number" value={newAct.start} onChange={e => setNewAct({ ...newAct, start: Number(e.target.value) })} placeholder="起始章" className="text-xs rounded border border-input bg-card px-2 py-1.5" />
              <input type="number" value={newAct.end} onChange={e => setNewAct({ ...newAct, end: Number(e.target.value) })} placeholder="结束章" className="text-xs rounded border border-input bg-card px-2 py-1.5" />
              <button onClick={addAct} className="text-xs rounded bg-accent text-white hover:bg-accent-hover transition-colors">添加卷</button>
            </div>
            <input value={newAct.goal} onChange={e => setNewAct({ ...newAct, goal: e.target.value })} placeholder="本卷目标（如：林尘从复仇者转变为守护者）" className="w-full text-xs rounded border border-input bg-card px-2 py-1.5" />
          </div>

          {/* Beat planner */}
          <div className="p-3 rounded-lg bg-paper border border-border">
            <p className="text-[10px] font-semibold text-ink-muted uppercase tracking-wide mb-2">添加关键情节点</p>
            <div className="grid grid-cols-5 gap-2 mb-2">
              <input type="number" value={newBeat.chapter} onChange={e => setNewBeat({ ...newBeat, chapter: Number(e.target.value) })} placeholder="章节" className="text-xs rounded border border-input bg-card px-2 py-1.5" />
              <select value={newBeat.type} onChange={e => setNewBeat({ ...newBeat, type: e.target.value as KeyBeat['type'] })}
                className="text-xs rounded border border-input bg-card px-2 py-1.5">
                {Object.entries(beatEmojis).map(([k, v]) => <option key={k} value={k}>{v} {k}</option>)}
              </select>
              <input value={newBeat.event} onChange={e => setNewBeat({ ...newBeat, event: e.target.value })} placeholder="事件描述" className="col-span-2 text-xs rounded border border-input bg-card px-2 py-1.5" />
              <button onClick={addBeat} className="text-xs rounded bg-accent text-white hover:bg-accent-hover transition-colors">添加</button>
            </div>
          </div>
        </div>
      )}

      {/* Current status */}
      {plan && currentAct && (
        <div className="mb-3 p-3 rounded-lg bg-gradient-to-r from-accent-soft/20 to-transparent border border-accent/10">
          <div className="flex items-center justify-between text-xs">
            <span className="text-ink font-medium">{currentAct.name}</span>
            <span className="text-accent font-bold">{actProgress}%</span>
          </div>
          <div className="h-1.5 bg-border rounded-full mt-1 overflow-hidden">
            <div className="h-full bg-accent rounded-full transition-all" style={{ width: `${actProgress}%` }} />
          </div>
          <div className="flex justify-between text-[9px] text-ink-subtle mt-0.5">
            <span>第{currentAct.range[0]}章</span>
            <span>第{currentAct.range[1]}章</span>
          </div>
          {/* Beat warnings */}
          {upcomingBeats.length > 0 && (
            <div className="mt-2 flex gap-2 flex-wrap">
              {upcomingBeats.map((b, i) => (
                <span key={i} className="text-[10px] px-2 py-0.5 rounded-full bg-accent-soft/30 text-accent border border-accent/20">
                  ⚡ {b.chapter - currentChapter}章后：{beatEmojis[b.type]} {b.event.slice(0, 20)}
                </span>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Act timeline visualization */}
      {plan?.acts && plan.acts.length > 0 && (
        <div className="mb-3 space-y-1.5">
          {plan.acts.map((act, _i) => {
            const pct = ((act.range[1] - act.range[0] + 1) / (plan.totalChapters || 100)) * 100;
            const progress = Math.min(100, Math.max(0, ((currentChapter - act.range[0]) / (act.range[1] - act.range[0] + 1)) * 100));
            return (
              <div key={act.id} className="flex items-center gap-2">
                <span className="text-[10px] text-ink-muted w-16 shrink-0">{act.name}</span>
                <div className="flex-1 h-5 bg-border/50 rounded-full overflow-hidden relative" style={{ width: `${Math.max(5, pct)}%` }}>
                  {currentChapter >= act.range[0] && (
                    <div className="h-full bg-accent/30 rounded-full" style={{ width: `${Math.max(3, progress)}%` }} />
                  )}
                  <span className="absolute inset-0 flex items-center justify-center text-[8px] text-ink-subtle">
                    第{act.range[0]}-{act.range[1]}章
                  </span>
                </div>
                <span className="text-[9px] text-ink-subtle">{act.goal.slice(0, 20)}</span>
                <button onClick={() => removeAct(act.id)} className="text-[9px] text-red-400 hover:text-red-600 dark:hover:text-red-400 opacity-0 group-hover:opacity-100">×</button>
              </div>
            );
          })}
        </div>
      )}

      {/* Key beats list */}
      {plan?.keyBeats && plan.keyBeats.length > 0 && (
        <div className="mb-3 flex gap-1.5 flex-wrap">
          {plan.keyBeats.slice(0, 12).map((b, i) => (
            <span key={i} className={`text-[10px] px-2 py-0.5 rounded-full border ${
              b.chapter <= currentChapter ? 'bg-emerald-50 border-emerald-200 text-emerald-600 dark:bg-emerald-950/20 dark:border-emerald-800 dark:text-emerald-400' : 'border-border text-ink-muted'
            }`} title={b.event}>
              {beatEmojis[b.type]} 第{b.chapter}章
              <button onClick={() => removeBeat(i)} className="ml-1 text-ink-subtle hover:text-red-500">×</button>
            </span>
          ))}
        </div>
      )}

      {/* Hierarchical context preview */}
      <div>
        <button onClick={() => setShowContext(!showContext)}
          className="flex items-center gap-1.5 text-[10px] text-accent hover:underline">
          {showContext ? '▾' : '▸'} 查看层级化注入上下文（当前：第{currentChapter}章）
        </button>
        {showContext && (
          <div className="mt-2 space-y-2 text-[10px]">
            {context.level1 && (
              <div className="p-2 rounded bg-accent-soft/20 border border-accent/10">
                <div className="text-accent font-medium mb-0.5">🔴 Level 1 · 始终注入</div>
                <pre className="text-ink-muted whitespace-pre-wrap">{context.level1}</pre>
              </div>
            )}
            {context.level2 && (
              <div className="p-2 rounded bg-paper border border-border">
                <div className="text-ink font-medium mb-0.5">🟡 Level 2 · 当前卷</div>
                <pre className="text-ink-muted whitespace-pre-wrap">{context.level2}</pre>
              </div>
            )}
            {context.level3 && (
              <div className="p-2 rounded bg-paper border border-border">
                <div className="text-ink-subtle font-medium mb-0.5">🟢 Level 3 · 前情</div>
                <pre className="text-ink-muted whitespace-pre-wrap">{context.level3}</pre>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
