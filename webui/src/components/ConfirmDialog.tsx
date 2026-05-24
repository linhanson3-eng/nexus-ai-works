import { AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";

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
    <Dialog open onOpenChange={() => onCancel()}>
      <DialogContent className="sm:max-w-sm">
        <DialogHeader>
          <div className="flex items-start gap-3">
            <div
              className={`w-10 h-10 rounded-lg flex items-center justify-center shrink-0 ${
                variant === "danger" ? "bg-destructive/10" : "bg-primary/10"
              }`}
            >
              <AlertTriangle
                className={`w-5 h-5 ${
                  variant === "danger" ? "text-destructive" : "text-primary"
                }`}
              />
            </div>
            <div>
              <DialogTitle className="text-sm">{title}</DialogTitle>
              <DialogDescription className="text-sm mt-1">{message}</DialogDescription>
            </div>
          </div>
        </DialogHeader>
        <DialogFooter>
          <Button variant="outline" onClick={onCancel}>
            {cancelLabel}
          </Button>
          <Button
            variant={variant === "danger" ? "destructive" : "default"}
            onClick={onConfirm}
          >
            {confirmLabel}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
