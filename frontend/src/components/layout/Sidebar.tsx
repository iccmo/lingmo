import { useNavigate, useLocation } from 'react-router-dom';
import { Separator } from 'src/components/ui/separator';
import type { NovelSummary } from 'src/types';
import { useEffect, useState } from 'react';
import { api } from 'src/lib/api';
import { LayoutDashboard, Settings, ScrollText, BarChart3, PenLine, BookOpen, Headphones, ArrowLeft, Eye, Users, Globe, Send, Wrench, X, AlertTriangle, GitBranch, Brain, type LucideIcon } from 'lucide-react';

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

/** Extract novel ID from pathname if we're in a novel context */
function useNovelId(): string | null {
 const { pathname } = useLocation();
 const match = pathname.match(/^\/novels\/([^/]+)/);
 return match ? match[1] : null;
}

/** Global navigation (when not inside a novel) */
function GlobalNav({ novels, onNovelSelect, onClose }: {
 novels: NovelSummary[];
 onNovelSelect?: (id: string) => void;
 onClose?: () => void;
}) {
 const navigate = useNavigate();
 const location = useLocation();

 const isActive = (path: string) => location.pathname === path;
 const goTo = (path: string) => { navigate(path); onClose?.(); };

 return (
 <>
 <div className="px-4 mb-1">
 <p className="text-[10px] font-semibold text-ink-subtle uppercase tracking-widest px-2">导航</p>
 </div>
 <NavItem label="工作台" icon={LayoutDashboard} active={isActive('/')} onClick={() => goTo('/')} />
 <NavItem label="设置" icon={Settings} active={isActive('/settings')} onClick={() => goTo('/settings')} />
 <NavItem label="日志" icon={ScrollText} active={isActive('/logs')} onClick={() => goTo('/logs')} />
 <NavItem label="统计" icon={BarChart3} active={isActive('/stats')} onClick={() => goTo('/stats')} />

 <Separator className="my-2 mx-4 w-auto" />

 <ModuleHeader icon={BookOpen} label="小说" />
 {novels.map(n => {
 const novelPath = `/novels/${n.id}`;
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
 className="flex items-center gap-2 px-3 py-1.5 mx-3 rounded-md text-[12px] sm:text-[13px] transition-colors text-left w-full text-ink-muted hover:text-ink hover:bg-surface-hover"
 >
 <span className="truncate flex-1 flex items-center gap-1.5">
 {n.title}
 {recent && (
 <span className="w-1.5 h-1.5 rounded-full bg-success-soft0 shrink-0" title="24小时内更新" />
 )}
 </span>
 {(() => {
 try {
 const approvals = JSON.parse(localStorage.getItem(`approvals-${n.id}`) || '{}');
 const reviseCount = Object.values(approvals).filter((s: unknown) => s === 'revise').length;
 if (reviseCount > 0) {
 return <span className="text-[9px] text-warn font-medium shrink-0 flex items-center gap-0.5" title={`${reviseCount}章待修改`}><AlertTriangle size={10} />{reviseCount}</span>;
 }
 } catch {}
 return null;
 })()}
 {n.total_chapters > 0 && (
 <span className="text-[10px] font-semibold text-ink-muted tabular-nums shrink-0">{n.total_chapters}章</span>
 )}
 </button>
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
 </div>
 );
 })}

 <Separator className="my-2 mx-4 w-auto" />

 <ModuleHeader icon={Headphones} label="听书" />
 <NavItem label="听书大厅" icon={Headphones} active={isActive('/listen')} onClick={() => goTo('/listen')} />
 </>
 );
}

/** Novel-internal navigation (when inside a novel) */
function NovelNav({ novelId, onClose }: { novelId: string; onClose?: () => void }) {
 const navigate = useNavigate();
 const location = useLocation();
 const [novelTitle, setNovelTitle] = useState('');

 useEffect(() => {
 api.novels.get(novelId).then(data => setNovelTitle(data.title)).catch(() => {});
 }, [novelId]);

 const basePath = `/novels/${novelId}`;
 const isActive = (path: string) => location.pathname === path;
 const goTo = (path: string) => { navigate(path); onClose?.(); };

 const navItems = [
 { label: '概览', icon: Eye, path: basePath },
 { label: '写作', icon: PenLine, path: `${basePath}/write` },
 { label: '分析', icon: BarChart3, path: `${basePath}/analysis` },
 { label: '角色', icon: Users, path: `${basePath}/characters` },
 { label: '世界', icon: Globe, path: `${basePath}/world` },
 { label: '伏笔', icon: GitBranch, path: `${basePath}/foreshadowing` },
 { label: '记忆', icon: Brain, path: `${basePath}/memory` },
 { label: '出版', icon: Send, path: `${basePath}/publish` },
 { label: '工具箱', icon: Wrench, path: `${basePath}/tools` },
 ];

 return (
 <>
 {/* Back button + novel title */}
 <div className="px-4 pb-2">
 <button
 onClick={() => { navigate(-1); onClose?.(); }}
 className="flex items-center gap-1.5 text-[11px] text-ink-subtle hover:text-accent transition-colors mb-2"
 >
 <ArrowLeft size={12} />
 <span>返回工作台</span>
 </button>
 <p className="text-sm font-semibold text-ink truncate">{novelTitle || novelId}</p>
 </div>

 <Separator className="my-2 mx-4 w-auto" />

 {/* Novel nav items */}
 <div className="px-4 mb-1">
 <p className="text-[10px] font-semibold text-ink-subtle uppercase tracking-widest px-2">小说</p>
 </div>
 {navItems.map(item => (
 <NavItem
 key={item.path}
 label={item.label}
 icon={item.icon}
 active={isActive(item.path)}
 onClick={() => goTo(item.path)}
 />
 ))}

 <div className="flex-1" />

 <Separator className="my-2 mx-4 w-auto" />
 <NavItem label="设置" icon={Settings} active={isActive('/settings')} onClick={() => goTo('/settings')} />
 </>
 );
}

export function Sidebar({ onNovelSelect, onClose }: Props) {
 const location = useLocation();
 const novelId = useNovelId();
 const [novels, setNovels] = useState<NovelSummary[]>([]);

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

 {novelId ? (
 <NovelNav novelId={novelId} onClose={onClose} />
 ) : (
 <GlobalNav novels={novels} onNovelSelect={onNovelSelect} onClose={onClose} />
 )}
 </aside>
 );
}
