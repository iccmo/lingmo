import { useNavigate, useLocation } from 'react-router-dom';
import { Separator } from 'src/components/ui/separator';
import type { NovelSummary } from 'src/types';
import { useEffect, useState } from 'react';
import { api } from 'src/lib/api';
import {
  LayoutDashboard, Settings, ScrollText, BarChart3,
  PenLine, BookOpen, Brain, Sparkles,
  Headphones, Clapperboard, Palette, Video,
  X, AlertTriangle, type LucideIcon,
} from 'lucide-react';

interface Props {
  onNovelSelect?: (id: string) => void;
  onClose?: () => void;
}

/** Sidebar nav item */
function NavItem({ label, icon: Icon, active, onClick, indent = false }: {
  label: string; icon?: LucideIcon; active: boolean;
  onClick: () => void; indent?: boolean;
}) {
  return (
    <button
      onClick={onClick}
      className={`flex items-center gap-2 px-3 py-1.5 mx-3 rounded-md text-[12px] sm:text-[13px] transition-colors text-left w-full ${
        indent ? 'ml-4 py-0.5 text-[10px] sm:text-[11px]' : ''
      } ${
        active
          ? indent ? 'text-accent font-medium' : 'bg-accent-soft text-accent font-medium'
          : indent
            ? 'text-ink-subtle hover:text-ink'
            : 'text-ink hover:bg-surface-hover'
      }`}
    >
      {Icon && <Icon size={indent ? 12 : 14} className="shrink-0" />}
      <span className="truncate flex-1">{label}</span>
    </button>
  );
}

/** Module section header */
function ModuleHeader({ icon: Icon, label }: { icon: LucideIcon; label: string }) {
  return (
    <div className="px-4 pt-3 pb-1">
      <p className="text-[10px] sm:text-[11px] font-semibold text-ink-subtle uppercase tracking-wider px-2 flex items-center gap-1.5">
        <Icon size={12} /> {label}
      </p>
    </div>
  );
}

