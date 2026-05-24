import { Component, type ErrorInfo, type ReactNode } from "react";
import { AlertTriangle, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";

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
            <div className="w-12 h-12 rounded-lg bg-destructive/10 flex items-center justify-center mx-auto">
              <AlertTriangle className="w-6 h-6 text-destructive" />
            </div>
            <div>
              <p className="font-semibold">页面出错了</p>
              <p className="text-sm text-muted-foreground mt-1">
                {this.state.error?.message || "未知错误"}
              </p>
            </div>
            <Button
              variant="outline"
              onClick={() => this.setState({ hasError: false, error: null })}
            >
              <RefreshCw className="w-3.5 h-3.5 mr-2" /> 重试
            </Button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
