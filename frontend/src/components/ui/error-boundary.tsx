import { Component, type ReactNode } from 'react';
import { AlertTriangle } from 'lucide-react';

interface Props { children: ReactNode; }
interface State { error: Error | null; }

export class ErrorBoundary extends Component<Props, State> {
 state: State = { error: null };

 static getDerivedStateFromError(error: Error): State {
 return { error };
 }

 componentDidCatch(error: Error) {
 console.error('[ErrorBoundary]', error);
 }

 render() {
 if (this.state.error) {
 return (
 <div className="flex items-center justify-center min-h-[300px] p-8">
 <div className="text-center max-w-md">
 <AlertTriangle size={48} className="text-warn mb-4" />
 <h2 className="font-heading text-xl font-semibold text-ink mb-2">出了点问题</h2>
 <p className="text-sm text-ink-muted mb-4">
 {this.state.error.message || '未知错误'}
 </p>
 <button
 onClick={() => {
 this.setState({ error: null });
 window.location.reload();
 }}
 className="px-4 py-2 text-sm rounded-md bg-accent text-white hover:bg-accent-hover transition-colors">
 刷新页面
 </button>
 </div>
 </div>
 );
 }
 return this.props.children;
 }
}

/** Inline error fallback for smaller sections */
export function ErrorFallback({ message, onRetry }: { message?: string; onRetry?: () => void }) {
 return (
 <div className="p-4 border border-destructive/20 bg-destructive-soft dark:bg-red-950/30 rounded-lg text-center">
 <p className="text-sm text-destructive mb-2">{message || '加载失败'}</p>
 {onRetry && (
 <button onClick={onRetry}
 className="text-xs px-3 py-1 rounded border border-red-300 hover:bg-destructive-soft dark:border-red-700 dark:hover:bg-red-900 transition-colors text-destructive ">
 重试
 </button>
 )}
 </div>
 );
}
