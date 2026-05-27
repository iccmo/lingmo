import { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { api } from 'src/lib/api';
import type { NovelDetail } from 'src/types';
import { WriterChapterList } from 'src/components/novels/WriterChapterList';
import { WriterContext } from 'src/components/novels/WriterContext';
import { WriterGenerate } from 'src/components/novels/WriterGenerate';

interface GenStatus {
  status: string;
  message: string;
  progress: number;
  overall?: number;
  grade?: string;
}

export function WriterView() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

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

  // Load novel on mount
  useEffect(() => {
    if (!id) return;
    setLoading(true);
    api.novels.get(id)
      .then(data => {
        setNovel(data);
        const latest = data.chapters.filter(c => c.word_count > 0).pop();
        if (latest) setActiveChapter(latest.number);
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
      .then(data => setChapterContent(data.content || ''))
      .catch(() => setChapterContent(''))
      .finally(() => setLoadingContent(false));
  }, [id, activeChapter]);

  // SSE polling during generation
  useEffect(() => {
    if (!polling || !id) return;
    const es = new EventSource(`/api/novels/${id}/generate/stream`);
    es.onmessage = (event) => {
      try {
        const s = JSON.parse(event.data) as GenStatus;
        setGenStatus(s);
        if (s.status === 'complete') {
          setPolling(false);
          toast.success(s.message);
          api.novels.get(id).then(data => {
            setNovel(data);
            const latest = data.chapters.filter(c => c.word_count > 0).pop();
            if (latest) setActiveChapter(latest.number);
            setTimeout(() => setGenStatus(null), 3000);
          });
        }
        if (s.status === 'error') {
          setPolling(false);
          toast.error(s.message);
        }
      } catch { /* ignore parse errors */ }
    };
    es.onerror = () => { es.close(); setPolling(false); };
    return () => es.close();
  }, [polling, id]);

  // Generate next chapter
  const handleGenerate = useCallback(async () => {
    if (!id) return;
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

      await fetch(`/api/novels/${id}/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      setPolling(true);
      setGenStatus({ status: 'generating', message: '正在构思下一章...', progress: 10 });
    } catch (e: unknown) {
      toast.error('生成失败: ' + (e as Error).message);
    }
  }, [id, direction]);

  // Save edited chapter
  const handleSave = useCallback(async () => {
    if (!id || !activeChapter) return;
    setSaving(true);
    try {
      await api.novels.saveChapter(id, activeChapter, editContent);
      setChapterContent(editContent);
      setEditing(false);
      toast.success('已保存');
    } catch (e: unknown) {
      toast.error('保存失败: ' + (e as Error).message);
    } finally {
      setSaving(false);
    }
  }, [id, activeChapter, editContent]);

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
          <span className="text-xs text-ink-muted ml-auto">
            第 {activeChapter} 章
            {qualityGrade != null && (
              <span className="ml-1.5 text-[10px] text-ink-subtle">
                Q:{qualityGrade.toFixed(2)}
              </span>
            )}
          </span>
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

          {/* Content area */}
          {loadingContent ? (
            <div className="p-8">
              <div className="skeleton h-4 w-3/4 mb-2 rounded" />
              <div className="skeleton h-4 w-full mb-2 rounded" />
              <div className="skeleton h-4 w-2/3 mb-2 rounded" />
              <div className="skeleton h-4 w-1/2 rounded" />
            </div>
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
                  {saving ? '保存中...' : '保存'}
                </button>
              </div>
            </div>
          ) : (
            /* Reading mode */
            <div className="relative">
              <button
                onClick={startEditing}
                className="absolute top-3 right-3 z-10 px-2 py-1 text-[10px] rounded border border-border
                  bg-card/80 backdrop-blur-sm text-ink-subtle hover:text-ink hover:border-accent transition-all"
              >
                ✏️ 编辑
              </button>
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
                  <p className="text-2xl mb-2">📖</p>
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
    </div>
  );
}
