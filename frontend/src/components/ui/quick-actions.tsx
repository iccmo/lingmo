import { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';

export function QuickActions() {
  const [open, setOpen] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();

  // Only show on app pages (not showcase)
  if (location.pathname === '/showcase') return null;

  const novelMatch = location.pathname.match(/\/novels\/([^/]+)/);
  const novelId = novelMatch ? novelMatch[1] : null;

  const actions = [
    { icon: '🏠', label: '工作台', onClick: () => navigate('/') },
    ...(novelId ? [
      { icon: '📖', label: '小说详情', onClick: () => navigate(`/novels/${novelId}`) },
      { icon: '✍️', label: '创作者模式', onClick: () => navigate(`/novels/${novelId}/edit`) },
      { icon: '📋', label: '章节大纲', onClick: () => navigate(`/novels/${novelId}/outline`) },
      { icon: '🌍', label: '世界观', onClick: () => navigate(`/novels/${novelId}/world`) },
    ] : []),
    { icon: '⚙️', label: '设置', onClick: () => navigate('/settings') },
  ];

  return (
    <div className="fixed bottom-6 right-6 z-50 flex flex-col items-end gap-2">
      {open && (
        <div className="flex flex-col gap-1.5 mb-2 animate-[fadeSlideIn_0.15s_ease-out]">
          {actions.map((a, i) => (
            <button key={i} onClick={() => { a.onClick(); setOpen(false); }}
              className="flex items-center gap-2 px-3 py-2 rounded-lg bg-card border border-border shadow-lg
                text-xs text-ink hover:text-accent hover:border-accent/30 transition-all whitespace-nowrap"
              style={{ animationDelay: `${i * 0.03}s` }}>
              {a.icon} {a.label}
            </button>
          ))}
        </div>
      )}
      <button onClick={() => setOpen(!open)}
        className={`w-11 h-11 rounded-full shadow-lg flex items-center justify-center text-lg transition-all duration-200 ${
          open ? 'bg-ink text-white rotate-45' : 'bg-accent text-white hover:bg-accent-hover hover:scale-105'
        }`}>
        {open ? '+' : '⚡'}
      </button>
    </div>
  );
}
