import { useEffect, useState } from 'react';

interface Section { id: string; label: string; icon: string; }

interface Props {
  sections: Section[];
  activeSection?: string;
  onNavigate?: (id: string) => void;
}

export function SectionNav({ sections, activeSection, onNavigate }: Props) {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const container = document.querySelector('main');
    if (!container) return;

    const handler = () => {
      const scrollTop = container.scrollTop;
      setVisible(scrollTop > 300);
    };
    container.addEventListener('scroll', handler, { passive: true });
    handler();
    return () => container.removeEventListener('scroll', handler);
  }, []);

  if (!visible) return null;

  return (
    <nav className="fixed right-8 top-1/2 -translate-y-1/2 z-30 flex flex-col gap-1 animate-[fadeSlideIn_0.3s_ease-out]">
      {sections.map(s => {
        const isActive = activeSection === s.id;
        return (
          <button
            key={s.id}
            onClick={() => {
              if (onNavigate) {
                onNavigate(s.id);
              } else {
                document.getElementById(`section-${s.id}`)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
              }
            }}
            className={`group flex items-center gap-2 px-2 py-1.5 rounded-md text-[11px] transition-all ${
              isActive
                ? 'text-accent font-medium'
                : 'text-ink-muted hover:text-ink'
            }`}
            title={s.label}>
            <span className={`w-1.5 h-1.5 rounded-full transition-all shrink-0 ${
              isActive ? 'bg-accent scale-125' : 'bg-border group-hover:bg-ink-subtle'
            }`} />
            <span className={`text-[10px] transition-opacity whitespace-nowrap ${
              isActive ? 'opacity-100' : 'opacity-0 group-hover:opacity-100'
            }`}>{s.label}</span>
          </button>
        );
      })}
    </nav>
  );
}
