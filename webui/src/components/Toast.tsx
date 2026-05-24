import { createContext, useCallback, useContext, useState, type ReactNode } from "react";
import { CheckCircle2, XCircle, AlertTriangle, X } from "lucide-react";

type ToastType = "success" | "error" | "info";

interface Toast {
  id: number;
  type: ToastType;
  message: string;
}

interface ToastContextValue {
  toasts: Toast[];
  success: (msg: string) => void;
  error: (msg: string) => void;
  info: (msg: string) => void;
}

export type ToastFn = ToastContextValue;

const ToastContext = createContext<ToastContextValue | null>(null);

let nextId = 0;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const addToast = useCallback((type: ToastType, message: string) => {
    const id = nextId++;
    setToasts((prev) => [...prev, { id, type, message }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 3500);
  }, []);

  const remove = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const value: ToastContextValue = {
    toasts,
    success: (msg) => addToast("success", msg),
    error: (msg) => addToast("error", msg),
    info: (msg) => addToast("info", msg),
  };

  const icons = {
    success: <CheckCircle2 className="w-4 h-4 text-success" />,
    error: <XCircle className="w-4 h-4 text-destructive" />,
    info: <AlertTriangle className="w-4 h-4 text-primary" />,
  };

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div className="fixed bottom-6 right-6 z-50 flex flex-col gap-2 max-w-sm">
        {toasts.map((t) => (
          <div
            key={t.id}
            className="flex items-center gap-3 bg-card border border-border rounded-lg px-4 py-3 shadow-lg animate-in slide-in-from-right"
          >
            {icons[t.type]}
            <span className="text-sm text-foreground flex-1">{t.message}</span>
            <button
              onClick={() => remove(t.id)}
              className="text-muted-foreground hover:text-foreground transition-colors"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be used within ToastProvider");
  return ctx;
}
