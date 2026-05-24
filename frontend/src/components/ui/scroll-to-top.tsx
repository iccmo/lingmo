import { useEffect, useState } from 'react';

export function ScrollToTop() {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const container = document.querySelector('main');
    if (!container) return;
    const handler = () => setVisible(container.scrollTop > 400);
    container.addEventListener('scroll', handler, { passive: true });
    return () => container.removeEventListener('scroll', handler);
  }, []);

  if (!visible) return null;

  return (
    <button
      onClick={() => {
        const container = document.querySelector('main');
        container?.scrollTo({ top: 0, behavior: 'smooth' });
      }}
      className="fixed bottom-6 right-20 z-40 w-10 h-10 rounded-full bg-card border border-border shadow-lg
        flex items-center justify-center text-ink-muted hover:text-ink hover:border-accent/30 hover:shadow-xl
        transition-all duration-200 animate-[fadeSlideIn_0.2s_ease-out]"
      aria-label="回到顶部"
    >
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
        <path d="M8 12V4M4 7l4-4 4 4" />
      </svg>
    </button>
  );
}
