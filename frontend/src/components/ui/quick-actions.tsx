import { useState } from 'react';
import { Zap, Plus, LayoutDashboard, BookOpen, PenLine, ClipboardList, Globe, Headphones, Settings } from 'lucide-react';
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
    { icon: 'LayoutDashboard', label: '工作台', onClick: () => navigate('/') },
    ...(novelId ? [
      { icon: 'BookOpen', label: '小说详情', onClick: () => navigate(`/novels/${novelId}`) },
      { icon: 'PenLine', label: '创作者模式', onClick: () => navigate(`/novels/${novelId}/edit`) },
      { icon: 'ClipboardList', label: '章节大纲', onClick: () => navigate(`/novels/${novelId}/outline`) },
      { icon: 'Globe', label: '世界观', onClick: () => navigate(`/novels/${novelId}/world`) },
    ] : []),
    { icon: 'Headphones', label: '听书', onClick: () => navigate('/listen') },
    { icon: 'Settings', label: '设置', onClick: () => navigate('/settings') },
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
              {(() => { const icons: Record<string, React.ElementType> = { LayoutDashboard, BookOpen, PenLine, ClipboardList, Globe, Headphones, Settings, Zap }; const I = icons[a.icon]; return I ? <I size={14} /> : a.icon; })()} {a.label}
            </button>
          ))}
        </div>
      )}
      <button onClick={() => setOpen(!open)}
        className={`w-11 h-11 rounded-full shadow-lg flex items-center justify-center text-lg transition-all duration-200 ${
          open ? 'bg-ink text-white dark:text-black rotate-45' : 'bg-accent text-white hover:bg-accent-hover hover:scale-105'
        }`}>
        {open ? <Plus size={16} /> : <Zap size={16} />}
      </button>
    </div>
  );
}
