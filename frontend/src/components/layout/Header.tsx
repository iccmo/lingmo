import { useState, useRef, useEffect } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { ModeToggle } from './ModeToggle';
import type { AppMode } from 'src/types';
import {
  Sparkles, Headphones, PanelLeftClose, PanelLeft,
  Moon, Monitor, Sun, Settings,
  Palette, Layout, Crosshair, FileText, Sparkles as PresetIcon
} from 'lucide-react';
import { FocusTimer } from 'src/components/writing/FocusTimer';
import { useTheme } from 'src/hooks/useTheme';
import { useLayout } from 'src/hooks/useLayout';
import { usePreset } from 'src/hooks/usePreset';
import { useTypewriter } from 'src/hooks/useTypewriter';
import { usePaperTexture } from 'src/hooks/usePaperTexture';

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
  if (pathname === '/listen') return '听书大厅';
  if (pathname === '/stats') return '统计';
  if (pathname.includes('/write')) return '写作';
  if (pathname.includes('/analysis')) return '分析';
  if (pathname.includes('/characters')) return '角色';
  if (pathname.includes('/memory')) return '记忆库';
  if (pathname.includes('/world')) return '世界观';
  if (pathname.includes('/outline')) return '大纲';
  if (pathname.includes('/edit')) return '编辑器';
  if (pathname.includes('/foreshadowing')) return '伏笔追踪';
  if (pathname.includes('/publish')) return '出版';
  if (pathname.includes('/tools')) return '工具箱';
  if (pathname.startsWith('/novels/')) return '小说详情';
  return '';
}

