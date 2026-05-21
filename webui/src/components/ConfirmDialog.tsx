import { AlertTriangle } from "lucide-react";

interface Props {
  title: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  variant?: "danger" | "default";
  onConfirm: () => void;
  onCancel: () => void;
}

export function ConfirmDialog({
  title,
  message,
  confirmLabel = "确认",
  cancelLabel = "取消",
  variant = "danger",
  onConfirm,
  onCancel,
}: Props) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm" onClick={onCancel}>
      <div
        className="bg-card border border-border rounded-2xl p-6 max-w-sm mx-4 shadow-2xl animate-in zoom-in"
        onClick={e => e.stopPropagation()}
      >
        <div className="flex items-start gap-3">
          <div className={`w-10 h-10 rounded-xl flex items-center justify-center shrink-0 ${variant === "danger" ? "bg-warning/10" : "bg-accent/10"}`}>
            <AlertTriangle className={`w-5 h-5 ${variant === "danger" ? "text-warning" : "text-accent"}`} />
          </div>
          <div className="flex-1">
            <h3 className="text-white font-semibold text-sm">{title}</h3>
            <p className="text-sm text-muted mt-1">{message}</p>
          </div>
        </div>
        <div className="flex justify-end gap-3 mt-6">
          <button
            onClick={onCancel}
            className="px-4 py-2 bg-surface border border-border rounded-xl text-sm text-slate-300 hover:text-white transition-colors"
          >
            {cancelLabel}
          </button>
          <button
            onClick={onConfirm}
            className={`px-4 py-2 rounded-xl text-sm font-semibold transition-colors ${
              variant === "danger"
                ? "bg-warning/20 text-warning border border-warning/30 hover:bg-warning/30"
                : "bg-accent text-black hover:bg-amber-400"
            }`}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
