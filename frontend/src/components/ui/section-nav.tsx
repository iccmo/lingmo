import { useEffect, useState } from 'react';

interface Section { id: string; label: string; icon: string; }

export function SectionNav({ sections }: { sections: Section[] }) {
  const [active, setActive] = useState('');
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const container = document.querySelector('main');
    if (!container) return;

    const handler = () => {
      const scrollTop = container.scrollTop;
      setVisible(scrollTop > 300);

      // Find which section is in view
      for (const s of sections) {
        const el = document.getElementById(`section-${s.id}`);
        if (el) {
          const rect = el.getBoundingClientRect();
          if (rect.top < window.innerHeight / 2 && rect.bottom > 0) {
            setActive(s.id);
            break;
          }
        }
      }
    };
    container.addEventListener('scroll', handler, { passive: true });
    handler();
    return () => container.removeEventListener('scroll', handler);
  }, [sections]);

  if (!visible) return null;

  return (
    <nav className="fixed right-8 top-1/2 -translate-y-1/2 z-30 flex flex-col gap-1 animate-[fadeSlideIn_0.3s_ease-out]">
      {sections.map(s => (
        <button
          key={s.id}
          onClick={() => {
            document.getElementById(`section-${s.id}`)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
          }}
          className={`group flex items-center gap-2 px-2 py-1.5 rounded-md text-[11px] transition-all ${
            active === s.id
              ? 'text-accent font-medium'
              : 'text-ink-muted hover:text-ink'
          }`}
          title={s.label}>
          <span className={`w-1.5 h-1.5 rounded-full transition-all shrink-0 ${
            active === s.id ? 'bg-accent scale-125' : 'bg-border group-hover:bg-ink-subtle'
          }`} />
          <span className={`text-[10px] transition-opacity whitespace-nowrap ${
            active === s.id ? 'opacity-100' : 'opacity-0 group-hover:opacity-100'
          }`}>{s.label}</span>
        </button>
      ))}
    </nav>
  );
}
