import { Crosshair } from 'lucide-react';
import { useTypewriter } from 'src/hooks/useTypewriter';

export function TypewriterToggle() {
  const { enabled, toggle } = useTypewriter();

  return (
    <button
      onClick={toggle}
      className={`
        flex items-center gap-1.5 px-2 py-1.5 text-sm rounded-md transition-colors
        ${enabled
          ? 'text-brand-primary bg-brand-accent/10'
          : 'text-text-muted hover:text-text-primary hover:bg-bg-surface'}
      `}
      title={enabled ? '打字机模式: 开启' : '打字机模式: 关闭'}
    >
      <Crosshair size={14} />
    </button>
  );
}
