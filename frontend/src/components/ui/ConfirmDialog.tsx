/** 确认对话框 — 替代浏览器原生 confirm() */
import { AlertTriangle, X } from 'lucide-react';

interface Props {
  open: boolean;
  title: string;
  message: string;
  confirmLabel?: string;
  variant?: 'danger' | 'warning';
  onConfirm: () => void;
  onCancel: () => void;
}

export function ConfirmDialog({
  open,
  title,
  message,
  confirmLabel = '确定',
  variant = 'danger',
  onConfirm,
  onCancel,
}: Props) {
  if (!open) return null;

  const colorClasses = variant === 'danger'
    ? 'bg-destructive hover:bg-destructive/80'
    : 'bg-warn hover:bg-warn/80';

  return (
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center bg-black/40 animate-[fadeIn_0.15s_ease-out]"
      onClick={(e) => { e.stopPropagation(); onCancel(); }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="bg-card border border-border rounded-xl shadow-2xl p-6 w-[360px] max-w-[90vw] animate-[fadeSlideIn_0.15s_ease-out]"
      >
        <div className="flex items-start gap-3 mb-4">
          <AlertTriangle size={22} className={variant === 'danger' ? 'text-destructive shrink-0 mt-0.5' : 'text-warn shrink-0 mt-0.5'} />
          <div className="flex-1 min-w-0">
            <h3 className="text-sm font-semibold text-ink">{title}</h3>
            <p className="text-xs text-ink-muted mt-1 leading-relaxed">{message}</p>
          </div>
          <button onClick={onCancel} className="text-ink-muted hover:text-ink shrink-0">
            <X size={16} />
          </button>
        </div>
        <div className="flex justify-end gap-2">
          <button
            onClick={onCancel}
            className="px-3 py-1.5 text-xs font-medium border border-border rounded-lg text-ink-muted hover:bg-surface transition-colors"
          >
            取消
          </button>
          <button
            onClick={(e) => { e.stopPropagation(); onConfirm(); }}
            className={`px-3 py-1.5 text-xs font-medium text-white rounded-lg transition-colors ${colorClasses}`}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
