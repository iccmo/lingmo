/** React Error Boundary — 捕获异常，显示重试按钮。 */
import { Component, type ReactNode, type ErrorInfo } from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';

interface Props { children: ReactNode; }
interface State { error: Error | null; errorInfo: ErrorInfo | null; }

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null, errorInfo: null };

  static getDerivedStateFromError(error: Error): Partial<State> {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    this.setState({ errorInfo: info });
    console.error('[ErrorBoundary]', error.message, info.componentStack?.slice(0, 200));
  }

  handleRetry = () => this.setState({ error: null, errorInfo: null });

  render() {
    if (this.state.error) {
      return (
        <div className="flex flex-col items-center justify-center min-h-[300px] p-8 text-center animate-[fadeSlideIn_0.2s_ease-out]">
          <AlertTriangle size={40} className="text-warn mb-4" />
          <h2 className="text-base font-semibold text-ink mb-2">页面出错了</h2>
          <p className="text-sm text-ink-muted mb-1 max-w-md">
            {this.state.error.message.slice(0, 120)}
          </p>
          <details className="text-xs text-ink-subtle mb-4 max-w-md">
            <summary className="cursor-pointer hover:text-ink">详细堆栈</summary>
            <pre className="mt-2 p-2 bg-surface rounded text-[10px] overflow-auto max-h-32 whitespace-pre-wrap">
              {this.state.errorInfo?.componentStack || this.state.error.stack || '无堆栈信息'}
            </pre>
          </details>
          <button
            onClick={this.handleRetry}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-accent text-white rounded-lg hover:bg-accent/80 transition-colors"
          >
            <RefreshCw size={12} /> 重试
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
