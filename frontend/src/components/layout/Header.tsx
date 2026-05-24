import { useLocation, useNavigate } from 'react-router-dom';
import { ModeToggle } from './ModeToggle';
import type { AppMode } from 'src/types';

interface Props {
  mode: AppMode;
  onModeChange: (mode: AppMode) => void;
  dark: boolean;
  onDarkToggle: () => void;
  sidebarOpen: boolean;
  onSidebarToggle: () => void;
}

function breadcrumbLabel(pathname: string): string {
  if (pathname === '/') return '工作台';
  if (pathname === '/settings') return '设置';
  if (pathname === '/logs') return '日志';
  if (pathname.includes('/memory')) return '记忆库';
  if (pathname.includes('/world')) return '世界观';
  if (pathname.includes('/outline')) return '大纲';
  if (pathname.includes('/edit')) return '编辑器';
  if (pathname.includes('/foreshadowing')) return '伏笔追踪';
  if (pathname.startsWith('/novels/')) return '小说详情';
  return '';
}

export function Header({ mode, onModeChange, dark, onDarkToggle, sidebarOpen, onSidebarToggle }: Props) {
  const location = useLocation();
  const navigate = useNavigate();
  const crumb = breadcrumbLabel(location.pathname);

  function handleChange(newMode: AppMode) {
    onModeChange(newMode);
    const match = location.hash.match(/\/novels\/([^/]+)/);
    if (match) {
      fetch(`/api/novels/${match[1]}/auto/${newMode === 'auto' ? 'start' : 'stop'}`, { method: 'POST' }).catch(() => {});
    }
  }

  return (
    <header className="h-14 bg-card/80 backdrop-blur border-b border-border flex items-center justify-between px-6 shrink-0">
      <div className="flex items-center gap-3">
        <span className="text-lg">✧</span>
        <span className="font-heading text-lg text-ink font-semibold tracking-tight">
          <span className="text-accent">灵墨</span>
        </span>
        <span className="hidden sm:inline text-[11px] text-ink-subtle border-l border-border pl-3">AI 创作伴侣</span>
        {crumb && (
          <span className="hidden md:flex items-center gap-1.5 text-[11px] text-ink-subtle border-l border-border pl-3 ml-1">
            <span className="text-ink-muted">/</span>
            <span className="text-ink font-medium">{crumb}</span>
          </span>
        )}
      </div>
      <div className="flex items-center gap-2">
        <button onClick={() => navigate('/listen')} className="text-base sm:text-sm text-accent hover:text-accent/80 transition-colors px-2 sm:px-1.5 min-w-[44px] min-h-[44px] flex items-center justify-center"
          title="听书">
          🎧
        </button>
        <button onClick={onSidebarToggle} className="text-sm text-ink-muted hover:text-ink transition-colors px-1.5"
          title={sidebarOpen ? '收起侧栏' : '展开侧栏'}>
          {sidebarOpen ? '◁' : '▷'}
        </button>
        <ModeToggle mode={mode} onChange={handleChange} />
        <button onClick={onDarkToggle} className="text-sm text-ink-muted hover:text-ink transition-colors px-2" title={dark ? '当前暗色 · 点切换自动' : '当前亮色 · 点切换暗色'}>
          {dark ? '🌙' : localStorage.getItem('dark') === 'auto' ? '🔄' : '☀️'}
        </button>
        <span className="text-border mx-0.5">|</span>
        <button onClick={() => {
          sessionStorage.removeItem('session');
          window.location.href = '/';
        }} className="text-xs text-ink-muted hover:text-red-500 transition-colors px-2" title="退出后台">
          退出
        </button>
      </div>
    </header>
  );
}
