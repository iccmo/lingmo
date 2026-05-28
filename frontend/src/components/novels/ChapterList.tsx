import { useState, useEffect, useRef, useCallback, useMemo, type ReactNode } from 'react';
import { api } from 'src/lib/api';
import { toast } from 'sonner';
const AUTO_SAVE_INTERVAL_MS = 5 * 60 * 1000; // 5 minutes
const MAX_AUTO_SAVES = 10;
import { ContextMenu } from 'src/components/ui/context-menu';
import { MobileReadingMode } from 'src/components/novels/MobileReadingMode';
import { ChapterDiff } from 'src/components/novels/ChapterDiff';
import { AudioTextSync } from 'src/components/novels/AudioTextSync';
import { SceneEditor } from 'src/components/novels/SceneEditor';
import { WordFrequency } from 'src/components/novels/WordFrequency';
import { useAudio } from 'src/lib/AudioContext';
import type { ChapterMeta } from 'src/types';

/* ─── Chapter tags ─── */
const TAG_OPTIONS = [
  { key: '高潮', emoji: '🔥', label: '高潮', color: 'bg-red-100 text-red-700 border-red-200 dark:bg-red-900/30 dark:text-red-400 dark:border-red-800' },
  { key: '过渡', emoji: '🌊', label: '过渡', color: 'bg-blue-100 text-blue-700 border-blue-200 dark:bg-blue-900/30 dark:text-blue-400 dark:border-blue-800' },
  { key: '伏笔', emoji: '🔮', label: '伏笔', color: 'bg-purple-100 text-purple-700 border-purple-200 dark:bg-purple-900/30 dark:text-purple-400 dark:border-purple-800' },
  { key: '战斗', emoji: '⚔️', label: '战斗', color: 'bg-orange-100 text-orange-700 border-orange-200 dark:bg-orange-900/30 dark:text-orange-400 dark:border-orange-800' },
  { key: '日常', emoji: '☕', label: '日常', color: 'bg-teal-100 text-teal-700 border-teal-200 dark:bg-teal-900/30 dark:text-teal-400 dark:border-teal-800' },
  { key: '转折', emoji: '🔄', label: '转折', color: 'bg-amber-100 text-amber-700 border-amber-200 dark:bg-amber-900/30 dark:text-amber-400 dark:border-amber-800' },
  { key: '感情', emoji: '💕', label: '感情', color: 'bg-pink-100 text-pink-700 border-pink-200 dark:bg-pink-900/30 dark:text-pink-400 dark:border-pink-800' },
];


const GRADE_COLORS: Record<string, string> = {
  S: 'bg-gradient-to-r from-emerald-100 to-accent-soft text-emerald-800 border-emerald-300 dark:from-emerald-900/40 dark:to-accent-soft/20 dark:text-emerald-300 dark:border-emerald-700 font-bold',
  A: 'bg-emerald-100 text-emerald-800 border-emerald-200 dark:bg-emerald-900/40 dark:text-emerald-300 dark:border-emerald-800',
  B: 'bg-sky-100 text-sky-800 border-sky-200 dark:bg-sky-900/40 dark:text-sky-300 dark:border-sky-800',
  C: 'bg-amber-100 text-amber-800 border-amber-200 dark:bg-amber-900/40 dark:text-amber-300 dark:border-amber-800',
  D: 'bg-red-100 text-red-800 border-red-200 dark:bg-red-900/40 dark:text-red-300 dark:border-red-800',
};

function gradeForScore(q: number | undefined): string {
  if (q === undefined) return '?';
  if (q >= 0.85) return 'S';
  if (q >= 0.80) return 'A';
  if (q >= 0.65) return 'B';
  if (q >= 0.50) return 'C';
  return 'D';
}

function highlightText(text: string, term: string): ReactNode {
  if (!term) return text;
  const escaped = term.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const parts = text.split(new RegExp(`(${escaped})`, 'gi'));
  return parts.map((part, i) =>
    part.toLowerCase() === term.toLowerCase()
      ? <mark key={i} className="search-highlight">{part}</mark>
      : part
  );
}

interface Props {
  chapters: ChapterMeta[];
  novelId: string;
  onDelete?: (num: number) => void;
  onRegenerate?: (num: number, feedback: string) => void;
}

