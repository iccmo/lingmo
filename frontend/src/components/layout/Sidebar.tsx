import { useNavigate, useLocation } from 'react-router-dom';
import { Separator } from 'src/components/ui/separator';
import type { NovelSummary } from 'src/types';
import { useEffect, useState } from 'react';
import { api } from 'src/lib/api';

interface Props {
  onNovelSelect?: (id: string) => void;
  onClose?: () => void;
}

export function Sidebar({ onNovelSelect, onClose }: Props) {
  const navigate = useNavigate();
  const location = useLocation();
  const [novels, setNovels] = useState<NovelSummary[]>([]);

  useEffect(() => {
    api.novels.list().then(novels => {
      // Sort: favorites first
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

  const isActive = (path: string) => location.pathname === path;

  return (
    <aside className="w-[200px] min-w-[200px] bg-card/50 border-r border-border flex flex-col overflow-y-auto py-4">
      {/* Mobile close button */}
      {onClose && (
        <button onClick={onClose}
          className="lg:hidden flex items-center justify-center w-7 h-7 rounded-full border border-border text-ink-muted hover:text-ink hover:bg-paper absolute top-2 right-2 z-10"
          aria-label="关闭侧栏">
          ✕
        </button>
      )}
      <div className="px-4 mb-1">
        <p className="text-[10px] font-semibold text-ink-subtle uppercase tracking-widest px-2">导航</p>
      </div>
      <button
        onClick={() => navigate('/')}
        className={`flex items-center gap-2.5 px-3 py-2 mx-3 rounded-md text-[12px] sm:text-[13px] transition-colors text-left ${
          isActive('/') ? 'bg-accent-soft text-accent font-medium' : 'text-ink hover:bg-paper'
        }`}
      >
        ◇ 工作台
      </button>
      <button
        onClick={() => navigate('/settings')}
        className={`flex items-center gap-2.5 px-3 py-2 mx-3 rounded-md text-[12px] sm:text-[13px] transition-colors text-left ${
          isActive('/settings') ? 'bg-accent-soft text-accent font-medium' : 'text-ink hover:bg-paper'
        }`}
      >
        ⚙ 设置
      </button>
      <button
        onClick={() => navigate('/logs')}
        className={`flex items-center gap-2.5 px-3 py-2 mx-3 rounded-md text-[12px] sm:text-[13px] transition-colors text-left ${
          isActive('/logs') ? 'bg-accent-soft text-accent font-medium' : 'text-ink hover:bg-paper'
        }`}
      >
        ☰ 日志
      </button>
      <button
        onClick={() => navigate('/stats')}
        className={`flex items-center gap-2.5 px-3 py-2 mx-3 rounded-md text-[12px] sm:text-[13px] transition-colors text-left ${
          location.pathname === '/stats' ? 'bg-accent-soft text-accent font-medium' : 'text-ink hover:bg-paper'
        }`}
      >
        📊 统计
      </button>
      <button
        onClick={() => navigate('/listen')}
        className={`flex items-center gap-2.5 px-3 py-2 mx-3 rounded-md text-[12px] sm:text-[13px] transition-colors text-left ${
          location.pathname === '/listen' ? 'bg-accent-soft text-accent font-medium' : 'text-ink hover:bg-paper'
        }`}
      >
        🎧 听书
      </button>
      <Separator className="my-3 mx-4 w-auto" />

      <div className="px-4 py-2">
        <p className="text-[10px] sm:text-[11px] font-semibold text-ink-subtle uppercase tracking-wider px-2 py-1">我的小说</p>
      </div>
      {novels.map(n => {
        const novelPath = `/novels/${n.id}`;
        const active = location.pathname === novelPath;
        const inNovel = location.pathname.startsWith(novelPath);
        const memActive = location.pathname === `${novelPath}/memory`;
        const foreshadowActive = location.pathname === `${novelPath}/foreshadowing`;
        // Activity indicator: updated in last 24h
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
                active ? 'bg-accent-soft text-accent font-medium' : inNovel ? 'text-ink hover:bg-paper' : 'text-ink-muted hover:text-ink hover:bg-paper'
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
                  const reviseCount = Object.values(approvals).filter((s: any) => s === 'revise').length;
                  if (reviseCount > 0) {
                    return <span className="text-[9px] text-amber-500 font-medium shrink-0" title={`${reviseCount}章待修改`}>🔧{reviseCount}</span>;
                  }
                } catch {}
                return null;
              })()}
              {n.total_chapters > 0 && (
                <span className="text-[10px] font-semibold text-ink-muted tabular-nums shrink-0">{n.total_chapters}章</span>
              )}
              {inNovel && !active && (
                <span className="text-[9px] text-ink-subtle">◆</span>
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
            <button
              onClick={() => navigate(`${novelPath}/memory`)}
              className={`flex items-center gap-2 px-3 py-0.5 mx-3 rounded-md text-[10px] sm:text-[11px] transition-colors text-left w-full ml-4 ${
                memActive ? 'text-accent font-medium' : 'text-ink-subtle hover:text-ink'
              }`}
            >
              🧠 记忆库
            </button>
            <button
              onClick={() => navigate(`${novelPath}/foreshadowing`)}
              className={`flex items-center gap-2 px-3 py-0.5 mx-3 rounded-md text-[10px] sm:text-[11px] transition-colors text-left w-full ml-4 ${
                foreshadowActive ? 'text-accent font-medium' : 'text-ink-subtle hover:text-ink'
              }`}
            >
              🔮 伏笔
            </button>
          </div>
        );
      })}
    </aside>
  );
}
