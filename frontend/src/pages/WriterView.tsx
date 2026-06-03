import { useState, useEffect, useCallback, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { api } from 'src/lib/api';
import type { NovelDetail } from 'src/types';
import { PenLine, BookOpen, BarChart3, ListTodo } from 'lucide-react';
import { WriterChapterList } from 'src/components/novels/WriterChapterList';
import { WriterContext } from 'src/components/novels/WriterContext';
import { WriterGenerate } from 'src/components/novels/WriterGenerate';
import { GenerationPipeline } from 'src/components/novels/GenerationPipeline';
import { WritingStatsBar } from 'src/components/writing/WritingStatsBar';
import { ChapterSkeleton } from 'src/components/ui/skeleton';
import { QualityTrend } from 'src/components/novels/QualityTrend';
import { EmotionalArc } from 'src/components/novels/EmotionalArc';
import { useWritingStats } from 'src/hooks/useWritingStats';
import { genErrorMessage } from 'src/lib/error-messages';

interface GenStatus {
  status: string;
  message: string;
  progress: number;
  overall?: number;
  grade?: string;
  stream_content?: string;
  quality_detail?: Record<string, { score: number; reason: string }>;
  causal_events?: string;
}

export function WriterView() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { stats, updateWords } = useWritingStats();

  const [novel, setNovel] = useState<NovelDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeChapter, setActiveChapter] = useState<number | null>(null);
  const [chapterContent, setChapterContent] = useState('');
  const [loadingContent, setLoadingContent] = useState(false);
  const [editing, setEditing] = useState(false);
  const [editContent, setEditContent] = useState('');
  const [saving, setSaving] = useState(false);
  const [rightPanelOpen, setRightPanelOpen] = useState(true);
  const [genStatus, setGenStatus] = useState<GenStatus | null>(null);
  const [polling, setPolling] = useState(false);
  const [showDirection, setShowDirection] = useState(false);
  const [direction, setDirection] = useState('');
  const [showAnalysis, setShowAnalysis] = useState(false);

  // Outline data
  interface OutlineItem { number: number; title: string; summary: string }
  const [outlineItems, setOutlineItems] = useState<OutlineItem[]>([]);
  const [outlineNext, setOutlineNext] = useState<number>(0);

  // Load outline
  useEffect(() => {
    if (!id) return;
    fetch(`/api/novels/${id}/outline`)
      .then(r => r.json())
      .then((d: { outline: OutlineItem[]; next_number: number }) => {
        setOutlineItems(d.outline || []);
        setOutlineNext(d.next_number || 0);
      })
      .catch(() => { /* outline fetch is best-effort */ });
  }, [id]);

  // Load novel on mount
  useEffect(() => {
    if (!id) return;
    setLoading(true);
    api.novels.get(id)
      .then(data => {
        setNovel(data);
        // Prefer last-read chapter, fallback to latest
        const lastRead = (() => { try { return JSON.parse(localStorage.getItem(`last-read-${id}`) || 'null'); } catch { return null; } })();
        const lastReadNum = lastRead?.chapter;
        const lastReadValid = data.chapters.some((c: {number:number; word_count:number}) => c.number === lastReadNum && c.word_count > 0);
        const latest = data.chapters.filter((c: {word_count:number}) => c.word_count > 0).pop();
        if (lastReadValid) setActiveChapter(lastReadNum);
        else if (latest) setActiveChapter(latest.number);
      })
      .catch(() => toast.error('加载小说失败'))
      .finally(() => setLoading(false));
  }, [id]);

  // Load chapter content
  useEffect(() => {
    if (!id || !activeChapter) return;
    setLoadingContent(true);
    setEditing(false);
    api.novels.chapter(id, activeChapter)
      .then(data => {
        const content = data.content || '';
        setChapterContent(content);
        // Update word count for stats
        const wordCount = content.replace(/\s/g, '').length;
        updateWords(wordCount);
      })
      .catch(() => setChapterContent('__LOAD_ERROR__'))
      .finally(() => setLoadingContent(false));
  }, [id, activeChapter, updateWords]);

  // Generate with SSE + polling fallback
  const genStartRef = useRef(0);

  useEffect(() => {
    if (!polling || !id) return;
    genStartRef.current = Date.now();
    let retries = 0;
    let es: EventSource | null = null;
    let pollTimer: ReturnType<typeof setInterval> | null = null;

    function connectSSE() {
      es = new EventSource(`/api/novels/${id}/generate/stream`);
      es.onmessage = (event) => {
        try {
          const s = JSON.parse(event.data) as GenStatus;
          setGenStatus(s);
          if (s.status === 'complete') {
            cleanup();
            const elapsed = Math.round((Date.now() - genStartRef.current) / 1000);
            toast.success(`生成完成！耗时${elapsed}秒`);
            // Keep genStatus visible so banner shows quality info
            api.novels.get(id!).then(data => {
              setNovel(data);
              const latest = data.chapters.filter(c => c.word_count > 0).pop();
              if (latest) setActiveChapter(latest.number);
            });
          }
          if (s.status === 'error') {
            cleanup();
            // Keep error visible in banner with friendly message
            setGenStatus({ ...s, message: genErrorMessage(s.message) });
          }
        } catch { /* ignore parse errors */ }
      };
      es.onerror = () => {
        es?.close();
        if (retries < 3) {
          retries++;
          setTimeout(connectSSE, 2000 * retries);
        } else {
          // Fallback: start polling as backup
          if (!pollTimer) {
            pollTimer = setInterval(async () => {
              try {
                const r = await fetch(`/api/novels/${id}/generate/queue-status`);
                const d = await r.json();
                if (d.status === 'done' || d.status === 'complete') {
                  cleanup();
                  toast.success('生成完成！');
                  api.novels.get(id!).then(data => setNovel(data));
                } else if (d.status === 'error') {
                  cleanup();
                  setGenStatus({ status: 'error', message: d.last_error || '生成失败', progress: 0 });
                } else if (d.status === 'idle' && Date.now() - genStartRef.current > 300000) {
                  cleanup();
                  setGenStatus({ status: 'error', message: '生成超时，模型可能过载，请稍后重试', progress: 0 });
                }
              } catch {}
            }, 5000);
          }
        }
      };
    }

    function cleanup() {
      generatingRef.current = false;
      setPolling(false);
      es?.close();
      if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
    }

    connectSSE();
    return cleanup;
  }, [polling, id]);

  // Generate state ref — instant guard against double-clicks (React state is async)
  const generatingRef = useRef(false);

  // Generate next chapter
  const handleGenerate = useCallback(async () => {
    if (!id) return;
    if (generatingRef.current) {
      toast('正在生成中，请等待当前章节完成', { description: genStatus?.message || '' });
      return;
    }
    try {
      const body: Record<string, unknown> = {
        quality_threshold: 0.78,
        compression: 'L1',
      };
      try {
        const fp = JSON.parse(localStorage.getItem(`soul-fingerprint-${id}`) || 'null');
        if (fp?.answer) body.soul_injection = `【灵魂】${fp.answer}`;
      } catch { /* no soul fingerprint */ }
      if (direction.trim()) body.direction = direction.trim();

      generatingRef.current = true;
      setPolling(true);  // set BEFORE fetch to prevent double requests
      setGenStatus({ status: 'generating', message: '正在构思下一章...', progress: 10 });
      await fetch(`/api/novels/${id}/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
    } catch (e: unknown) {
      const errMsg = genErrorMessage((e as Error).message || '网络错误');
      generatingRef.current = false;
      setPolling(false);
      setGenStatus({ status: 'error', message: errMsg, progress: 0 });
    }
  }, [id, direction, polling]);

  // Save edited chapter
  const handleSave = useCallback(async (silent = false) => {
    if (!id || !activeChapter || !editContent) return;
    setSaving(true);
    try {
      await api.novels.saveChapter(id, activeChapter, editContent);
      setChapterContent(editContent);
      if (!silent) {
        setEditing(false);
        toast.success('已保存');
      }
    } catch (e: unknown) {
      if (!silent) toast.error('保存失败: ' + (e as Error).message);
    } finally {
      setSaving(false);
    }
  }, [id, activeChapter, editContent]);

  // Auto-save: debounce save every 5 seconds while editing
  const autoSaveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const lastSavedContent = useRef(editContent);
  useEffect(() => {
    if (!editing || editContent === lastSavedContent.current) return;
    if (autoSaveTimer.current) clearTimeout(autoSaveTimer.current);
    autoSaveTimer.current = setTimeout(() => {
      lastSavedContent.current = editContent;
      handleSave(true);
    }, 5000);
    return () => { if (autoSaveTimer.current) clearTimeout(autoSaveTimer.current); };
  }, [editContent, editing, handleSave]);

  // Clear auto-save content ref when entering edit mode
  useEffect(() => {
    if (editing) lastSavedContent.current = '';
  }, [editing]);

  // Keyboard shortcuts
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 's') {
        e.preventDefault();
        if (editing) handleSave(false);
        else toast('当前不在编辑模式');
      }
      if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
        e.preventDefault();
        if (!generatingRef.current) handleGenerate();
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [editing, handleSave, handleGenerate]);

  // Enter edit mode
  const startEditing = useCallback(() => {
    setEditContent(chapterContent);
    setEditing(true);
  }, [chapterContent]);

  // Quality grade from score
  const qualityGrade = novel?.chapters.find(c => c.number === activeChapter)?.quality_score;

  // ── Loading states ──
  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center">
          <div className="skeleton h-8 w-48 mx-auto mb-2 rounded" />
          <div className="text-xs text-ink-subtle">加载中...</div>
        </div>
      </div>
    );
  }

  if (!novel) {
    return (
      <div className="flex items-center justify-center h-full">
        <p className="text-ink-subtle">小说未找到</p>
      </div>
    );
  }

  const genChapters = novel.chapters.filter(c => c.word_count > 0);

  return (
    <div className="flex flex-col h-full">
      {/* Top bar */}
      <div className="flex items-center gap-3 px-4 py-2 border-b border-border shrink-0">
        <button
          onClick={() => navigate(`/novels/${id}`)}
          className="text-xs text-ink-subtle hover:text-ink transition-colors"
        >
          ← 返回
        </button>
        <h2 className="text-sm font-semibold text-ink truncate">{novel.title}</h2>
        {activeChapter && (
          <span className="text-xs text-ink-muted ml-auto flex items-center gap-2">
            第 {activeChapter} 章
            {qualityGrade != null && (
              <span className="ml-1.5 text-[10px] text-ink-subtle">
                Q:{qualityGrade.toFixed(2)}
              </span>
            )}
          </span>
        )}
        {/* Analysis toggle */}
        {novel && novel.chapters.filter(c => c.word_count > 0).length >= 2 && (
          <button
            onClick={() => setShowAnalysis(!showAnalysis)}
            className={`ml-2 text-xs px-2.5 py-1 rounded-md border transition-all ${
              showAnalysis
                ? 'bg-accent/10 text-accent border-accent/30'
                : 'text-ink-muted border-border hover:text-ink hover:border-accent/20'
            }`}
          >
            <BarChart3 size={13} className="inline mr-1" />
            {showAnalysis ? '返回写作' : '分析'}
          </button>
        )}
      </div>

      {/* 3-panel body */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left: chapter list (desktop) */}
        <div className="w-[200px] min-w-[200px] border-r border-border overflow-y-auto shrink-0 hidden lg:block">
          <WriterChapterList
            chapters={novel.chapters}
            activeChapter={activeChapter}
            onSelect={(n) => { setActiveChapter(n); setRightPanelOpen(true); }}
          />
        </div>

        {/* Center: chapter content */}
        <div className="flex-1 overflow-y-auto">
          {/* Mobile chapter selector */}
          <div className="lg:hidden px-3 py-2 border-b border-border">
            <select
              value={activeChapter ?? ''}
              onChange={e => setActiveChapter(Number(e.target.value))}
              className="w-full text-xs rounded-md border border-input bg-card px-3 py-1.5"
            >
              {genChapters.map(ch => (
                <option key={ch.number} value={ch.number}>
                  第{ch.number}章 {ch.title} {ch.quality_score != null ? `(Q:${ch.quality_score.toFixed(2)})` : ''}
                </option>
              ))}
            </select>
          </div>

          {/* Mobile right panel toggle */}
          <div className="lg:hidden px-3 py-1 border-b border-border">
            <button
              onClick={() => setRightPanelOpen(!rightPanelOpen)}
              className="text-xs text-accent hover:underline"
            >
              {rightPanelOpen ? '收起上下文 ▲' : '展开上下文 ▼'}
            </button>
          </div>

          {/* Mobile right panel (inline) */}
          {rightPanelOpen && (
            <div className="lg:hidden px-3 py-2 border-b border-border">
              <WriterContext novelId={id!} chapterNum={activeChapter} genStatus={genStatus} />
            </div>
          )}

          {/* Generation pipeline — shows streams, quality, retry */}
          <GenerationPipeline
            genStatus={genStatus as unknown as { status: string; message: string; progress: number; overall?: number; grade?: string; stream_content?: string; quality_detail?: Record<string, number> }}
            onRetry={handleGenerate}
          />

          {/* Post-generation quality panel */}
          {genStatus?.status === 'complete' && genStatus.quality_detail && (
            <div className="mx-4 lg:mx-6 mt-3 p-4 bg-card/60 rounded-xl border border-border animate-[fadeSlideIn_0.2s_ease-out]">
              <h4 className="text-xs font-semibold text-ink mb-3 flex items-center gap-1.5">
                <BarChart3 size={13} className="text-accent" /> 质量细分
                {genStatus.grade && (
                  <span className={`ml-auto text-[10px] px-1.5 py-0.5 rounded font-bold ${
                    genStatus.grade === 'A' ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300' :
                    genStatus.grade === 'B' ? 'bg-sky-100 text-sky-700 dark:bg-sky-900/40 dark:text-sky-300' :
                    'bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300'
                  }`}>{genStatus.grade}级</span>
                )}
              </h4>
              <div className="grid grid-cols-3 gap-2">
                {Object.entries(genStatus.quality_detail).slice(0, 6).map(([key, val]) => {
                  const score = typeof val === 'number' ? val : (val as { score: number; reason: string }).score;
                  const reason = typeof val === 'object' ? (val as { score: number; reason: string }).reason : '';
                  const pct = Math.min(100, Math.max(0, score * 10));
                  return (
                    <div key={key} className="p-2 rounded-lg bg-surface/50" title={reason}>
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-[10px] text-ink-muted">{key}</span>
                        <span className={`text-[10px] font-bold tabular-nums ${
                          score >= 8 ? 'text-emerald-500' : score >= 6 ? 'text-amber-500' : 'text-red-400'
                        }`}>{score}</span>
                      </div>
                      <div className="h-1 bg-border rounded-full overflow-hidden">
                        <div className={`h-full rounded-full transition-all ${
                          score >= 8 ? 'bg-emerald-400' : score >= 6 ? 'bg-amber-400' : 'bg-red-400'
                        }`} style={{ width: `${pct}%` }} />
                      </div>
                    </div>
                  );
                })}
              </div>
              {genStatus.causal_events && (
                <div className="mt-3 pt-3 border-t border-border">
                  <p className="text-[10px] text-ink-muted leading-relaxed whitespace-pre-wrap">{genStatus.causal_events}</p>
                </div>
              )}
            </div>
          )}

          {/* Analysis panel */}
          {showAnalysis && novel && (
            <div className="p-4 lg:p-6 space-y-4 overflow-y-auto">
              <h3 className="text-sm font-semibold text-ink mb-2">写作分析</h3>
              <QualityTrend chapters={novel.chapters} />
              <EmotionalArc chapters={novel.chapters} />
            </div>
          )}

          {/* Content area */}
          {!showAnalysis && (
          <>
          {loadingContent ? (
            <ChapterSkeleton />
          ) : editing ? (
            /* Edit mode */
            <div className="p-4 lg:p-6">
              <textarea
                value={editContent}
                onChange={e => setEditContent(e.target.value)}
                className="w-full min-h-[500px] bg-paper border border-border rounded-lg p-4 lg:p-6
                  text-sm leading-relaxed resize-y font-[var(--font-editor)]
                  focus:outline-none focus:border-accent focus:ring-1 focus:ring-accent/20"
                placeholder="编辑章节内容..."
              />
              <div className="flex gap-2 mt-3 justify-end">
                <button
                  onClick={() => setEditing(false)}
                  className="px-3 py-1.5 text-xs rounded-md border border-border text-ink-muted hover:text-ink transition-colors"
                >
                  取消
                </button>
                <button
                  onClick={handleSave}
                  disabled={saving}
                  className="px-4 py-1.5 text-xs rounded-md bg-accent text-white hover:bg-accent-hover disabled:opacity-50 transition-all"
                >
                  {saving ? '自动保存中...' : '保存 (Ctrl+S)'}
                </button>
              </div>
            </div>
          ) : (
            /* Reading mode */
            <div className="relative">
              <div className="absolute top-3 right-3 z-10 flex gap-1.5">
                <button
                  onClick={async () => {
                    if (!id || !activeChapter) return;
                    try {
                      const r = await fetch(`/api/novels/${id}/chapters/${activeChapter}/fix-formatting`, { method: 'POST' });
                      const d = await r.json();
                      if (d.ok) {
                        toast.success(`排版已优化（${d.changes}处修改）`);
                        // Reload chapter content
                        const data = await api.novels.chapter(id, activeChapter);
                        setChapterContent(data.content || '');
                      } else {
                        toast.error('优化失败');
                      }
                    } catch { toast.error('网络错误'); }
                  }}
                  className="px-2 py-1 text-[10px] rounded border border-border
                    bg-card/80 backdrop-blur-sm text-ink-subtle hover:text-ink hover:border-accent transition-all"
                  title="修复孤儿引号和排版问题"
                >
                  ✨ 排版
                </button>
                <button
                  onClick={startEditing}
                  className="px-2 py-1 text-[10px] rounded border border-border
                    bg-card/80 backdrop-blur-sm text-ink-subtle hover:text-ink hover:border-accent transition-all"
                >
                  <PenLine size={13} className="mr-1" /> 编辑
                </button>
              </div>
              {chapterContent ? (
                <div className="reading-mode px-6 py-8 max-w-[680px] mx-auto">
                  {chapterContent.split('\n').map((line, i) => {
                    const trimmed = line.trim();
                    if (!trimmed) return <br key={i} />;
                    if (trimmed.startsWith('# ') && !trimmed.startsWith('## '))
                      return <h1 key={i} className="chapter-title">{trimmed.replace(/^# /, '')}</h1>;
                    if (trimmed.startsWith('## '))
                      return <h2 key={i} className="text-lg font-semibold mt-8 mb-3 text-ink">{trimmed.replace(/^## /, '')}</h2>;
                    if (trimmed.startsWith('> '))
                      return <blockquote key={i} className="border-l-2 border-accent/30 pl-4 italic text-ink-muted my-4"><p>{trimmed.replace(/^> /, '')}</p></blockquote>;
                    if (trimmed === '——' || trimmed === '—')
                      return <hr key={i} className="section-break" />;
                    return <p key={i} className="mb-1">{trimmed}</p>;
                  })}
                </div>
              ) : (
                <div className="text-center py-20 text-ink-muted">
                  <BookOpen size={32} className="text-accent mb-2" />
                  <p className="text-sm">章节内容为空</p>
                  {activeChapter && (
                    <p className="text-xs text-ink-subtle mt-1">
                      点击下方"生成下一章"开始写作
                    </p>
                  )}
                </div>
              )}
            </div>
          )}
          </>
          )}
        </div>

        {/* Right: context panel (desktop) */}
        {rightPanelOpen && (
          <div className="w-[300px] min-w-[300px] border-l border-border overflow-y-auto shrink-0 hidden lg:block">
            <div className="p-3">
              <button
                onClick={() => setRightPanelOpen(false)}
                className="text-[10px] text-ink-subtle hover:text-ink mb-2 transition-colors"
              >
                ✕ 收起
              </button>
              <WriterContext novelId={id!} chapterNum={activeChapter} genStatus={genStatus} />

              {/* Outline card */}
              {outlineItems.length > 0 && (
                <div className="mt-3 pt-3 border-t border-border">
                  <h4 className="text-[10px] font-semibold text-ink-muted uppercase tracking-wider mb-2 flex items-center gap-1">
                    <ListTodo size={11} /> 大纲 ({outlineItems.length}章)
                  </h4>
                  <div className="space-y-1 max-h-[200px] overflow-y-auto">
                    {outlineItems.map(item => (
                      <div key={item.number}
                        className={`text-[11px] px-2 py-1.5 rounded-md transition-colors cursor-pointer
                          ${item.number === activeChapter ? 'bg-accent/10 border border-accent/20' : 'hover:bg-surface border border-transparent'}`}
                        onClick={() => setActiveChapter(item.number)}>
                        <span className="font-medium text-ink">第{item.number}章</span>
                        <span className="ml-1.5 text-ink">{item.title}</span>
                        {item.summary && (
                          <p className="text-[10px] text-ink-muted mt-0.5 leading-relaxed truncate">{item.summary}</p>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
        {/* Collapsed right panel toggle (desktop) */}
        {!rightPanelOpen && (
          <div className="border-l border-border shrink-0 hidden lg:flex items-center">
            <button
              onClick={() => setRightPanelOpen(true)}
              className="px-1 py-4 text-[10px] text-ink-subtle hover:text-ink transition-colors"
              title="展开上下文"
            >
              ◀
            </button>
          </div>
        )}
      </div>

      {/* Fixed bottom bar */}
      <WriterGenerate
        chapterCount={genChapters.length}
        onGenerate={handleGenerate}
        genStatus={genStatus}
        direction={direction}
        setDirection={setDirection}
        showDirection={showDirection}
        setShowDirection={setShowDirection}
      />

      {/* Writing stats floating bar */}
      <WritingStatsBar stats={stats} />
    </div>
  );
}