export function ChapterList({ chapters, novelId, onDelete, onRegenerate }: Props) {
  const [expanded, setExpanded] = useState<number | null>(null);
  const [content, setContent] = useState<string>('');
  const [loadingContent, setLoadingContent] = useState(false);
  const [publishedSet, setPublishedSet] = useState<Set<number>>(new Set());
  const [focusMode, setFocusMode] = useState(false);
  const [readProgress, setReadProgress] = useState(0);
  const [searchTerm, setSearchTerm] = useState('');
  const [searchVisible, setSearchVisible] = useState(false);
  const [pinned, setPinned] = useState<Set<number>>(() => {
    try { return new Set(JSON.parse(localStorage.getItem(`pinned-${novelId}`) || '[]')); }
    catch { return new Set(); }
  });
  const [mobileChapter, setMobileChapter] = useState<number | null>(null);
  const [collapsedArcs, setCollapsedArcs] = useState<Set<string>>(new Set());
  const [attentionFilter, setAttentionFilter] = useState(false);
  const [editMode, setEditMode] = useState(false);
  const [editContent, setEditContent] = useState('');
  const editContentRef = useRef(editContent);
  // Keep ref in sync with state
  useEffect(() => { editContentRef.current = editContent; }, [editContent]);
  const [saving, setSaving] = useState(false);
  const [sceneView, setSceneView] = useState(false);
  // AI Proofreading
  const [proofreading, setProofreading] = useState(false);
  const [proofreadIssues, setProofreadIssues] = useState<{ type: string; original: string; suggestion: string; reason: string }[]>([]);
  const [showProofread, setShowProofread] = useState(false);
  // Word frequency analysis
  const [showWordFreq, setShowWordFreq] = useState(false);
  // Reverse polish
  const [polishing, setPolishing] = useState(false);
  const [polishedText, setPolishedText] = useState('');
  // Text analysis
  const [analyzing, setAnalyzing] = useState(false);
  const [analysisResult, setAnalysisResult] = useState<any>(null);
  // Chapter approval status: 'draft' | 'approved' | 'revise'
  const [approvals, setApprovals] = useState<Record<number, string>>(() => {
    try { return JSON.parse(localStorage.getItem(`approvals-${novelId}`) || '{}'); }
    catch { return {}; }
  });

  function cycleApproval(num: number, e?: { stopPropagation: () => void }) {
    e?.stopPropagation();
    setApprovals(prev => {
      const current = prev[num] || 'draft';
      const next = current === 'draft' ? 'approved' : current === 'approved' ? 'revise' : 'draft';
      const updated = { ...prev, [num]: next };
      localStorage.setItem(`approvals-${novelId}`, JSON.stringify(updated));
      return updated;
    });
  }

  // ── Audio text sync ──
  const { positionSec, progress: audioProgress, playing: audioPlaying, paused: audioPaused, current: audioCurrent } = useAudio();

  // Estimate audio duration from progress ratio (same formula as MiniPlayer)
  const estimatedDuration = useMemo(() => {
    if (audioProgress > 0 && positionSec > 0) {
      return Math.round(positionSec / (audioProgress / 100));
    }
    return 0;
  }, [positionSec, audioProgress]);

  // Check if the currently playing chapter matches the expanded one
  const isAudioSyncing =
    expanded !== null &&
    audioCurrent !== null &&
    audioCurrent.novelId === novelId &&
    audioCurrent.chapterNum === expanded &&
    audioPlaying &&
    !audioPaused;

  async function saveEdit() {
    if (!expanded || !editContent.trim()) return;
    setSaving(true);
    try {
      await fetch(`/api/novels/${novelId}/chapters/${expanded}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content: editContent }),
      });
      setContent(editContent);
      setEditMode(false);
      toast.success('已保存');
    } catch (e: unknown) {
      toast.error('保存失败: ' + (e as Error).message);
    } finally {
      setSaving(false);
    }
  }

  // Paragraph refinement removed (unused)

  function enterEditMode() {
    setEditContent(content);
    setEditMode(true);
    // Check for existing auto-saves and offer to restore
    if (!expanded) return;
    try {
      const prefix = `auto-save-${novelId}-${expanded}-`;
      const saves: { key: string; content: string; timestamp: number }[] = [];
      for (let i = 0; i < localStorage.length; i++) {
        const key = localStorage.key(i);
        if (key && key.startsWith(prefix)) {
          const val = localStorage.getItem(key);
          if (val) {
            const ts = parseInt(key.replace(prefix, ''), 10);
            if (!isNaN(ts)) saves.push({ key, content: val, timestamp: ts });
          }
        }
      }
      if (saves.length > 0) {
        saves.sort((a, b) => b.timestamp - a.timestamp);
        const latest = saves[0];
        const timeAgo = Date.now() - latest.timestamp;
        const agoStr = timeAgo < 60000 ? '刚刚'
          : timeAgo < 3600000 ? `${Math.floor(timeAgo / 60000)} 分钟前`
          : `${Math.floor(timeAgo / 3600000)} 小时前`;
        if (confirm(`检测到未保存的草稿（${agoStr}），是否恢复？`)) {
          setEditContent(latest.content);
          toast.success('已恢复自动保存的草稿');
        }
      }
    } catch { /* skip auto-save restore on error */ }
  }

  function saveNotes() {
    if (!expanded) return;
    const updated = { ...notes, [expanded]: noteInput };
    setNotes(updated);
    localStorage.setItem(`chapter-notes-${novelId}`, JSON.stringify(updated));
    toast.success('笔记已保存');
  }

  // Load notes when chapter expands
  useEffect(() => {
    if (expanded) setNoteInput(notes[expanded] || '');
  }, [expanded]);

  // Batch select mode
  const [selectMode, setSelectMode] = useState(false);
  const [selected, setSelected] = useState<Set<number>>(new Set());

  // Quick feedback regenerate
  const [feedbackInput, setFeedbackInput] = useState('');
  const [regenerating, setRegenerating] = useState(false);
  const [rewriteFocus, setRewriteFocus] = useState('');
  // Chapter notes
  const [notes, setNotes] = useState<Record<number, string>>(() => {
    try { return JSON.parse(localStorage.getItem(`chapter-notes-${novelId}`) || '{}'); }
    catch { return {}; }
  });
  const [noteInput, setNoteInput] = useState('');
  // Style reference chapters (gold standard)
  const [styleRefs, setStyleRefs] = useState<Set<number>>(() => {
    try { return new Set(JSON.parse(localStorage.getItem(`style-refs-${novelId}`) || '[]')); }
    catch { return new Set(); }
  });
  // Chapter tags
  const [chapterTags, setChapterTags] = useState<Record<number, string[]>>(() => {
    try { return JSON.parse(localStorage.getItem(`chapter-tags-${novelId}`) || '{}'); }
    catch { return {}; }
  });
  const [tagPickerChapter, setTagPickerChapter] = useState<number | null>(null);

  useEffect(() => {
    fetch(`/api/novels/${novelId}/publish-status`)
      .then(r => r.json())
      .then(d => setPublishedSet(new Set(d.published)))
      .catch(() => {});
  }, [novelId]);

  // Reading progress tracker + continuous reading
  useEffect(() => {
    if (!expanded) { setReadProgress(0); return; }
    const el = document.querySelector(`[data-chapter-content="${expanded}"]`);
    if (!el) return;
    let triggeredNext = false;
    const handler = () => {
      const { scrollTop, scrollHeight, clientHeight } = el;
      setReadProgress(Math.round((scrollTop / (scrollHeight - clientHeight)) * 100));
      // Auto-load next chapter when scrolled to bottom
      if (scrollTop + clientHeight >= scrollHeight - 50 && !triggeredNext) {
        triggeredNext = true;
        const nextCh = chapters.find(c => c.number === expanded + 1 && c.word_count > 0);
        if (nextCh) {
          toast.info(`正在加载第${nextCh.number}章...`, { duration: 1500 });
          setTimeout(() => toggleChapter(nextCh.number), 500);
        }
      }
    };
    el.addEventListener('scroll', handler, { passive: true });
    return () => el.removeEventListener('scroll', handler);
  }, [expanded]);

  // Ctrl+F for chapter search
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'f' && expanded) {
        e.preventDefault();
        setSearchVisible(prev => !prev);
        setSearchTerm('');
      }
      if (e.key === 'Escape' && searchVisible) {
        setSearchVisible(false);
        setSearchTerm('');
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [expanded, searchVisible]);

  // Reset select mode when chapters change (e.g. after generation)
  useEffect(() => {
    setSelectMode(false);
    setSelected(new Set());
  }, [chapters.length]);

  // Auto-save timer: periodic snapshots while editMode is active
  useEffect(() => {
    if (!editMode || !expanded) return;
    const saveSnapshot = () => {
      const currentContent = editContentRef.current;
      if (!currentContent) return;
      try {
        const now = Date.now();
        const key = `auto-save-${novelId}-${expanded}-${now}`;
        localStorage.setItem(key, currentContent);

        // Enforce max auto-saves per chapter: keep latest 10, delete oldest
        const prefix = `auto-save-${novelId}-${expanded}-`;
        const allKeys: { key: string; ts: number }[] = [];
        for (let i = 0; i < localStorage.length; i++) {
          const k = localStorage.key(i);
          if (k && k.startsWith(prefix)) {
            const ts = parseInt(k.replace(prefix, ''), 10);
            if (!isNaN(ts)) allKeys.push({ key: k, ts });
          }
        }
        if (allKeys.length > MAX_AUTO_SAVES) {
          allKeys.sort((a, b) => a.ts - b.ts); // oldest first
          const toDelete = allKeys.slice(0, allKeys.length - MAX_AUTO_SAVES);
          for (const item of toDelete) {
            localStorage.removeItem(item.key);
          }
        }
        toast('💾 已自动保存', { description: `第${expanded}章快照已保存`, duration: 2000 });
      } catch { /* localStorage may be full */ }
    };
    const timer = setInterval(saveSnapshot, AUTO_SAVE_INTERVAL_MS);
    // Save once after 2s on first enter
    const initialTimer = setTimeout(saveSnapshot, 2000);
    return () => {
      clearInterval(timer);
      clearTimeout(initialTimer);
    };
  }, [editMode, expanded, novelId]);

  // Auto-scroll to last-read chapter on mount, or auto-expand from MiniPlayer
  useEffect(() => {
    if (chapters.length === 0) return;
    try {
      const autoExpand = sessionStorage.getItem(`auto-expand-${novelId}`);
      if (autoExpand) {
        const num = parseInt(autoExpand);
        sessionStorage.removeItem(`auto-expand-${novelId}`);
        const target = chapters.find(c => c.number === num);
        if (target) {
          setTimeout(() => toggleChapter(num), 400);
          setTimeout(() => {
            document.querySelector(`[data-chapter="${num}"]`)?.scrollIntoView({ block: 'center', behavior: 'smooth' });
          }, 600);
          return;
        }
      }
      const lastRead = JSON.parse(localStorage.getItem(`last-read-${novelId}`) || 'null');
      if (lastRead?.chapter) {
        setTimeout(() => {
          document.querySelector(`[data-chapter="${lastRead.chapter}"]`)?.scrollIntoView({ block: 'center', behavior: 'smooth' });
        }, 300);
      }
    } catch {}
  }, [novelId, chapters.length]);

  // Derived: sorted chapters (pinned first)
  const sortedChapters = [...chapters].sort((a, b) => {
    const aPinned = pinned.has(a.number) ? 0 : 1;
    const bPinned = pinned.has(b.number) ? 0 : 1;
    if (aPinned !== bPinned) return aPinned - bPinned;
    return a.number - b.number;
  });

  // ---- Virtual scroll ----
  const ROW_HEIGHT = 48;
  const OVERSCAN = 5;
  const [scrollTop, setScrollTop] = useState(0);
  const listRef = useRef<HTMLDivElement>(null);
  const handleListScroll = useCallback((e: React.UIEvent<HTMLDivElement>) => {
    setScrollTop(e.currentTarget.scrollTop);
  }, []);

  const containerHeight = listRef.current?.clientHeight || window.innerHeight * 0.7;
  let startIdx = Math.max(0, Math.floor(scrollTop / ROW_HEIGHT) - OVERSCAN);
  let endIdx = Math.min(
    sortedChapters.length,
    Math.ceil((scrollTop + containerHeight) / ROW_HEIGHT) + OVERSCAN,
  );

  // Always include the expanded chapter so its content area stays rendered
  if (expanded !== null) {
    const expIdx = sortedChapters.findIndex((c) => c.number === expanded);
    if (expIdx !== -1) {
      startIdx = Math.min(startIdx, expIdx);
      endIdx = Math.max(endIdx, expIdx + 1);
    }
  }
  // ---- End virtual scroll ----

  const writableChapters = sortedChapters.filter(c => c.word_count > 0);

  // Detect arcs from chapter titles (第X卷, 第X部, Volume X, Part X)
  interface Arc { label: string; startChapter: number; }
  const arcs: Arc[] = [];
  let currentArc: Arc | null = null;
  for (const ch of sortedChapters) {
    const t = ch.title || '';
    const arcMatch = t.match(/第[一二三四五六七八九十百千\d]+[卷部篇集]/);
    if (arcMatch) {
      if (currentArc) arcs.push(currentArc);
      currentArc = { label: arcMatch[0], startChapter: ch.number };
    }
  }
  if (currentArc) arcs.push(currentArc);

  function toggleArc(label: string) {
    setCollapsedArcs(prev => {
      const next = new Set(prev);
      if (next.has(label)) next.delete(label); else next.add(label);
      return next;
    });
  }

  if (!sortedChapters.length) {
    return (
      <div className="text-center py-20">
        <div className="inline-flex items-center justify-center w-20 h-20 rounded-2xl bg-accent-soft/30 mb-6">
          <span className="text-4xl">📖</span>
        </div>
        <h3 className="font-heading text-xl font-semibold text-ink mb-2">等待第一章</h3>
        <p className="text-sm text-ink-muted mb-2 max-w-sm mx-auto leading-relaxed">
          你的故事从第一章开始。配置灵魂、设计角色，然后让 AI 写出第一页。
        </p>
        <p className="text-xs text-ink-subtle mb-6">
          按 <kbd className="px-1.5 py-0.5 rounded bg-paper border border-border font-mono text-[11px]">Ctrl+G</kbd> 或点击下方按钮
        </p>
        <button onClick={async () => {
          toast.info('正在生成第一章...');
          await fetch(`/api/novels/${novelId}/generate`, { method: 'POST' });
          toast.success('已触发生成');
        }}
          className="inline-flex items-center gap-2 text-sm px-6 py-3 rounded-xl bg-accent text-white hover:bg-accent-hover transition-all font-medium shadow-lg shadow-accent/25 btn-generate active:scale-95">
          ✨ 开始创作第一章
        </button>
      </div>
    );
  }

  async function toggleChapter(n: number) {
    if (selectMode) {
      toggleSelect(n);
      return;
    }
    if (expanded === n) {
      const el = document.querySelector(`[data-chapter-content="${n}"]`);
      if (el) localStorage.setItem(`read-pos-${novelId}-${n}`, String(el.scrollTop));
      setExpanded(null); setContent(''); return;
    }
    // Auto-collapse previous chapter for clean reading
    if (expanded !== null) {
      const prevEl = document.querySelector(`[data-chapter-content="${expanded}"]`);
      if (prevEl) localStorage.setItem(`read-pos-${novelId}-${expanded}`, String(prevEl.scrollTop));
    }
    setExpanded(n); setContent(''); setLoadingContent(true);
    // Save last-read chapter
    const ch = chapters.find(c => c.number === n);
    localStorage.setItem(`last-read-${novelId}`, JSON.stringify({ chapter: n, title: ch?.title || '', timestamp: Date.now() }));
    // Track as read
    try {
      const read = JSON.parse(localStorage.getItem(`read-chapters-${novelId}`) || '[]');
      if (!read.includes(n)) { read.push(n); localStorage.setItem(`read-chapters-${novelId}`, JSON.stringify(read)); }
    } catch {}
    // Scroll chapter row into view
    setTimeout(() => {
      document.querySelector(`[data-chapter="${n}"]`)?.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    }, 50);
    try {
      const data = await api.novels.chapter(novelId, n);
      setContent(data.content || '(暂无正文)');
    } catch { setContent('正文尚未生成'); }
    finally {
      setLoadingContent(false);
      // Restore reading position
      setTimeout(() => {
        const saved = localStorage.getItem(`read-pos-${novelId}-${n}`);
        const el = document.querySelector(`[data-chapter-content="${n}"]`);
        if (saved && el) el.scrollTop = parseInt(saved) || 0;
      }, 150);
    }
  }

  function toggleSelect(n: number) {
    setSelected(prev => {
      const next = new Set(prev);
      if (next.has(n)) next.delete(n); else next.add(n);
      return next;
    });
  }

  function toggleStyleRef(n: number, e?: React.MouseEvent) {
    e?.stopPropagation();
    setStyleRefs(prev => {
      const next = new Set(prev);
      if (next.has(n)) next.delete(n); else next.add(n);
      localStorage.setItem(`style-refs-${novelId}`, JSON.stringify([...next]));
      return next;
    });
    toast.success(styleRefs.has(n) ? '已取消风格参考' : '已设为风格参考——后续生成将以本章为质量标杆');
  }

  // Chapter tag operations
  function saveTags(tags: Record<number, string[]>) {
    setChapterTags(tags);
    localStorage.setItem(`chapter-tags-${novelId}`, JSON.stringify(tags));
  }

  function toggleTag(chapterNum: number, tag: string) {
    setChapterTags(prev => {
      const current = prev[chapterNum] || [];
      const next = current.includes(tag)
        ? current.filter(t => t !== tag)
        : [...current, tag];
      const updated = { ...prev, [chapterNum]: next };
      if (next.length === 0) delete updated[chapterNum];
      localStorage.setItem(`chapter-tags-${novelId}`, JSON.stringify(updated));
      return updated;
    });
  }

  function openTagPicker(chapterNum: number) {
    setTagPickerChapter(chapterNum);
  }

  // Close tag picker on click outside or scroll
  useEffect(() => {
    if (tagPickerChapter === null) return;
    const handler = () => setTagPickerChapter(null);
    const timer = setTimeout(() => document.addEventListener('click', handler), 0);
    window.addEventListener('scroll', handler, true);
    return () => {
      clearTimeout(timer);
      document.removeEventListener('click', handler);
      window.removeEventListener('scroll', handler, true);
    };
  }, [tagPickerChapter]);

  function togglePin(n: number, e?: React.MouseEvent) {
    e?.stopPropagation();
    setPinned(prev => {
      const next = new Set(prev);
      if (next.has(n)) next.delete(n); else next.add(n);
      localStorage.setItem(`pinned-${novelId}`, JSON.stringify([...next]));
      return next;
    });
  }

  function toggleSelectAll() {
    if (selected.size === chapters.length) {
      setSelected(new Set());
    } else {
      setSelected(new Set(chapters.map(c => c.number)));
    }
  }

  async function batchHumanize() {
    const nums = [...selected];
    toast.info(`正在对 ${nums.length} 章去AI味...`);
    for (const n of nums) {
      await fetch(`/api/novels/${novelId}/chapters/${n}/humanize`, { method: 'POST' });
    }
    toast.success(`${nums.length} 章已触发去AI味`);
    setSelectMode(false); setSelected(new Set());
  }

  async function batchFactCheck() {
    const nums = [...selected];
    toast.info(`正在核查 ${nums.length} 章...`);
    let totalIssues = 0;
    for (const n of nums) {
      try {
        const r = await fetch(`/api/novels/${novelId}/chapters/${n}/fact-check`);
        const d = await r.json();
        totalIssues += d.issues?.length || 0;
      } catch { /* skip */ }
    }
    toast.success(`核查完成：${nums.length} 章共 ${totalIssues} 个疑点`);
    setSelectMode(false); setSelected(new Set());
  }

  async function handleProofread() {
    if (!expanded) return;
    setProofreading(true);
    setProofreadIssues([]);
    try {
      const r = await fetch(`/api/novels/${novelId}/chapters/${expanded}/proofread`, { method: 'POST' });
      const d = await r.json();
      setProofreadIssues(d.issues || []);
      setShowProofread(true);
      if ((d.issues || []).length === 0) {
        toast.success('校对完成，未发现问题');
      } else {
        toast.success(`校对完成: ${d.issues.length} 处问题`);
      }
    } catch (e: unknown) {
      toast.error('校对失败: ' + (e as Error).message);
    } finally {
      setProofreading(false);
    }
  }

  async function handleAnalyze() {
    if (!expanded || !content) return;
    setAnalyzing(true);
    try {
      const r = await fetch('/api/text/analyze', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({text: content}),
      });
      setAnalysisResult(await r.json());
    } catch { toast.error('分析失败'); }
    finally { setAnalyzing(false); }
  }

  async function handleReversePolish() {
    if (!expanded || !content) return;
    setPolishing(true);
    setPolishedText('');
    try {
      const r = await fetch(`/api/novels/${novelId}/chapters/${expanded}/polish-reverse`, { method: 'POST' });
      const d = await r.json();
      setPolishedText(d.polished);
      toast.success(`克制编辑完成: ${d.original_length} → ${d.polished_length} 字`);
    } catch (e: unknown) {
      toast.error('克制编辑失败: ' + (e as Error).message);
    } finally {
      setPolishing(false);
    }
  }

  async function handleRegenerate() {
    if (!expanded || !feedbackInput.trim()) return;
    // Save current version before regenerating
    if (content && content !== '正文尚未生成') {
      try {
        const versions = JSON.parse(localStorage.getItem(`chapter-versions-${novelId}`) || '{}');
        if (!versions[String(expanded)]) versions[String(expanded)] = [];
        versions[String(expanded)].push({ content, timestamp: Date.now() });
        if (versions[String(expanded)].length > 5) versions[String(expanded)].shift();
        localStorage.setItem(`chapter-versions-${novelId}`, JSON.stringify(versions));
        toast.success('旧版本已保存（最多保留5个）');
      } catch {}
    }
    setRegenerating(true);
    try {
      const focusHint = rewriteFocus
        ? `\\n重点改进${rewriteFocus}。`
        : '';
      const dir = `重写第${expanded}章。作者反馈：${feedbackInput.trim()}。${focusHint}保持原有剧情主线，但改进指出的问题。`;
      await fetch(`/api/novels/${novelId}/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ direction: dir, quality_threshold: 0.65 }),
      });
      toast.success(`第${expanded}章重新生成已触发`);
      setFeedbackInput('');
      setRewriteFocus('');
      setExpanded(null);
      onRegenerate?.(expanded, feedbackInput.trim());
    } catch (e: unknown) {
      toast.error('重新生成失败: ' + (e as Error).message);
    } finally {
      setRegenerating(false);
    }
  }

  function readingTime(words: number): string {
    if (words < 500) return '<1min';
    const mins = Math.round(words / 400); // Chinese reading speed ~400 chars/min
    return mins >= 60 ? `${Math.floor(mins/60)}h${mins%60}m` : `${mins}min`;
  }

  function dialogueRatio(ch: ChapterMeta): { pct: number; label: string; color: string } | null {
    const s = ch.summary || '';
    if (!s || s.length < 10) return null;
    const markers = (s.match(/[「「""''“”说问道答讲喊叫骂吵]/g) || []).length;
    const ratio = Math.round((markers / Math.min(s.length, 200)) * 100);
    if (ratio > 10) return { pct: 80, label: '🗣️', color: 'text-sky-500' };
    if (ratio > 4) return { pct: 50, label: '📝', color: 'text-ink-muted' };
    return { pct: 25, label: '📖', color: 'text-amber-500' };
  }

  return (
    <div>
      {/* Batch mode toggle + quick jump + next unread */}
      <div className="flex items-center gap-2 mb-2">
        {/* Jump to latest */}
        {!selectMode && writableChapters.length > 0 && (
          <button onClick={() => {
            const latest = writableChapters[writableChapters.length - 1];
            document.querySelector(`[data-chapter="${latest.number}"]`)?.scrollIntoView({ block: 'center', behavior: 'smooth' });
          }}
            className="text-[10px] px-2 py-1 rounded border border-border text-ink-muted hover:text-ink transition-colors">
            ↓ 最新
          </button>
        )}

        {/* Attention filter */}
        <button onClick={() => setAttentionFilter(!attentionFilter)}
          className={`text-[10px] px-2 py-1 rounded border transition-colors ${
            attentionFilter ? 'bg-amber-50 text-amber-600 border-amber-200 dark:bg-amber-950/20 dark:text-amber-400 dark:border-amber-800' : 'border-border text-ink-muted hover:text-ink'
          }`}>
          {attentionFilter ? '🔍 只看需关注' : '🔍 需关注'}
        </button>

        {/* Jump to next unread */}
        {!selectMode && writableChapters.length > 0 && (() => {
          try {
            const read: number[] = JSON.parse(localStorage.getItem(`read-chapters-${novelId}`) || '[]');
            const firstUnread = writableChapters.find(c => !read.includes(c.number));
            if (!firstUnread) return null;
            return (
              <button onClick={() => {
                document.querySelector(`[data-chapter="${firstUnread.number}"]`)?.scrollIntoView({ block: 'center', behavior: 'smooth' });
              }}
                className="text-[10px] px-2 py-1 rounded border border-border text-ink-muted hover:text-ink transition-colors">
                📖 下一未读 (Ch{firstUnread.number})
              </button>
            );
          } catch { return null; }
        })()}
        {/* Quick chapter jump */}
        {!selectMode && writableChapters.length > 0 && (
          <form onSubmit={e => {
            e.preventDefault();
            const input = (e.target as HTMLFormElement).querySelector('input');
            const num = parseInt(input?.value || '');
            if (num && chapters.find(c => c.number === num)) {
              toggleChapter(num);
              input!.value = '';
            }
          }} className="flex items-center gap-1 ml-auto">
            <span className="text-[10px] text-ink-subtle">跳至</span>
            <input
              type="number" min={1} max={chapters.length}
              placeholder={`1-${sortedChapters.length}`}
              className="w-14 text-[10px] rounded border border-input bg-card px-1.5 py-0.5 text-center
                placeholder:text-ink-subtle focus:outline-none focus:border-accent" />
          </form>
        )}
        <button
          onClick={() => { setSelectMode(!selectMode); setSelected(new Set()); }}
          className={`text-[11px] px-2 py-1 rounded border transition-colors ${
            selectMode
              ? 'bg-accent-soft text-accent border-accent/30'
              : 'border-border text-ink-muted hover:text-ink'
          }`}>
          {selectMode ? '✕ 退出选择' : '☐ 批量操作'}
        </button>
        {selectMode && (
          <span className="text-[10px] text-ink-muted">
            已选 {selected.size} / {writableChapters.length} 章
            <button onClick={toggleSelectAll} className="ml-2 text-accent hover:underline">
              {selected.size === writableChapters.length ? '取消全选' : '全选'}
            </button>
          </span>
        )}
      </div>

      <div ref={listRef} className="max-h-[70vh] overflow-y-auto" onScroll={handleListScroll}>
        {/* Top spacer for virtual scroll */}
        <div style={{ height: startIdx * ROW_HEIGHT }} />
        {sortedChapters.slice(startIdx, endIdx).map((ch) => {
        // Check if this chapter starts a new arc
        const arc = arcs.find(a => a.startChapter === ch.number);
        const prevArc = arcs.find(a => a.startChapter <= ch.number && arcs[arcs.indexOf(a) + 1]?.startChapter > ch.number) || arcs[arcs.length - 1];
        const isArcStart = arc !== undefined;
        const arcLabel = isArcStart ? arc!.label : (prevArc && prevArc.startChapter < ch.number ? prevArc.label : null);
        const arcCollapsed = arcLabel ? collapsedArcs.has(arcLabel) : false;

        // If this chapter belongs to a collapsed arc, hide it
        if (arcCollapsed && !isArcStart) return null;
        // Attention filter: show only chapters with low quality or marked for revision
        if (attentionFilter && ch.word_count > 0) {
          const needsAttention = (ch.quality_score && ch.quality_score < 0.7) || approvals[ch.number] === 'revise';
          if (!needsAttention) return null;
        }
        const ctxItems = [
          { icon: '✏️', label: '编辑', onClick: () => {
            toggleChapter(ch.number);
            setTimeout(() => enterEditMode(), 500);
          }},
          { icon: '🔄', label: '重写本章', onClick: () => {
            if (onRegenerate) {
              setExpanded(ch.number);
              setFeedbackInput('');
              setRewriteFocus('');
            }
          }},
          { icon: '⭐', label: styleRefs.has(ch.number) ? '取消风格参考' : '设为风格参考', onClick: () => toggleStyleRef(ch.number) },
          { icon: '🧹', label: '去AI味', onClick: async () => {
            toast.success('已触发去AI味');
            await fetch(`/api/novels/${novelId}/chapters/${ch.number}/humanize`, { method: 'POST' });
          }},
          { icon: '🔍', label: '事实核查', onClick: async () => {
            const r = await fetch(`/api/novels/${novelId}/chapters/${ch.number}/fact-check`);
            const d = await r.json();
            toast.success(`核查: ${d.issues?.length || 0} 疑点`);
          }},
          { icon: '⬇', label: '导出 TXT', onClick: () => {
            window.open(`/api/novels/${novelId}/chapters/${ch.number}/export`, '_blank');
          }},
          { icon: '📌', label: pinned.has(ch.number) ? '取消置顶' : '置顶', onClick: () => togglePin(ch.number) },
          { icon: '🏷️', label: '标签', onClick: () => openTagPicker(ch.number) },
          { icon: `${approvals[ch.number] === 'approved' ? '✅' : approvals[ch.number] === 'revise' ? '🔧' : '📝'}`, label: approvals[ch.number] === 'approved' ? '已审' : approvals[ch.number] === 'revise' ? '待改→草稿' : '草稿→已审', onClick: () => cycleApproval(ch.number) },
          ...(onDelete ? [{
            icon: '🗑', label: '删除本章', danger: true as const,
            onClick: () => onDelete(ch.number),
          }] : []),
        ];
        return (
        <div key={ch.number}>
          {/* Arc header */}
          {isArcStart && arc && (
            <div className="flex items-center gap-2 px-4 py-2 mt-3 first:mt-0 bg-muted/30 rounded-md border border-border cursor-pointer hover:bg-muted/50 transition-colors"
              onClick={() => toggleArc(arc.label)}>
              <span className={`text-xs transition-transform ${collapsedArcs.has(arc.label) ? '' : 'rotate-90'}`}>▸</span>
              <span className="text-xs font-semibold text-ink">{arc.label}</span>
              <span className="text-[10px] text-ink-subtle ml-auto">
                {collapsedArcs.has(arc.label) ? '已折叠' : `${sortedChapters.filter(c => {
                  const a = arcs.find(a2 => a2.startChapter <= c.number);
                  return a && a.label === arc.label;
                }).length} 章`}
              </span>
            </div>
          )}
          <ContextMenu items={ctxItems}>
          <div onClick={() => toggleChapter(ch.number)}
            data-chapter={ch.number}
            className={`flex items-center px-3 sm:px-4 py-3 gap-2 sm:gap-3.5 rounded-md cursor-pointer transition-all duration-150 hover:bg-paper group relative flex-wrap sm:flex-nowrap ${
              selected.has(ch.number) ? 'bg-accent-soft/50 ring-1 ring-accent/20' : ''
            } ${
              expanded === ch.number && !selectMode ? 'bg-paper border-l-[3px] border-l-accent rounded-l-none' : 'border-l-[3px] border-l-transparent'
            }`}>
            {/* Hover preview tooltip */}
            {ch.summary && !expanded && (
              <div className="absolute left-4 right-4 -top-1 z-20 opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none">
                <div className="bg-ink text-white dark:text-black text-[11px] rounded-lg px-3 py-2 shadow-xl leading-relaxed max-w-md">
                  {ch.summary.slice(0, 100)}{ch.summary.length > 100 ? '...' : ''}
                  <div className="text-[9px] text-white/50 mt-1">{ch.word_count.toLocaleString()}字 · {ch.ending_hook ? '🎣 ' + ch.ending_hook.slice(0, 30) : '无钩子'}</div>
                </div>
              </div>
            )}
            {/* Checkbox in select mode */}
            {selectMode && (
              <span onClick={e => { e.stopPropagation(); toggleSelect(ch.number); }}
                className={`shrink-0 w-4 h-4 rounded border-2 flex items-center justify-center text-[10px] transition-colors ${
                  selected.has(ch.number)
                    ? 'bg-accent border-accent text-white'
                    : 'border-border hover:border-accent/40'
                }`}>
                {selected.has(ch.number) ? '✓' : ''}
              </span>
            )}
            {/* Pin toggle */}
            <button onClick={e => togglePin(ch.number, e)}
              className={`text-[10px] shrink-0 transition-all ${
                pinned.has(ch.number) ? 'text-amber-500' : 'text-ink-subtle opacity-0 group-hover:opacity-100'
              }`}
              title={pinned.has(ch.number) ? '取消置顶' : '置顶'}>
              📌
            </button>
            {/* Style reference toggle */}
            {ch.word_count > 0 && (
              <button onClick={e => toggleStyleRef(ch.number, e)}
                className={`text-[10px] shrink-0 transition-all ${
                  styleRefs.has(ch.number) ? 'text-accent' : 'text-ink-subtle opacity-0 group-hover:opacity-100'
                }`}
                title={styleRefs.has(ch.number) ? '取消风格参考' : '设为风格参考——后续生成将参考本章质量'}>
                {styleRefs.has(ch.number) ? '⭐' : '☆'}
              </button>
            )}
            {/* Approval toggle */}
            <button onClick={e => cycleApproval(ch.number, e)}
              className={`text-[10px] shrink-0 transition-all ${
                approvals[ch.number] === 'approved' ? 'text-emerald-500'
                : approvals[ch.number] === 'revise' ? 'text-amber-500'
                : 'text-ink-subtle opacity-0 group-hover:opacity-100'
              }`}
              title={approvals[ch.number] === 'approved' ? '已审 → 点击切换待改' : approvals[ch.number] === 'revise' ? '待改 → 点击切换草稿' : '草稿 → 点击切换已审'}>
              {approvals[ch.number] === 'approved' ? '✅' : approvals[ch.number] === 'revise' ? '🔧' : '○'}
            </button>
            {/* Read status dot */}
            {(() => {
              try {
                const read = JSON.parse(localStorage.getItem(`read-chapters-${novelId}`) || '[]');
                if (read.includes(ch.number)) {
                  return <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 shrink-0" title="已读" />;
                }
              } catch {}
              return <span className="w-1.5 h-1.5 rounded-full bg-border shrink-0" title="未读" />;
            })()}
            {/* Opening strength indicator */}
            {ch.word_count > 0 && (() => {
              const openingScore = ch.quality_score ? Math.min(100, Math.round(ch.quality_score * 100 + (ch.word_count > 2000 ? 10 : -10))) : null;
              if (openingScore === null) return null;
              return (
                <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${
                  openingScore >= 80 ? 'bg-emerald-400' : openingScore >= 60 ? 'bg-amber-400' : 'bg-red-400'
                }`} title={`开头力度: ${openingScore}`} />
              );
            })()}
            <span className="text-xs text-ink-subtle tabular-nums min-w-[52px]">第{ch.number}章</span>
            <span className="flex-1 text-sm font-medium truncate">{ch.title}</span>
            {/* Notes indicator */}
            {notes[ch.number] && (
              <span className="text-[10px] text-amber-500 shrink-0" title={`笔记: ${notes[ch.number].slice(0, 50)}`}>📝</span>
            )}
            {ch.word_count > 0 && (
              <span className="text-[10px] text-ink-subtle shrink-0 hidden sm:inline" title="预计阅读时间">
                🕐 {readingTime(ch.word_count)}
              </span>
            )}
            <span className="text-[11px] text-ink-subtle tabular-nums shrink-0">{ch.word_count.toLocaleString()}字</span>
            {/* Model badge */}
            {ch.model_used && ch.word_count > 0 && (
              <span className="text-[9px] text-ink-subtle bg-paper px-1 py-0.5 rounded shrink-0 hidden md:inline"
                title={`生成模型: ${ch.model_used}`}>
                {ch.model_used.replace('deepseek', 'DS').replace('gpt-4o', 'GPT4').replace('claude', 'CL').slice(0, 6)}
              </span>
            )}
            {/* Dialogue ratio indicator */}
            {ch.word_count > 0 && dialogueRatio(ch) && (
              <span className={`text-[10px] shrink-0 ${dialogueRatio(ch)!.color}`} title={`对话占比: ${dialogueRatio(ch)!.label}`}>
                {dialogueRatio(ch)!.label}
              </span>
            )}
            {/* Chapter tags */}
            {(chapterTags[ch.number] || []).map(tag => {
              const tagInfo = TAG_OPTIONS.find(t => t.key === tag);
              if (!tagInfo) return null;
              return (
                <span key={tag}
                  className={`text-[9px] px-1 py-0.5 rounded border shrink-0 ${tagInfo.color}`}
                  title={`标签: ${tag}`}>
                  {tagInfo.emoji}
                </span>
              );
            })}
            {publishedSet.has(ch.number) ? (
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-50 text-emerald-700 border border-emerald-200 dark:bg-emerald-900/30 dark:text-emerald-400 dark:border-emerald-800 font-semibold shrink-0">✅ 已发布</span>
            ) : (
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-gray-50 text-gray-400 border border-gray-200 dark:bg-gray-800 dark:text-gray-500 dark:border-gray-700 shrink-0">⏳ 未发布</span>
            )}
            {ch.quality_score !== undefined && (
              <span className={`text-[10px] px-1.5 py-0.5 rounded border font-semibold tabular-nums shrink-0 ${GRADE_COLORS[gradeForScore(ch.quality_score)] || ''}`}>
                {gradeForScore(ch.quality_score)} {ch.quality_score.toFixed(2)}
              </span>
            )}
            {/* Version history badge */}
            {ch.word_count > 0 && (() => {
              try {
                const versions = JSON.parse(localStorage.getItem(`chapter-versions-${novelId}`) || '{}');
                const chVersions = versions[String(ch.number)];
                if (chVersions && chVersions.length > 0) {
                  return (
                    <button
                      onClick={e => { e.stopPropagation(); toggleChapter(ch.number); }}
                      className="text-[10px] px-1.5 py-0.5 rounded bg-purple-50 text-purple-600 border border-purple-200 dark:bg-purple-900/30 dark:text-purple-400 dark:border-purple-800 font-semibold shrink-0 hover:bg-purple-100 dark:hover:bg-purple-900/50 transition-colors"
                      title={`${chVersions.length} 个历史版本`}
                    >
                      📜 {chVersions.length}
                    </button>
                  );
                }
              } catch {}
              return null;
            })()}
            {/* Per-chapter actions on hover (hidden in select mode) */}
            {!selectMode && (
              <span className="hidden group-hover:flex gap-1 ml-auto shrink-0">
                <button onClick={async e => { e.stopPropagation(); toast.success('已触发去AI味'); await fetch(`/api/novels/${novelId}/chapters/${ch.number}/humanize`,{method:'POST'}); }}
                  className="text-[10px] text-ink-muted hover:text-accent px-1" title="去AI味">🧹</button>
                <button onClick={async e => { e.stopPropagation(); const r=await fetch(`/api/novels/${novelId}/chapters/${ch.number}/fact-check`); const d=await r.json(); toast.success(`核查:${d.issues?.length||0}疑点`); }}
                  className="text-[10px] text-ink-muted hover:text-accent px-1" title="事实核查">🔍</button>
                <a href={`/api/novels/${novelId}/chapters/${ch.number}/export`} onClick={e => e.stopPropagation()}
                  className="text-[10px] text-ink-muted hover:text-accent px-1">⬇</a>
                {onDelete && (
                  <button onClick={e => { e.stopPropagation(); onDelete(ch.number); }}
                    className="text-[10px] text-ink-muted hover:text-red-500 px-1">🗑</button>
                )}
              </span>
            )}
            <span className="text-sm text-ink-subtle shrink-0">{expanded === ch.number ? '⌄' : '›'}</span>
          </div>
          </ContextMenu>
          {expanded === ch.number && (
            <div
              data-chapter-content={ch.number}
              className={`${focusMode ? 'fixed inset-0 z-50 bg-paper overflow-y-auto' : 'mx-4 mb-3'} reading-mode bg-card border border-border rounded-lg chapter-content`}>
              {/* Reading progress bar */}
              {!focusMode && (
                <div className="reading-progress -mx-[1.5rem] -mt-[3rem] mb-6">
                  <div className="reading-progress-fill" style={{ width: `${Math.min(100, readProgress)}%` }} />
                </div>
              )}

              {/* Inline search */}
              {searchVisible && (
                <div className="flex items-center gap-2 mb-3 -mx-2 px-2 py-1.5 bg-paper rounded-md border border-border">
                  <span className="text-xs text-ink-subtle">🔍</span>
                  <input
                    value={searchTerm}
                    onChange={e => setSearchTerm(e.target.value)}
                    placeholder="在章节中搜索..."
                    autoFocus
                    onKeyDown={e => e.stopPropagation()}
                    className="flex-1 text-xs bg-transparent outline-none placeholder:text-ink-subtle" />
                  {searchTerm && (
                    <span className="text-[10px] text-ink-subtle tabular-nums">
                      {(content.match(new RegExp(searchTerm.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'gi')) || []).length} 处匹配
                    </span>
                  )}
                  <button onClick={() => { setSearchVisible(false); setSearchTerm(''); }}
                    className="text-xs text-ink-muted hover:text-ink">✕</button>
                </div>
              )}

              {focusMode && (
                <button onClick={e => { e.stopPropagation(); setFocusMode(false); }}
                  className="fixed top-4 right-4 text-xs text-ink-muted hover:text-ink bg-card border border-border rounded-full px-3 py-1.5 shadow-lg z-50">
                  ✕ 退出专注模式
                </button>
              )}
              <div className="flex items-center gap-3 mb-3 flex-wrap">
                <button onClick={e => { e.stopPropagation(); setFocusMode(!focusMode); }}
                  className="text-[10px] text-ink-subtle hover:text-accent">
                  {focusMode ? '' : '📖 专注阅读'}
                </button>
                <span className="text-[10px] text-ink-subtle">|</span>
                <button onClick={e => {
                  e.stopPropagation();
                  navigator.clipboard.writeText(content).then(() => toast.success('已复制全文'));
                }}
                  className="text-[10px] text-ink-subtle hover:text-accent">
                  📋 复制
                </button>
                <span className="text-[10px] text-ink-subtle">|</span>
                <button onClick={e => {
                  e.stopPropagation();
                  if ('speechSynthesis' in window) {
                    const utter = new SpeechSynthesisUtterance(content.replace(/[#*\->]/g, ''));
                    utter.lang = 'zh-CN';
                    utter.rate = 0.9;
                    speechSynthesis.cancel();
                    speechSynthesis.speak(utter);
                    toast.success('正在朗读...');
                  } else {
                    toast.error('浏览器不支持朗读');
                  }
                }}
                  className="text-[10px] text-ink-subtle hover:text-accent">
                  🔊 朗读
                </button>
                <span className="text-[10px] text-ink-subtle">|</span>
                <span className="text-[10px] text-ink-subtle">|</span>
                <button onClick={e => { e.stopPropagation(); setMobileChapter(ch.number); }}
                  className="text-[10px] text-ink-subtle hover:text-accent">
                  📱 手机预览
                </button>
                <span className="text-[10px] text-ink-subtle">|</span>
                {editMode ? (
                  <>
                    <button onClick={e => { e.stopPropagation(); saveEdit(); }} disabled={saving}
                      className="text-[10px] text-emerald-500 hover:text-emerald-600 font-medium">
                      {saving ? '保存中...' : '💾 保存'}
                    </button>
                    <span className="text-[10px] text-ink-subtle">|</span>
                    <button onClick={e => { e.stopPropagation(); setEditMode(false); }}
                      className="text-[10px] text-ink-subtle hover:text-ink">
                      取消
                    </button>
                  </>
                ) : (
                  <button onClick={e => { e.stopPropagation(); enterEditMode(); }}
                    className="text-[10px] text-ink-subtle hover:text-accent">
                    ✏️ 编辑
                  </button>
                )}
                <span className="text-[10px] text-ink-subtle">|</span>
                {content && (
                  <button onClick={e => { e.stopPropagation(); setSceneView(!sceneView); }}
                    className={`text-[10px] transition-colors ${sceneView ? 'text-accent font-medium' : 'text-ink-subtle hover:text-accent'}`}>
                    🎬 场景
                  </button>
                )}
                {content && <span className="text-[10px] text-ink-subtle">|</span>}
                {content && (
                  <button onClick={e => { e.stopPropagation(); handleReversePolish(); }}
                    disabled={polishing}
                    className="text-[10px] text-ink-subtle hover:text-accent disabled:opacity-50">
                    {polishing ? '⏳ 删减中...' : '✂️ 克制'}
                  </button>
                )}
                <span className="text-[10px] text-ink-subtle">|</span>
                {content && (
                  <button onClick={e => { e.stopPropagation(); handleProofread(); }}
                    disabled={proofreading}
                    className="text-[10px] text-ink-subtle hover:text-accent disabled:opacity-50">
                    {proofreading ? '⏳ 校对中...' : '🔍 校对'}
                  </button>
                )}
                <span className="text-[10px] text-ink-subtle">|</span>
                {content && content !== '正文尚未生成' && (
                  <button onClick={e => { e.stopPropagation(); setShowWordFreq(!showWordFreq); }}
                    className={`text-[10px] transition-colors ${showWordFreq ? 'text-accent font-medium' : 'text-ink-subtle hover:text-accent'}`}>
                    📊 词频
                  </button>
                )}
                <span className="text-[10px] text-ink-subtle">|</span>
                {content && content !== '正文尚未生成' && (
                  <button onClick={e => { e.stopPropagation(); handleAnalyze(); }}
                    disabled={analyzing}
                    className="text-[10px] text-ink-subtle hover:text-accent disabled:opacity-50">
                    {analyzing ? '⏳' : '📈'} 分析
                  </button>
                )}
                <span className="text-[10px] text-ink-subtle">|</span>
                <button onClick={e => { e.stopPropagation(); setExpanded(null); }}
                  className="text-[10px] text-ink-subtle hover:text-ink">
                  收起
                </button>
              </div>

              {/* Edit mode: textarea */}
              {editMode ? (
                <textarea
                  value={editContent}
                  onChange={e => setEditContent(e.target.value)}
                  className="w-full min-h-[400px] bg-paper border border-border rounded-lg p-4 text-sm font-[var(--font-editor)] leading-relaxed resize-y
                    focus:outline-none focus:border-accent focus:ring-1 focus:ring-accent/20"
                  onClick={e => e.stopPropagation()}
                  onKeyDown={e => e.stopPropagation()}
                  placeholder="编辑章节内容..." />
              ) : content ? (
                isAudioSyncing ? (
                  <div className="px-2">
                    <div className="flex items-center gap-2 mb-3 text-[10px] text-accent animate-pulse">
                      <span>🔊</span>
                      <span>正在同步朗读 — 当前句子高亮显示</span>
                    </div>
                    <AudioTextSync
                      content={content}
                      positionSec={positionSec}
                      duration={estimatedDuration}
                      isPlaying={isAudioSyncing}
                    />
                  </div>
                ) : (
                  content.split('\n').map((line, i) => {
                    const trimmed = line.trim();
                    if (!trimmed) return <br key={i} />;
                    if (trimmed === '---' || trimmed === '***' || trimmed === '___') return <hr key={i} />;
                    if (trimmed.startsWith('# ')) return <h1 key={i}>{highlightText(trimmed.replace(/^# /, ''), searchTerm)}</h1>;
                    if (trimmed.startsWith('## ')) return <h2 key={i}>{highlightText(trimmed.replace(/^## /, ''), searchTerm)}</h2>;
                    if (trimmed.startsWith('> ')) return <blockquote key={i}><p>{highlightText(trimmed.replace(/^> /, ''), searchTerm)}</p></blockquote>;
                    return <p key={i}>{highlightText(trimmed, searchTerm)}</p>;
                  })
                )
              ) : loadingContent ? (
                <div className="space-y-3 py-4">
                  {[100, 85, 92, 60, 95, 78].map((w, i) => (
                    <div key={i} className="skeleton h-4 rounded" style={{ width: `${w}%`, animationDelay: `${i * 0.1}s` }} />
                  ))}
                </div>
              ) : (
                <div className="text-center py-8 text-ink-muted">加载中...</div>
              )}

              {/* Proofreading Results */}
              {analysisResult && (
                <div className="mt-3 p-3 rounded-lg bg-sky-50/50 dark:bg-sky-950/10 border border-sky-200 dark:border-sky-800 animate-[fadeSlideIn_0.2s_ease-out]">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-[11px] font-semibold text-sky-700 dark:text-sky-400">📈 文本分析</span>
                    <span className="text-[9px] text-ink-subtle">{analysisResult.chars}字 · {analysisResult.sentences}句</span>
                  </div>
                  <div className="grid grid-cols-3 gap-1.5 text-[10px]">
                    {[
                      ['密度', analysisResult.density, '期望/百字'],
                      ['扭转力', analysisResult.forces?.torque, '转折强度'],
                      ['开头', analysisResult.opening?.assessment, '连接强度'],
                      ['体感', analysisResult.body_sense?.total || 0, '视觉+触觉+听觉'],
                      ['视觉', analysisResult.body_sense?.visual || 0, '看/见/望/盯'],
                      ['触觉', analysisResult.body_sense?.tactile || 0, '碰/摸/冷/热/疼'],
                      ['句长', analysisResult.style_fingerprint?.sentence_length, '字/句'],
                      ['对话', analysisResult.style_fingerprint?.dialogue_ratio + '%', '引号占比'],
                      ['描述', analysisResult.style_fingerprint?.description_ratio + '%', '感官描写占比'],
                    ].map(([label, value, hint]) => (
                      <div key={label as string} className="text-center p-1.5 rounded bg-white/50 dark:bg-black/10">
                        <div className="text-ink-subtle text-[9px]">{label}</div>
                        <div className="font-bold text-ink">{String(value)}</div>
                        <div className="text-[8px] text-ink-subtle/50">{hint}</div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
              {polishedText && (
                <div className="mt-3 p-3 rounded-lg bg-purple-50/50 dark:bg-purple-950/10 border border-purple-200 dark:border-purple-800 animate-[fadeSlideIn_0.2s_ease-out]">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-[11px] font-semibold text-purple-700 dark:text-purple-400">
                      ✂️ 克制编辑结果
                    </span>
                    <button onClick={() => {
                      setContent(polishedText);
                      setPolishedText('');
                      toast.success('已应用克制编辑');
                    }}
                      className="text-[10px] text-accent hover:underline">应用</button>
                  </div>
                  <div className="text-[13px] text-ink leading-[2.1] font-[var(--font-editor)] whitespace-pre-wrap max-h-[300px] overflow-y-auto">
                    {polishedText}
                  </div>
                </div>
              )}
              {showProofread && proofreadIssues.length > 0 && (
                <div className="mt-3 p-3 rounded-lg bg-amber-50/50 dark:bg-amber-950/10 border border-amber-200 dark:border-amber-800 animate-[fadeSlideIn_0.2s_ease-out]">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-[11px] font-semibold text-amber-700 dark:text-amber-400">
                      🔍 校对结果 — {proofreadIssues.length} 处问题
                    </span>
                    <button
                      onClick={e => { e.stopPropagation(); setShowProofread(false); setProofreadIssues([]); }}
                      className="text-[10px] text-ink-muted hover:text-ink"
                    >
                      收起
                    </button>
                  </div>
                  <div className="space-y-1.5 max-h-64 overflow-y-auto">
                    {proofreadIssues.map((issue, i) => {
                      const typeLabel = issue.type === 'typo' ? '错别字'
                        : issue.type === 'repetition' ? '重复用词'
                        : issue.type === 'inconsistency' ? '逻辑不连贯'
                        : issue.type === 'punctuation' ? '标点错误'
                        : issue.type;
                      const isError = issue.type === 'typo' || issue.type === 'punctuation';
                      return (
                        <div key={i} className="text-[10px] p-1.5 rounded bg-card border border-border/50">
                          <div className="flex items-center gap-1.5 mb-0.5">
                            <span className={`px-1 rounded text-[9px] font-medium ${
                              isError
                                ? 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400'
                                : 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400'
                            }`}>
                              {typeLabel}
                            </span>
                            <span className="text-ink-subtle">{issue.reason}</span>
                          </div>
                          <div className="flex items-baseline gap-2">
                            <span className={`line-through ${isError ? 'text-red-500' : 'text-amber-500'}`}>
                              {issue.original}
                            </span>
                            <span className="text-emerald-600 dark:text-emerald-400 font-medium">
                              → {issue.suggestion}
                            </span>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Word Frequency Analysis */}
              {showWordFreq && content && content !== '正文尚未生成' && (
                <div className="mt-3 p-3 rounded-lg bg-paper/50 border border-border animate-[fadeSlideIn_0.2s_ease-out]">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-[11px] font-semibold text-ink">
                      📊 词频分析 {expanded ? `— 第${expanded}章` : ''}
                    </span>
                    <button
                      onClick={e => { e.stopPropagation(); setShowWordFreq(false); }}
                      className="text-[10px] text-ink-muted hover:text-ink"
                    >
                      收起
                    </button>
                  </div>
                  <WordFrequency content={content} label={expanded ? `第${expanded}章` : undefined} />
                </div>
              )}

              {/* Scene Editor */}
              {sceneView && content && content !== '正文尚未生成' && (
                <SceneEditor
                  chapterContent={content}
                  chapterNumber={ch.number}
                  novelId={novelId}
                  onSave={async (mergedContent: string) => {
                    await fetch(`/api/novels/${novelId}/chapters/${ch.number}`, {
                      method: 'PUT',
                      headers: { 'Content-Type': 'application/json' },
                      body: JSON.stringify({ content: mergedContent }),
                    });
                    setContent(mergedContent);
                  }}
                  saving={saving}
                />
              )}

              {/* Chapter notes */}
              <div className="mt-4 pt-3 border-t border-border">
                <div className="flex items-center justify-between mb-1.5">
                  <p className="text-[11px] text-ink-muted">📝 私人笔记</p>
                  <button onClick={e => { e.stopPropagation(); saveNotes(); }}
                    className="text-[10px] text-accent hover:underline">保存</button>
                </div>
                <textarea
                  value={noteInput}
                  onChange={e => { e.stopPropagation(); setNoteInput(e.target.value); }}
                  placeholder="待改：节奏太慢 / 灵感：加入暗线 / 问题：配角动机不明确..."
                  rows={2}
                  onClick={e => e.stopPropagation()}
                  onKeyDown={e => e.stopPropagation()}
                  className="w-full text-[11px] rounded-md border border-input bg-paper px-3 py-1.5 resize-none
                    placeholder:text-ink-subtle focus:outline-none focus:border-accent" />
              </div>

              {/* Chapter version diff */}
              {content && content !== '正文尚未生成' && (() => {
                try {
                  const versions = JSON.parse(localStorage.getItem(`chapter-versions-${novelId}`) || '{}');
                  if (versions[String(ch.number)]?.length > 0) {
                    return (
                      <ChapterDiff
                        novelId={novelId}
                        chapterNum={ch.number}
                        currentContent={content}
                      />
                    );
                  }
                } catch {}
                return null;
              })()}

              {/* Quick feedback regenerate */}
              {content && content !== '正文尚未生成' && (
                <div className="mt-6 pt-4 border-t border-border">
                  <p className="text-[11px] text-ink-muted mb-2">不满意？选择重点改进方向并输入反馈：</p>
                  {/* Focus dimension chips */}
                  <div className="flex gap-1.5 mb-2 flex-wrap">
                    {[
                      { key: '对话', icon: '💬', label: '对话自然度' },
                      { key: '节奏', icon: '🏃', label: '节奏感' },
                      { key: '钩子', icon: '🎣', label: '结尾钩子' },
                      { key: '描写', icon: '🎨', label: '场景描写' },
                      { key: '人物', icon: '👤', label: '人物塑造' },
                      { key: '爽感', icon: '🔥', label: '爽感/高潮' },
                    ].map(f => (
                      <button key={f.key} onClick={e => { e.stopPropagation(); setRewriteFocus(rewriteFocus === f.key ? '' : f.key); }}
                        className={`text-[10px] px-2 py-0.5 rounded-full border transition-colors ${
                          rewriteFocus === f.key
                            ? 'bg-accent-soft text-accent border-accent/30'
                            : 'border-border text-ink-muted hover:text-ink'
                        }`}>
                        {f.icon} {f.label}
                      </button>
                    ))}
                  </div>
                  <div className="flex gap-2">
                    <input
                      value={feedbackInput}
                      onChange={e => setFeedbackInput(e.target.value)}
                      placeholder="如：节奏太慢 / 对话不够自然 / 增加细节描写..."
                      onKeyDown={e => { e.stopPropagation(); if (e.key === 'Enter') handleRegenerate(); }}
                      className="flex-1 text-xs rounded-md border border-input bg-paper px-3 py-1.5
                        placeholder:text-ink-subtle focus:outline-none focus:border-accent"
                    />
                    <button
                      onClick={e => { e.stopPropagation(); handleRegenerate(); }}
                      disabled={regenerating || !feedbackInput.trim()}
                      className="text-xs px-3 py-1.5 rounded-md bg-accent text-white hover:bg-accent-hover
                        disabled:opacity-40 transition-colors shrink-0">
                      {regenerating ? '生成中...' : '🔄 重新生成'}
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      );
    })}
        {/* Bottom spacer for virtual scroll */}
        <div style={{ height: (sortedChapters.length - endIdx) * ROW_HEIGHT }} />
      </div>

      {/* Mobile reading mode */}
      {mobileChapter !== null && (
        <MobileReadingMode
          novelId={novelId}
          chapters={chapters}
          initialChapter={mobileChapter}
          onClose={() => setMobileChapter(null)}
        />
      )}

      {/* Floating batch action bar */}
      {selectMode && selected.size > 0 && (
        <div className="fixed bottom-16 left-1/2 -translate-x-1/2 z-40 bg-card border border-border rounded-xl shadow-xl px-4 py-3
          flex items-center gap-3 animate-[fadeSlideIn_0.2s_ease-out]">
          <span className="text-xs text-ink-muted">{selected.size} 章已选</span>
          <span className="text-border">|</span>
          <button onClick={batchHumanize}
            className="text-xs px-2.5 py-1 rounded-md bg-accent-soft text-accent hover:bg-accent-soft/80 transition-colors">
            🧹 去AI味
          </button>
          <button onClick={batchFactCheck}
            className="text-xs px-2.5 py-1 rounded-md bg-accent-soft text-accent hover:bg-accent-soft/80 transition-colors">
            🔍 事实核查
          </button>
          <button onClick={() => { setSelectMode(false); setSelected(new Set()); }}
            className="text-xs px-2.5 py-1 rounded-md border border-border text-ink-muted hover:text-ink transition-colors">
            取消
          </button>
        </div>
      )}

      {/* Chapter tag picker overlay */}
      {tagPickerChapter !== null && (
        <div
          className="fixed inset-0 z-[95] flex items-center justify-center"
          onClick={e => { e.stopPropagation(); setTagPickerChapter(null); }}
        >
          <div
            onClick={e => e.stopPropagation()}
            className="bg-card border border-border rounded-xl shadow-xl p-4 w-[260px] animate-[fadeSlideIn_0.15s_ease-out]">
            <div className="flex items-center justify-between mb-3">
              <h4 className="text-xs font-semibold text-ink">
                🏷️ 第{tagPickerChapter}章 · 标签
              </h4>
              <button
                onClick={() => setTagPickerChapter(null)}
                className="text-xs text-ink-muted hover:text-ink"
              >
                ✕
              </button>
            </div>
            <div className="space-y-1">
              {TAG_OPTIONS.map(tag => {
                const selected = (chapterTags[tagPickerChapter] || []).includes(tag.key);
                return (
                  <button
                    key={tag.key}
                    onClick={() => toggleTag(tagPickerChapter, tag.key)}
                    className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-xs text-left transition-colors ${
                      selected
                        ? 'bg-accent-soft/50 border border-accent/20'
                        : 'hover:bg-paper border border-transparent'
                    }`}>
                    <span className="text-base">{tag.emoji}</span>
                    <span className={`flex-1 ${selected ? 'text-accent font-medium' : 'text-ink'}`}>
                      {tag.label}
                    </span>
                    {selected && <span className="text-accent text-[10px]">✓</span>}
                  </button>
                );
              })}
            </div>
            {(chapterTags[tagPickerChapter] || []).length > 0 && (
              <button
                onClick={() => {
                  const updated = { ...chapterTags };
                  delete updated[tagPickerChapter];
                  saveTags(updated);
                  setTagPickerChapter(null);
                }}
                className="w-full mt-3 text-[10px] text-ink-muted hover:text-red-500 transition-colors py-1.5">
                清除所有标签
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
