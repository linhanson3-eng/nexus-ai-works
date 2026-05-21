import { Component, type ErrorInfo, type ReactNode } from "react";
import { AlertTriangle, RefreshCw } from "lucide-react";

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, error: null };

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("[ErrorBoundary]", error, info.componentStack);
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) return this.props.fallback;
      return (
        <div className="flex items-center justify-center h-full min-h-[200px]">
          <div className="text-center space-y-4">
            <div className="w-12 h-12 rounded-xl bg-warning/10 flex items-center justify-center mx-auto">
              <AlertTriangle className="w-6 h-6 text-warning" />
            </div>
            <div>
              <p className="text-white font-semibold">页面出错了</p>
              <p className="text-sm text-muted mt-1">{this.state.error?.message || "未知错误"}</p>
            </div>
            <button
              onClick={() => this.setState({ hasError: false, error: null })}
              className="inline-flex items-center gap-2 px-4 py-2 bg-accent/10 text-accent border border-accent/20 rounded-xl text-sm hover:bg-accent/20 transition-colors"
            >
              <RefreshCw className="w-3.5 h-3.5" /> 重试
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
