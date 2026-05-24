import { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';

interface Command {
  id: string;
  label: string;
  shortcut?: string;
  icon: string;
  action: () => void;
  section: string;
  keywords?: string;
}

export function CommandPalette() {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [activeIndex, setActiveIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();
  const location = useLocation();

  // Fetch novels for quick nav
  const [novels, setNovels] = useState<{id: string; title: string; genre: string}[]>([]);
  useEffect(() => {
    fetch('/api/novels').then(r => r.json()).then(d => setNovels(d || [])).catch(() => {});
  }, [location.pathname]);

  // Build commands
  const commands: Command[] = [
    // Navigation
    { id: 'nav-dashboard', label: '工作台', icon: '◇', section: '导航', shortcut: 'G H',
      action: () => navigate('/'), keywords: 'dashboard home' },
    { id: 'nav-settings', label: '设置', icon: '⚙', section: '导航', shortcut: 'G S',
      action: () => navigate('/settings') },
    { id: 'nav-logs', label: '运行日志', icon: '☰', section: '导航',
      action: () => navigate('/logs') },
    { id: 'nav-listen', label: '听书', icon: '🎧', section: '导航', shortcut: 'G L',
      action: () => navigate('/listen'), keywords: 'audio tts listen' },
    // Quick open novels
    ...novels.slice(0, 8).map((n): Command => ({
      id: `novel-${n.id}`,
      label: n.title,
      icon: '📖',
      section: '小说',
      action: () => navigate(`/novels/${n.id}`),
      keywords: n.genre,
    })),
    // Actions
    { id: 'act-new-novel', label: '创建新小说', icon: '✍️', section: '操作',
      action: () => navigate('/'), keywords: 'create new' },
    { id: 'act-toggle-dark', label: '切换暗色模式', icon: '🌙', section: '操作',
      action: () => {
        const next = !document.documentElement.classList.contains('dark');
        document.documentElement.classList.toggle('dark', next);
        localStorage.setItem('dark', String(next));
      }},
  ];

  // Filter
  const filtered = query.trim()
    ? commands.filter(c =>
        c.label.toLowerCase().includes(query.toLowerCase()) ||
        (c.keywords || '').toLowerCase().includes(query.toLowerCase()))
    : commands;

  // Group by section
  const sections = new Map<string, Command[]>();
  for (const cmd of filtered) {
    const list = sections.get(cmd.section) || [];
    list.push(cmd);
    sections.set(cmd.section, list);
  }

  // Reset index on query change
  useEffect(() => { setActiveIndex(0); }, [query]);

  // Keyboard listener
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        setOpen(prev => !prev);
        setQuery('');
        setActiveIndex(0);
      }
      if (e.key === 'Escape' && open) {
        e.preventDefault();
        setOpen(false);
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [open]);

  // Focus input on open
  useEffect(() => {
    if (open) setTimeout(() => inputRef.current?.focus(), 50);
  }, [open]);

  const executeCommand = useCallback((cmd: Command) => {
    cmd.action();
    setOpen(false);
    setQuery('');
  }, []);

  function handleKeyDown(e: { key: string; preventDefault: () => void }) {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setActiveIndex(i => Math.min(i + 1, filtered.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setActiveIndex(i => Math.max(i - 1, 0));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (filtered[activeIndex]) executeCommand(filtered[activeIndex]);
    }
  }

  if (!open) return null;

  let globalIndex = 0;

  return (
    <div className="fixed inset-0 z-[100] flex items-start justify-center pt-[18vh] bg-black/25 backdrop-blur-sm"
      onClick={() => setOpen(false)}>
      <div className="w-[520px] max-w-[92vw] bg-card border border-border rounded-xl shadow-2xl overflow-hidden animate-[fadeSlideIn_0.15s_ease-out]"
        onClick={e => e.stopPropagation()}>
        {/* Search input */}
        <div className="flex items-center gap-2 px-4 py-3 border-b border-border">
          <span className="text-ink-subtle text-sm">🔍</span>
          <input
            ref={inputRef}
            value={query}
            onChange={e => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="搜索命令、小说、设置..."
            className="flex-1 bg-transparent text-ink text-sm outline-none placeholder:text-ink-subtle"
          />
          <kbd className="text-[10px] text-ink-subtle bg-paper border border-border px-1.5 py-0.5 rounded font-mono">
            Esc
          </kbd>
        </div>

        {/* Results */}
        <div className="max-h-[360px] overflow-y-auto py-2">
          {filtered.length === 0 ? (
            <div className="text-center py-8 text-sm text-ink-muted">
              无匹配结果
            </div>
          ) : (
            [...sections.entries()].map(([section, cmds]) => (
              <div key={section}>
                <div className="text-[10px] font-semibold text-ink-subtle uppercase tracking-wider px-4 py-1.5 mt-1">
                  {section}
                </div>
                {cmds.map(cmd => {
                  const index = globalIndex++;
                  const active = index === activeIndex;
                  return (
                    <button
                      key={cmd.id}
                      onClick={() => executeCommand(cmd)}
                      onMouseEnter={() => setActiveIndex(index)}
                      className={`w-full flex items-center gap-3 px-4 py-2 text-left text-sm transition-colors ${
                        active ? 'bg-accent-soft text-accent' : 'text-ink hover:bg-paper'
                      }`}>
                      <span className="text-base w-5 text-center shrink-0">{cmd.icon}</span>
                      <span className="flex-1 truncate">{cmd.label}</span>
                      {cmd.shortcut && (
                        <kbd className="text-[10px] text-ink-subtle font-mono shrink-0">{cmd.shortcut}</kbd>
                      )}
                    </button>
                  );
                })}
              </div>
            ))
          )}
        </div>

        {/* Footer */}
        <div className="flex gap-3 px-4 py-2 border-t border-border text-[10px] text-ink-subtle">
          <span>↑↓ 导航</span>
          <span>↵ 选择</span>
          <span>Esc 关闭</span>
        </div>
      </div>
    </div>
  );
}
