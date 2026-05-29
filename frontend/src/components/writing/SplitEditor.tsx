import { useState, useCallback } from 'react';
import { GripVertical } from 'lucide-react';

interface Props {
  leftContent: React.ReactNode;
  rightContent: React.ReactNode;
  leftLabel?: string;
  rightLabel?: string;
  defaultRatio?: number;
}

export function SplitEditor({
  leftContent,
  rightContent,
  leftLabel = '大纲',
  rightLabel = '正文',
  defaultRatio = 0.35,
}: Props) {
  const [ratio, setRatio] = useState(defaultRatio);
  const [isDragging, setIsDragging] = useState(false);

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    setIsDragging(true);

    const handleMouseMove = (e: MouseEvent) => {
      const container = (e.target as HTMLElement).closest('.split-container');
      if (!container) return;
      const rect = container.getBoundingClientRect();
      const newRatio = Math.max(0.2, Math.min(0.6, (e.clientX - rect.left) / rect.width));
      setRatio(newRatio);
    };

    const handleMouseUp = () => {
      setIsDragging(false);
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };

    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
  }, []);

  return (
    <div className={`split-container flex h-full ${isDragging ? 'select-none' : ''}`}>
      {/* Left panel */}
      <div
        className="flex flex-col overflow-hidden"
        style={{ width: `${ratio * 100}%` }}
      >
        <div className="px-3 py-2 border-b border-border-default">
          <span className="text-xs font-medium text-text-muted">{leftLabel}</span>
        </div>
        <div className="flex-1 overflow-y-auto">
          {leftContent}
        </div>
      </div>

      {/* Divider */}
      <div
        onMouseDown={handleMouseDown}
        className={`
          w-1 cursor-col-resize flex items-center justify-center
          hover:bg-brand-primary/20 transition-colors
          ${isDragging ? 'bg-brand-primary/30' : 'bg-border-default'}
        `}
      >
        <GripVertical size={10} className="text-text-muted" />
      </div>

      {/* Right panel */}
      <div
        className="flex flex-col overflow-hidden"
        style={{ width: `${(1 - ratio) * 100}%` }}
      >
        <div className="px-3 py-2 border-b border-border-default">
          <span className="text-xs font-medium text-text-muted">{rightLabel}</span>
        </div>
        <div className="flex-1 overflow-y-auto">
          {rightContent}
        </div>
      </div>
    </div>
  );
}