export function Sidebar({ onNovelSelect, onClose }: Props) {
  const navigate = useNavigate();
  const location = useLocation();
  const [novels, setNovels] = useState<NovelSummary[]>([]);
  const [selectedNovelId, setSelectedNovelId] = useState<string | null>(null);

  useEffect(() => {
    api.novels.list().then(novels => {
      try {
        const starred: string[] = JSON.parse(localStorage.getItem('starred-novels') || '[]');
        novels.sort((a, b) => {
          const aStar = starred.includes(a.id) ? 0 : 1;
          const bStar = starred.includes(b.id) ? 0 : 1;
          return aStar - bStar;
        });
      } catch {}
      setNovels(novels);
    }).catch(() => {});
  }, [location.pathname]);

  // Detect selected novel from URL
  useEffect(() => {
    const match = location.pathname.match(/^\/novels\/([^/]+)/);
    setSelectedNovelId(match ? match[1] : null);
  }, [location.pathname]);

  const isActive = (path: string) => location.pathname === path;
  const goTo = (path: string) => { navigate(path); onClose?.(); };

  return (
    <aside className="w-[200px] min-w-[200px] bg-card/50 border-r border-border flex flex-col overflow-y-auto py-4">
      {/* Mobile close button */}
      {onClose && (
        <button onClick={onClose}
          className="lg:hidden flex items-center justify-center w-7 h-7 rounded-full border border-border text-ink-muted hover:text-ink hover:bg-surface-hover absolute top-2 right-2 z-10"
          aria-label="关闭侧栏">
          <X size={14} />
        </button>
      )}

      {/* ── Global Nav ── */}
      <div className="px-4 mb-1">
        <p className="text-[10px] font-semibold text-ink-subtle uppercase tracking-widest px-2">导航</p>
      </div>
      <NavItem label="工作台" icon={LayoutDashboard} active={isActive('/')} onClick={() => goTo('/')} />
      <NavItem label="设置" icon={Settings} active={isActive('/settings')} onClick={() => goTo('/settings')} />
      <NavItem label="日志" icon={ScrollText} active={isActive('/logs')} onClick={() => goTo('/logs')} />
      <NavItem label="统计" icon={BarChart3} active={isActive('/stats')} onClick={() => goTo('/stats')} />

      <Separator className="my-2 mx-4 w-auto" />

      {/* ── Module: 小说 ── */}
      <ModuleHeader icon={BookOpen} label="小说" />
      {novels.map(n => {
        const novelPath = `/novels/${n.id}`;
        const active = location.pathname === novelPath;
        const inNovel = location.pathname.startsWith(novelPath);
        const recent = n.latest_chapter?.generated_at
          ? (Date.now() - new Date(n.latest_chapter.generated_at + 'Z').getTime()) < 86400000
          : false;
        return (
          <div key={n.id}>
            <button
              onClick={() => {
                navigate(novelPath);
                onNovelSelect?.(n.id);
              }}
              className={`flex items-center gap-2 px-3 py-1.5 mx-3 rounded-md text-[12px] sm:text-[13px] transition-colors text-left w-full ${
                active ? 'bg-accent-soft text-accent font-medium' : inNovel ? 'text-ink hover:bg-surface-hover' : 'text-ink-muted hover:text-ink hover:bg-surface-hover'
              }`}
            >
              <span className="truncate flex-1 flex items-center gap-1.5">
                {n.title}
                {recent && (
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 shrink-0" title="24小时内更新" />
                )}
              </span>
              {(() => {
                try {
                  const approvals = JSON.parse(localStorage.getItem(`approvals-${n.id}`) || '{}');
                  const reviseCount = Object.values(approvals).filter((s: unknown) => s === 'revise').length;
                  if (reviseCount > 0) {
                    return <span className="text-[9px] text-amber-500 font-medium shrink-0 flex items-center gap-0.5" title={`${reviseCount}章待修改`}><AlertTriangle size={10} />{reviseCount}</span>;
                  }
                } catch {}
                return null;
              })()}
              {n.total_chapters > 0 && (
                <span className="text-[10px] font-semibold text-ink-muted tabular-nums shrink-0">{n.total_chapters}章</span>
              )}
            </button>
            {/* Mini progress bar */}
            {n.total_chapters > 0 && (
              <div className="mx-3">
                <div className="h-0.5 bg-border rounded-full overflow-hidden">
                  <div
                    className="h-full bg-accent/40 rounded-full transition-all duration-300"
                    style={{ width: `${Math.min(n.total_chapters * 5, 100)}%` }}
                  />
                </div>
              </div>
            )}
            {/* Sub-items when this novel is selected */}
            {inNovel && (
              <>
                <NavItem label="写作" icon={PenLine} indent active={location.pathname === `${novelPath}/write`}
                  onClick={() => goTo(`${novelPath}/write`)} />
                <NavItem label="记忆库" icon={Brain} indent active={location.pathname === `${novelPath}/memory`}
                  onClick={() => goTo(`${novelPath}/memory`)} />
                <NavItem label="伏笔" icon={Sparkles} indent active={location.pathname === `${novelPath}/foreshadowing`}
                  onClick={() => goTo(`${novelPath}/foreshadowing`)} />
              </>
            )}
          </div>
        );
      })}

      <Separator className="my-2 mx-4 w-auto" />

      {/* ── Module: 听书 ── */}
      <ModuleHeader icon={Headphones} label="听书" />
      <NavItem label="听书大厅" icon={Headphones} active={isActive('/listen')} onClick={() => goTo('/listen')} />

      <Separator className="my-2 mx-4 w-auto" />

      {/* ── Module: 短剧 ── */}
      <ModuleHeader icon={Clapperboard} label="短剧" />
      {selectedNovelId ? (
        <>
          <NavItem label="视觉圣经" icon={Palette} indent
            active={location.pathname.includes('/visual-bible')}
            onClick={() => goTo(`/novels/${selectedNovelId}`)} />
          <NavItem label="分镜脚本" icon={Clapperboard} indent
            active={location.pathname.includes('/storyboard')}
            onClick={() => goTo(`/novels/${selectedNovelId}`)} />
          <NavItem label="制片中心" icon={Video} indent
            active={location.pathname.includes('/produce')}
            onClick={() => goTo(`/novels/${selectedNovelId}`)} />
        </>
      ) : (
        <p className="px-5 py-1 text-[10px] text-ink-subtle">选择小说后可用</p>
      )}
    </aside>
  );
}
