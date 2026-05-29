import { Columns2, Maximize, Square, Minimize } from 'lucide-react';
import type { LayoutMode } from 'src/themes/layouts';
import { useLayout } from 'src/hooks/useLayout';

const icons: Record<LayoutMode, typeof Columns2> = {
  classic: Columns2,
  immersive: Square,
  compact: Maximize,
  zen: Minimize,
};

export function LayoutSwitcher() {
  const { currentLayout, cycleLayout } = useLayout();
  const Icon = icons[currentLayout.id];

  return (
    <button
      onClick={cycleLayout}
      className="flex items-center gap-1.5 px-2 py-1.5 text-sm
                 text-text-muted hover:text-text-primary
                 hover:bg-bg-surface rounded-md transition-colors"
      title={`当前: ${currentLayout.name} · 点击切换`}
    >
      <Icon size={14} />
    </button>
  );
}
