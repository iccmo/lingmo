import { useState, useEffect, useRef } from 'react';
import type { ChapterMeta } from 'src/types';
import { Search } from 'lucide-react';

interface SearchResult {
  chapter: ChapterMeta;
  matches: { line: string; lineNum: number }[];
}

interface Props {
  novelId: string;
  chapters: ChapterMeta[];
  onNavigate: (chapterNum: number) => void;
}

export function ChapterSearch({ novelId, chapters, onNavigate }: Props) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<SearchResult[]>([]);
  const [searching, setSearching] = useState(false);
  const [activeIdx, setActiveIdx] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  // Ctrl+Shift+F to open
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key === 'F') {
        e.preventDefault();
        setOpen(prev => !prev);
      }
      if (e.key === 'Escape' && open) setOpen(false);
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [open]);

  useEffect(() => { if (open) setTimeout(() => inputRef.current?.focus(), 50); }, [open]);

  // Debounced search
  useEffect(() => {
    if (!query.trim() || query.length < 2) { setResults([]); return; }
    setSearching(true);
    const timer = setTimeout(async () => {
      const q = query.toLowerCase();
      const r: SearchResult[] = [];
      for (const ch of chapters.filter(c => c.word_count > 0)) {
        try {
          const data = await fetch(`/api/novels/${novelId}/chapters/${ch.number}`).then(r => r.json());
          const content = data.content || '';
          const lines = content.split('\n');
          const matches = lines
            .map((line: string, i: number) => ({ line, lineNum: i + 1 }))
            .filter((m: { line: string }) => m.line.toLowerCase().includes(q))
            .slice(0, 3);
          if (matches.length > 0) r.push({ chapter: ch, matches });
        } catch { /* skip */ }
        // Show first 3 results immediately
        if (r.length >= 3) break;
      }
      setResults(r);
      setSearching(false);
    }, 400);
    return () => clearTimeout(timer);
  }, [query, novelId, chapters]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[95] flex items-start justify-center pt-[12vh] bg-black/25 backdrop-blur-sm"
      onClick={() => setOpen(false)}>
      <div className="w-[600px] max-w-[94vw] bg-card border border-border rounded-xl shadow-2xl overflow-hidden animate-[fadeSlideIn_0.15s_ease-out]"
        onClick={e => e.stopPropagation()}>
        {/* Header */}
        <div className="flex items-center gap-2 px-4 py-3 border-b border-border">
          <Search size={14} className="text-ink-subtle" />
          <input
            ref={inputRef}
            value={query}
            onChange={e => { setQuery(e.target.value); setActiveIdx(0); }}
            placeholder="搜索所有章节内容..."
            className="flex-1 bg-transparent text-ink text-sm outline-none placeholder:text-ink-subtle"
            onKeyDown={e => {
              if (e.key === 'ArrowDown') { e.preventDefault(); setActiveIdx(i => Math.min(i + 1, results.length - 1)); }
              if (e.key === 'ArrowUp') { e.preventDefault(); setActiveIdx(i => Math.max(i - 1, 0)); }
              if (e.key === 'Enter' && results[activeIdx]) {
                onNavigate(results[activeIdx].chapter.number);
                setOpen(false);
              }
            }}
          />
          <kbd className="text-[10px] text-ink-subtle bg-paper border border-border px-1.5 py-0.5 rounded font-mono">Esc</kbd>
        </div>

        {/* Results */}
        <div className="max-h-[400px] overflow-y-auto">
          {searching && (
            <div className="text-center py-8 text-sm text-ink-muted">搜索中...</div>
          )}
          {!searching && query.length < 2 && (
            <div className="text-center py-8 text-sm text-ink-muted">
              输入至少 2 个字符开始搜索（Ctrl+Shift+F 呼出）
            </div>
          )}
          {!searching && query.length >= 2 && results.length === 0 && (
            <div className="text-center py-8 text-sm text-ink-muted">
              未找到匹配章节
            </div>
          )}
          {results.map((r, i) => (
            <button
              key={r.chapter.number}
              onClick={() => { onNavigate(r.chapter.number); setOpen(false); }}
              className={`w-full text-left px-4 py-3 border-b border-border last:border-0 transition-colors ${
                i === activeIdx ? 'bg-accent-soft' : 'hover:bg-paper'
              }`}>
              <div className="flex items-center gap-2 mb-1">
                <span className="text-xs font-semibold text-ink">第{r.chapter.number}章</span>
                <span className="text-xs text-ink-muted truncate">{r.chapter.title}</span>
                <span className="text-[10px] text-ink-subtle ml-auto">{r.matches.length}+ 处匹配</span>
              </div>
              {r.matches.slice(0, 2).map((m, j) => (
                <p key={j} className="text-[11px] text-ink-muted leading-relaxed truncate pl-2 border-l-2 border-border">
                  {m.line.slice(0, 80)}
                </p>
              ))}
            </button>
          ))}
        </div>

        {/* Footer */}
        <div className="flex gap-3 px-4 py-2 border-t border-border text-[10px] text-ink-subtle">
          <span>Ctrl+Shift+F 呼出</span>
          <span>↑↓ 导航</span>
          <span>↵ 跳转</span>
        </div>
      </div>
    </div>
  );
}
