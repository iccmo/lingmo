import { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Card, CardContent } from 'src/components/ui/card';
import { Badge } from 'src/components/ui/badge';
import { Skeleton } from 'src/components/ui/skeleton';
import { api } from 'src/lib/api';
import { toast } from 'sonner';
import type { DraftOption, NovelDetail, ChapterMeta } from 'src/types';

type Step = 'input' | 'selecting' | 'editing' | 'saving';

export function Editor() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [step, setStep] = useState<Step>('input');
  const [novel, setNovel] = useState<NovelDetail | null>(null);
  const [direction, setDirection] = useState('');
  const [drafts, setDrafts] = useState<DraftOption[]>([]);
  const [selectedDraft, setSelectedDraft] = useState<DraftOption | null>(null);
  const [body, setBody] = useState('');
  const [title, setTitle] = useState('');
  const [loading, setLoading] = useState(false);
  const [editChapterNum, setEditChapterNum] = useState<number | null>(null);
  const [showPreview, setShowPreview] = useState(false);
  const [chapterList, setChapterList] = useState<ChapterMeta[]>([]);
  // Find/replace
  const [findTerm, setFindTerm] = useState('');
  const [replaceTerm, setReplaceTerm] = useState('');
  const [showFind, setShowFind] = useState(false);
  const [matchCount, setMatchCount] = useState(0);

  // Undo/redo history
  const [history, setHistory] = useState<string[]>([]);
  const [historyIdx, setHistoryIdx] = useState(-1);
  const [ignoreNextChange, setIgnoreNextChange] = useState(false);

  function pushHistory(text: string) {
    if (ignoreNextChange) { setIgnoreNextChange(false); return; }
    setHistory(prev => {
      const next = prev.slice(0, historyIdx + 1);
      if (next[next.length - 1] === text) return prev;
      next.push(text);
      if (next.length > 100) next.shift();
      return next;
    });
    setHistoryIdx(prev => Math.min(prev + 1, 99));
  }

  function undo() {
    if (historyIdx <= 0) return;
    const newIdx = historyIdx - 1;
    setBody(history[newIdx]);
    setHistoryIdx(newIdx);
    setIgnoreNextChange(true);
  }

  function redo() {
    if (historyIdx >= history.length - 1) return;
    const newIdx = historyIdx + 1;
    setBody(history[newIdx]);
    setHistoryIdx(newIdx);
    setIgnoreNextChange(true);
  }

  useEffect(() => {
    if (!id) return;
    api.novels.get(id).then(d => {
      setNovel(d);
      setChapterList(d.chapters || []);
    }).catch(() => toast.error('加载失败'));
  }, [id]);

  // Load existing chapter for editing
  const loadChapter = useCallback(async (num: number) => {
    if (!id) return;
    setLoading(true);
    try {
      const data = await api.novels.chapter(id, num);
      setBody(data.content || '');
      setTitle(data.title || '');
      setEditChapterNum(num);
      setStep('editing');
      toast.success(`已加载第${num}章`);
    } catch {
      toast.error('加载章节失败');
    } finally {
      setLoading(false);
    }
  }, [id]);

  // Auto-save draft to localStorage
  useEffect(() => {
    if (step === 'editing' && body.length > 100 && id) {
      const timer = setTimeout(() => {
        localStorage.setItem(`editor-draft-${id}`, body);
      }, 3000);
      return () => clearTimeout(timer);
    }
  }, [body, step, id]);

  // Restore draft on mount
  useEffect(() => {
    if (id && step === 'editing' && !body) {
      const saved = localStorage.getItem(`editor-draft-${id}`);
      if (saved) {
        setBody(saved);
        toast.info('已恢复上次编辑内容', { duration: 2000 });
      }
    }
  }, [id]);

  // Keyboard shortcuts
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (step !== 'editing') return;
      if ((e.ctrlKey || e.metaKey) && e.key === 'f') {
        e.preventDefault(); setShowFind(true);
      }
      if ((e.ctrlKey || e.metaKey) && e.key === 's') {
        e.preventDefault();
        handleSave();
      }
      if ((e.ctrlKey || e.metaKey) && e.key === 'z' && !e.shiftKey) {
        e.preventDefault();
        undo();
      }
      if ((e.ctrlKey || e.metaKey) && (e.key === 'y' || (e.key === 'z' && e.shiftKey))) {
        e.preventDefault();
        redo();
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [body, title, step, editChapterNum, historyIdx, history]);

  async function handleDraft() {
    if (!direction.trim()) { toast.error('请输入本章方向'); return; }
    if (!id) return;
    setLoading(true);
    setStep('selecting');
    try {
      const res = await api.novels.draft(id, direction);
      setDrafts(res.directions);
    } catch (e: unknown) {
      toast.error('生成草稿失败: ' + (e as Error).message);
      setStep('input');
    } finally {
      setLoading(false);
    }
  }

  async function handleSelect(draft: DraftOption) {
    if (!id) return;
    setSelectedDraft(draft);
    setLoading(true);
    try {
      const res = await api.novels.expand(id, draft.id, { direction: draft.direction, preview: draft.preview, hook: draft.hook });
      setTitle(res.title);
      setBody(res.body);
      setEditChapterNum(null);
      setStep('editing');
    } catch (e: unknown) {
      toast.error('展开失败: ' + (e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  async function handleSave() {
    if (!id || !novel) return;
    const chapterNum = editChapterNum || (novel.total_chapters || 0) + 1;
    if (!body.trim()) { toast.error('内容不能为空'); return; }
    setStep('saving');
    try {
      await api.novels.saveChapter(id, chapterNum, body);
      localStorage.removeItem(`editor-draft-${id}`);
      toast.success(`第${chapterNum}章已保存`);
      navigate(`/novels/${id}`);
    } catch (e: unknown) {
      toast.error('保存失败: ' + (e as Error).message);
      setStep('editing');
    }
  }

  const stepLabels: Record<Step, string> = { input: '输入方向', selecting: '选择走向', editing: '编辑正文', saving: '保存中' };
  const wordCount = body.replace(/\s/g, '').length;
  const wordGoal = 3000;
  const wordPct = Math.min(100, Math.round((wordCount / wordGoal) * 100));

  if (!novel) {
    return <div className="p-8 space-y-4 max-w-[720px] mx-auto"><Skeleton className="h-8 w-64" /><Skeleton className="h-5 w-48" /></div>;
  }

  return (
    <div className="max-w-[900px] mx-auto page-enter">
      <button onClick={() => navigate(`/novels/${id}`)} className="text-xs text-ink-muted hover:text-ink mb-2 block">
        ← 返回小说详情
      </button>
      <h1 className="font-heading text-[28px] font-semibold text-ink leading-tight mb-1">{novel.title}</h1>
      <p className="text-sm text-ink-muted mb-6">创作者模式 · {stepLabels[step]}</p>

      {/* Step indicators with labels */}
      <div className="flex items-center gap-2 mb-8">
        {(['input','selecting','editing','saving'] as Step[]).map((s, i) => {
          const active = step === s;
          const done = ['input','selecting','editing','saving'].indexOf(step) > i;
          return (
            <div key={s} className="flex items-center gap-2">
              <div className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-medium transition-all ${
                active ? 'bg-accent text-white' : done ? 'bg-accent-soft text-accent' : 'bg-border/50 text-ink-subtle'
              }`}>
                <span className="w-4 h-4 rounded-full bg-white/20 flex items-center justify-center text-[10px] font-bold">
                  {done ? '✓' : i + 1}
                </span>
                {stepLabels[s]}
              </div>
              {i < 3 && <div className={`w-6 h-0.5 rounded ${done ? 'bg-accent' : 'bg-border'}`} />}
            </div>
          );
        })}
      </div>

      {/* Existing chapters */}
      {step === 'input' && chapterList.filter(c => c.word_count > 0).length > 0 && (
        <div className="mb-6">
          <p className="text-xs text-ink-muted mb-2">或编辑已有章节：</p>
          <div className="flex gap-1.5 flex-wrap">
            {chapterList.filter(c => c.word_count > 0).slice(-10).map(c => (
              <button key={c.number} onClick={() => loadChapter(c.number)}
                className="text-[11px] px-2.5 py-1 rounded-full border border-border text-ink-muted hover:text-ink hover:border-accent/30 transition-colors">
                第{c.number}章 {c.title.slice(0, 10)}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Step 1: Input direction */}
      {step === 'input' && (
        <div>
          <textarea
            placeholder="输入本章方向...&#10;例如：主角突破金丹，但天道降下雷劫，同时宿敌趁机偷袭宗门..."
            className="w-full min-h-[120px] rounded-lg border border-input bg-card text-ink text-sm px-4 py-3 resize-y
              placeholder:text-ink-subtle focus:outline-none focus:border-accent focus:ring-1 focus:ring-accent/20 transition-all"
            value={direction}
            onChange={e => setDirection(e.target.value)}
          />
          <button
            className="mt-4 px-5 py-2.5 rounded-lg bg-accent text-white hover:bg-accent-hover transition-colors font-medium text-sm disabled:opacity-50"
            onClick={handleDraft} disabled={loading}>
            ✨ 生成 3 个草稿方向
          </button>
        </div>
      )}

      {/* Step 2: Select draft */}
      {step === 'selecting' && (
        <div>
          {loading ? (
            <div className="space-y-3">
              {[1,2,3].map(i => <Skeleton key={i} className="h-28 w-full rounded-lg" />)}
            </div>
          ) : (
            <div>
              <p className="text-sm text-ink-muted mb-4">选择最合适的剧情走向，AI 将据此展开完整章节：</p>
              <div className="grid gap-3">
                {drafts.map(d => (
                  <Card key={d.id}
                    className={`cursor-pointer transition-all hover:-translate-y-0.5 hover:shadow-md ${
                      selectedDraft?.id === d.id ? 'border-accent ring-1 ring-accent/20 bg-accent-soft/30' : 'border-border hover:border-accent/30'
                    }`}
                    onClick={() => handleSelect(d)}>
                    <CardContent className="p-4">
                      <div className="flex items-center gap-2 mb-2">
                        <Badge variant="outline" className="text-xs">走向 {d.id}</Badge>
                        <span className="text-sm font-semibold text-ink">{d.direction}</span>
                      </div>
                      {d.preview && (
                        <p className="text-xs text-ink-muted leading-relaxed line-clamp-3 font-[var(--font-editor)]">{d.preview}</p>
                      )}
                      {d.hook && (
                        <p className="text-[10px] text-accent mt-2">🎣 钩子: {d.hook.slice(0, 50)}</p>
                      )}
                    </CardContent>
                  </Card>
                ))}
              </div>
              <button className="text-xs text-ink-muted hover:text-ink mt-3 transition-colors" onClick={() => setStep('input')}>
                ← 重新输入方向
              </button>
            </div>
          )}
        </div>
      )}

      {/* Step 3: Edit */}
      {step === 'editing' && (
        <div>
          {/* Toolbar */}
          <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
            <div className="flex items-center gap-2">
              <Badge variant="outline" className="text-xs">
                {editChapterNum ? `编辑第${editChapterNum}章` : `新章 ${(novel.total_chapters || 0) + 1}`}
              </Badge>
              {title && <span className="text-sm text-ink font-medium">{title}</span>}
            </div>
            <div className="flex items-center gap-3">
              {/* Word count progress */}
              <div className="flex items-center gap-1.5 text-[10px]">
                <div className="w-16 h-1.5 bg-border rounded-full overflow-hidden">
                  <div className={`h-full rounded-full transition-all ${wordPct >= 100 ? 'bg-emerald-500' : 'bg-accent'}`}
                    style={{ width: `${Math.max(3, wordPct)}%` }} />
                </div>
                <span className={`tabular-nums ${wordCount >= wordGoal ? 'text-emerald-500 font-semibold' : 'text-ink-muted'}`}>
                  {wordCount.toLocaleString()}
                </span>
              </div>
              <div className="flex items-center gap-1 text-[10px] text-ink-subtle">
                <button onClick={undo} disabled={historyIdx <= 0}
                  className="px-1.5 py-0.5 rounded border border-border hover:text-ink disabled:opacity-30 transition-colors"
                  title="撤销 Ctrl+Z">↩</button>
                <button onClick={redo} disabled={historyIdx >= history.length - 1}
                  className="px-1.5 py-0.5 rounded border border-border hover:text-ink disabled:opacity-30 transition-colors"
                  title="重做 Ctrl+Shift+Z">↪</button>
              </div>
              <button onClick={() => setShowPreview(!showPreview)}
                className={`text-[10px] px-2 py-0.5 rounded border transition-colors ${
                  showPreview ? 'bg-accent-soft text-accent border-accent/30' : 'border-border text-ink-muted hover:text-ink'
                }`}>
                {showPreview ? '隐藏预览' : '👁 预览'}
              </button>
            </div>
          </div>

          {/* Find/Replace bar */}
          {showFind && (
            <div className="flex items-center gap-2 mb-2 p-2 bg-paper rounded-lg border border-border">
              <input value={findTerm} onChange={e => { setFindTerm(e.target.value); setMatchCount((body.match(new RegExp(e.target.value.replace(/[.*+?^${}()|[\]\\]/g,'\\$&'),'gi'))||[]).length); }}
                placeholder="查找..." autoFocus
                className="flex-1 text-xs bg-transparent outline-none placeholder:text-ink-subtle" />
              <span className="text-[10px] text-ink-subtle tabular-nums">{matchCount}处</span>
              <input value={replaceTerm} onChange={e => setReplaceTerm(e.target.value)}
                placeholder="替换为..."
                className="w-28 text-xs bg-transparent outline-none placeholder:text-ink-subtle" />
              <button onClick={() => { setBody(body.replace(new RegExp(findTerm.replace(/[.*+?^${}()|[\]\\]/g,'\\$&'),'g'),replaceTerm)); setShowFind(false); }}
                className="text-[10px] px-2 py-0.5 rounded bg-accent text-white hover:bg-accent-hover disabled:opacity-30"
                disabled={!findTerm}>全部替换</button>
              <button onClick={() => setShowFind(false)} className="text-xs text-ink-muted hover:text-ink">✕</button>
            </div>
          )}

          <div className={`grid ${showPreview ? 'grid-cols-2' : 'grid-cols-1'} gap-4`}>
            {/* Editor */}
            <textarea
              className="w-full min-h-[500px] rounded-lg border border-input bg-card text-ink text-[15px] leading-[1.9] px-4 py-3 resize-y
                font-[var(--font-editor)] focus:outline-none focus:border-accent focus:ring-1 focus:ring-accent/20 transition-all"
              value={body}
              onChange={e => { setBody(e.target.value); pushHistory(e.target.value); }}
              placeholder="开始编辑章节正文..."
            />

            {/* Live Preview */}
            {showPreview && (
              <div className="min-h-[500px] rounded-lg border border-border bg-paper p-4 overflow-y-auto reading-mode text-sm">
                {body ? (
                  body.split('\n').map((line, i) => {
                    const trimmed = line.trim();
                    if (!trimmed) return <br key={i} />;
                    if (trimmed.startsWith('# ')) return <h1 key={i}>{trimmed.replace(/^# /, '')}</h1>;
                    if (trimmed.startsWith('## ')) return <h2 key={i}>{trimmed.replace(/^## /, '')}</h2>;
                    if (trimmed.startsWith('> ')) return <blockquote key={i}><p>{trimmed.replace(/^> /, '')}</p></blockquote>;
                    return <p key={i}>{trimmed}</p>;
                  })
                ) : (
                  <p className="text-ink-subtle text-center py-20">预览将在这里显示...</p>
                )}
              </div>
            )}
          </div>

          {/* Actions */}
          <div className="flex gap-2 mt-4">
            <button
              className="px-5 py-2.5 rounded-lg bg-accent text-white hover:bg-accent-hover transition-colors font-medium text-sm flex items-center gap-1.5"
              onClick={handleSave}>
              💾 保存章节
              <span className="text-[10px] opacity-50 font-mono">Ctrl+S</span>
            </button>
            <button className="text-sm px-4 py-2.5 rounded-lg border border-border text-ink-muted hover:text-ink transition-colors"
              onClick={() => setStep('selecting')}>
              重新选择走向
            </button>
            <button className="text-sm px-4 py-2.5 rounded-lg border border-border text-ink-muted hover:text-ink transition-colors"
              onClick={() => { if (confirm('确定放弃当前编辑？')) { setBody(''); setStep('input'); } }}>
              放弃
            </button>
          </div>
        </div>
      )}

      {/* Step 4: Saving */}
      {step === 'saving' && (
        <div className="text-center py-24">
          <div className="animate-spin w-10 h-10 border-[3px] border-accent border-t-transparent rounded-full mx-auto mb-4" />
          <p className="text-ink-muted text-sm">正在保存章节...</p>
        </div>
      )}
    </div>
  );
}
