/** React Error Boundary — 捕获子树异常，显示重试按钮。 */
import { Component, type ReactNode, type ErrorInfo } from 'react';

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  error: Error | null;
  errorInfo: ErrorInfo | null;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null, errorInfo: null };

  static getDerivedStateFromError(error: Error): Partial<State> {
    return { error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    this.setState({ errorInfo });
    console.error('[ErrorBoundary]', error, errorInfo.componentStack);
  }

  handleRetry = () => {
    this.setState({ error: null, errorInfo: null });
  };

  render() {
    if (this.state.error) {
      if (this.props.fallback) return this.props.fallback;

      return (
        <div className="flex flex-col items-center justify-center min-h-[200px] p-8 text-center">
          <div className="text-4xl mb-4">⚠</div>
          <h2 className="text-base font-semibold text-ink mb-2">页面出错了</h2>
          <p className="text-sm text-ink-muted mb-1 max-w-md">
            {this.state.error.message.slice(0, 150)}
          </p>
          <details className="text-xs text-ink-subtle mb-4 max-w-md text-left">
            <summary className="cursor-pointer hover:text-ink">详细堆栈</summary>
            <pre className="mt-2 p-2 bg-surface rounded text-[10px] overflow-auto max-h-32">
              {this.state.errorInfo?.componentStack || this.state.error.stack}
            </pre>
          </details>
          <button
            onClick={this.handleRetry}
            className="px-4 py-2 text-sm bg-accent text-white rounded-lg hover:bg-accent/80 transition-colors"
          >
            重试
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}
