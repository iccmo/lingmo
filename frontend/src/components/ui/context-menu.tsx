import { useEffect, useRef, useState, type ReactNode } from 'react';

interface ContextMenuProps {
  children: ReactNode;
  items: {
    label: string;
    icon?: string;
    onClick: () => void;
    danger?: boolean;
    disabled?: boolean;
  }[];
}

export function ContextMenu({ children, items }: ContextMenuProps) {
  const [show, setShow] = useState(false);
  const [pos, setPos] = useState({ x: 0, y: 0 });
  const menuRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!show) return;
    const handler = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setShow(false);
      }
    };
    // Delay to avoid immediate close on the same click
    const timer = setTimeout(() => document.addEventListener('click', handler), 0);
    return () => {
      clearTimeout(timer);
      document.removeEventListener('click', handler);
    };
  }, [show]);

  useEffect(() => {
    const handler = () => setShow(false);
    window.addEventListener('scroll', handler, true);
    return () => window.removeEventListener('scroll', handler, true);
  }, []);

  function handleContextMenu(e: { preventDefault: () => void; stopPropagation: () => void; clientX: number; clientY: number }) {
    e.preventDefault();
    e.stopPropagation();

    // Position within viewport
    const x = Math.min(e.clientX, window.innerWidth - 180);
    const y = Math.min(e.clientY, window.innerHeight - items.length * 36 - 10);
    setPos({ x, y });
    setShow(true);
  }

  return (
    <div ref={containerRef} onContextMenu={handleContextMenu}>
      {children}
      {show && (
        <div
          ref={menuRef}
          className="fixed z-[90] min-w-[160px] bg-card border border-border rounded-lg shadow-xl py-1 animate-[fadeSlideIn_0.12s_ease-out]"
          style={{ left: pos.x, top: pos.y }}>
          {items.map((item, i) => (
            <button
              key={i}
              disabled={item.disabled}
              onClick={e => {
                e.stopPropagation();
                item.onClick();
                setShow(false);
              }}
              className={`w-full flex items-center gap-2 px-3 py-1.5 text-[13px] text-left transition-colors
                disabled:opacity-30 disabled:cursor-not-allowed
                ${item.danger
                  ? 'text-red-500 hover:bg-red-50 dark:hover:bg-red-950'
                  : 'text-ink hover:bg-paper'
                }`}>
              {item.icon && <span className="text-xs">{item.icon}</span>}
              {item.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
