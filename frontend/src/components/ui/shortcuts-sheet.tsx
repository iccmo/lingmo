import { useEffect, useState } from 'react';

const SHORTCUTS = [
  { keys: ['Ctrl', 'G'], desc: '生成下一章', section: '创作' },
  { keys: ['Ctrl', 'K'], desc: '命令面板', section: '全局' },
  { keys: ['J'], desc: '下一章', section: '浏览' },
  { keys: ['K'], desc: '上一章', section: '浏览' },
  { keys: ['Esc'], desc: '关闭弹窗 / 退出', section: '全局' },
  { keys: ['?'], desc: '显示快捷键', section: '全局' },
  { keys: ['⌘', '↵'], desc: '确认生成（在方向弹窗中）', section: '创作' },
];

export function ShortcutsSheet() {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === '?' && !(e.target as HTMLElement)?.matches('input, textarea, select')) {
        e.preventDefault();
        setOpen(prev => !prev);
      }
      if (e.key === 'Escape' && open) setOpen(false);
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [open]);

  if (!open) return null;

  // Group by section
  const sections = new Map<string, typeof SHORTCUTS>();
  for (const s of SHORTCUTS) {
    const list = sections.get(s.section) || [];
    list.push(s);
    sections.set(s.section, list);
  }

  return (
    <div className="fixed inset-0 z-[90] flex items-center justify-center bg-black/20 backdrop-blur-sm"
      onClick={() => setOpen(false)}>
      <div className="bg-card border border-border rounded-xl p-6 w-[400px] max-w-[90vw] shadow-xl animate-[fadeSlideIn_0.15s_ease-out]"
        onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-heading text-lg font-semibold text-ink">键盘快捷键</h3>
          <button onClick={() => setOpen(false)}
            className="text-xs text-ink-muted hover:text-ink">✕</button>
        </div>

        {[...sections.entries()].map(([section, shortcuts]) => (
          <div key={section} className="mb-3 last:mb-0">
            <div className="text-[10px] font-semibold text-ink-subtle uppercase tracking-wider mb-1.5">
              {section}
            </div>
            {shortcuts.map((s, i) => (
              <div key={i} className="flex items-center justify-between py-1.5">
                <span className="text-sm text-ink">{s.desc}</span>
                <span className="flex gap-1">
                  {s.keys.map((k, j) => (
                    <kbd key={j} className="px-1.5 py-0.5 rounded bg-paper border border-border text-[11px] text-ink-muted font-mono">
                      {k}
                    </kbd>
                  ))}
                </span>
              </div>
            ))}
          </div>
        ))}

        <p className="text-[10px] text-ink-subtle mt-4 pt-3 border-t border-border">
          按 <kbd className="px-1 py-0.5 rounded bg-paper border border-border font-mono">?</kbd> 随时查看快捷键
        </p>
      </div>
    </div>
  );
}