/** 写作工具下拉菜单 */
function WritingToolsDropdown() {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const { currentTheme, themes, setTheme } = useTheme();
  const { currentLayout, layouts, setLayout } = useLayout();
  const { currentPreset, presets, applyPreset } = usePreset();
  const { enabled: typewriter, toggle: toggleTypewriter } = useTypewriter();
  const { paperType, cyclePaper } = usePaperTexture();

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1.5 px-3 py-1.5 text-sm
                   text-ink-muted hover:text-ink hover:bg-surface-hover
                   rounded-md transition-colors min-h-[44px]"
        title="写作工具"
      >
        <Settings size={14} />
        <span className="hidden sm:inline text-xs">工具</span>
      </button>

      {open && (
        <div className="absolute right-0 top-full mt-1 w-80 p-4
                        bg-surface border border-border
                        rounded-xl shadow-lg z-50 max-h-[80vh] overflow-y-auto">
          {/* 场景预设 */}
          <div className="mb-4">
            <div className="flex items-center gap-2 mb-2">
              <PresetIcon size={14} className="text-accent" />
              <span className="text-xs font-semibold text-ink-subtle uppercase tracking-wider">写作场景</span>
            </div>
            <div className="grid grid-cols-2 gap-1.5">
              {presets.map(preset => (
                <button
                  key={preset.id}
                  onClick={() => { applyPreset(preset); setOpen(false); }}
                  className={`
                    flex items-center gap-2 px-3 py-2 rounded-lg text-left transition-colors text-sm
                    ${currentPreset?.id === preset.id
                      ? 'bg-accent/10 text-accent border border-accent/30'
                      : 'text-ink-muted hover:bg-surface-hover hover:text-ink border border-transparent'}
                  `}
                >
                  <span>{preset.icon}</span>
                  <span className="truncate">{preset.name}</span>
                </button>
              ))}
            </div>
          </div>

          {/* 主题 */}
          <div className="mb-4">
            <div className="flex items-center gap-2 mb-2">
              <Palette size={14} className="text-accent" />
              <span className="text-xs font-semibold text-ink-subtle uppercase tracking-wider">主题配色</span>
            </div>
            <div className="grid grid-cols-3 gap-1.5">
              {themes.map(theme => (
                <button
                  key={theme.id}
                  onClick={() => { setTheme(theme); }}
                  className={`
                    flex items-center gap-2 px-2 py-1.5 rounded-lg text-left transition-colors text-xs
                    ${currentTheme.id === theme.id
                      ? 'bg-accent/10 text-accent border border-accent/30'
                      : 'text-ink-muted hover:bg-surface-hover hover:text-ink border border-transparent'}
                  `}
                >
                  <div
                    className="w-3 h-3 rounded-full shrink-0 border border-white/20"
                    style={{ background: theme.colors.brand.primary }}
                  />
                  <span className="truncate">{theme.name}</span>
                </button>
              ))}
            </div>
          </div>

          {/* 布局 */}
          <div className="mb-4">
            <div className="flex items-center gap-2 mb-2">
              <Layout size={14} className="text-accent" />
              <span className="text-xs font-semibold text-ink-subtle uppercase tracking-wider">页面布局</span>
            </div>
            <div className="grid grid-cols-2 gap-1.5">
              {layouts.map(layout => (
                <button
                  key={layout.id}
                  onClick={() => { setLayout(layout.id); }}
                  className={`
                    px-3 py-2 rounded-lg text-left transition-colors text-sm
                    ${currentLayout.id === layout.id
                      ? 'bg-accent/10 text-accent border border-accent/30'
                      : 'text-ink-muted hover:bg-surface-hover hover:text-ink border border-transparent'}
                  `}
                >
                  <div className="font-medium">{layout.name}</div>
                  <div className="text-[11px] text-ink-subtle">{layout.description}</div>
                </button>
              ))}
            </div>
          </div>

          {/* 开关选项 */}
          <div>
            <div className="flex items-center gap-2 mb-2">
              <Settings size={14} className="text-accent" />
              <span className="text-xs font-semibold text-ink-subtle uppercase tracking-wider">写作辅助</span>
            </div>
            <div className="space-y-1">
              <button
                onClick={toggleTypewriter}
                className="flex items-center justify-between w-full px-3 py-2 rounded-lg
                           text-sm text-ink-muted hover:bg-surface-hover hover:text-ink transition-colors"
              >
                <div className="flex items-center gap-2">
                  <Crosshair size={14} />
                  <span>打字机模式</span>
                </div>
                <span className={`text-xs px-2 py-0.5 rounded ${typewriter ? 'bg-accent/20 text-accent' : 'bg-surface-hover'}`}>
                  {typewriter ? '开启' : '关闭'}
                </span>
              </button>
              <button
                onClick={cyclePaper}
                className="flex items-center justify-between w-full px-3 py-2 rounded-lg
                           text-sm text-ink-muted hover:bg-surface-hover hover:text-ink transition-colors"
              >
                <div className="flex items-center gap-2">
                  <FileText size={14} />
                  <span>纸张纹理</span>
                </div>
                <span className="text-xs text-ink-subtle">
                  {{'none':'无','parchment':'羊皮纸','xuan':'宣纸','grid':'方格','lined':'横线'}[paperType]}
                </span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
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
    <header className="h-14 bg-card/80 backdrop-blur-sm border-b border-border flex items-center justify-between px-4 sm:px-6 shrink-0">
      <div className="flex items-center gap-3">
        <Sparkles size={18} className="text-accent" />
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
      <div className="flex items-center gap-1.5">
        <FocusTimer />
        <span className="text-border mx-0.5">|</span>
        <WritingToolsDropdown />
        <span className="text-border mx-0.5">|</span>
        <button onClick={() => navigate('/listen')} className="text-accent hover:text-accent/80 transition-colors px-2 min-w-[44px] min-h-[44px] flex items-center justify-center"
          title="听书" aria-label="听书">
          <Headphones size={16} />
        </button>
        <button onClick={onSidebarToggle} className="text-ink-muted hover:text-ink transition-colors p-1.5 min-w-[44px] min-h-[44px] flex items-center justify-center"
          title={sidebarOpen ? '收起侧栏' : '展开侧栏'} aria-label={sidebarOpen ? '收起侧栏' : '展开侧栏'}>
          {sidebarOpen ? <PanelLeftClose size={16} /> : <PanelLeft size={16} />}
        </button>
        <ModeToggle mode={mode} onChange={handleChange} />
        <button aria-label="切换主题" onClick={onDarkToggle} className="text-ink-muted hover:text-ink transition-colors p-2 min-w-[44px] min-h-[44px] flex items-center justify-center"
          title={dark ? '当前暗色 · 点切换自动' : '当前亮色 · 点切换暗色'}>
          {dark ? <Moon size={16} /> : localStorage.getItem('dark') === 'auto' ? <Monitor size={16} /> : <Sun size={16} />}
        </button>
        <span className="text-border mx-0.5 hidden sm:inline">|</span>
        <button onClick={() => {
          sessionStorage.removeItem('session');
          window.location.href = '/';
        }} className="text-xs text-ink-muted hover:text-destructive transition-colors px-2 min-h-[44px] hidden sm:flex items-center" title="退出后台">
          退出
        </button>
      </div>
    </header>
  );
}
