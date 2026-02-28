import { useState, useCallback } from "react";
import { clsx } from "clsx";
import { CheckCircle, XCircle, AlertTriangle, Info, X } from "lucide-react";

type ToastType = "success" | "error" | "warning" | "info";

interface Toast {
  id: number;
  type: ToastType;
  title: string;
  message?: string;
}

let _add: ((t: Omit<Toast, "id">) => void) | null = null;
let _id = 0;

export function toast(type: ToastType, title: string, message?: string) {
  _add?.({ type, title, message });
}
toast.success = (title: string, msg?: string) => toast("success", title, msg);
toast.error = (title: string, msg?: string) => toast("error", title, msg);
toast.warning = (title: string, msg?: string) => toast("warning", title, msg);
toast.info = (title: string, msg?: string) => toast("info", title, msg);

const icons = {
  success: <CheckCircle size={16} className="text-success shrink-0" />,
  error: <XCircle size={16} className="text-danger shrink-0" />,
  warning: <AlertTriangle size={16} className="text-warning shrink-0" />,
  info: <Info size={16} className="text-brand-400 shrink-0" />,
};

export function ToastContainer() {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const add = useCallback((t: Omit<Toast, "id">) => {
    const id = ++_id;
    setToasts((prev) => [...prev, { ...t, id }]);
    setTimeout(() => setToasts((prev) => prev.filter((x) => x.id !== id)), 4500);
  }, []);

  _add = add;

  const dismiss = (id: number) => setToasts((prev) => prev.filter((x) => x.id !== id));

  return (
    <div className="fixed bottom-4 right-4 z-[100] flex flex-col gap-2 pointer-events-none">
      {toasts.map((t) => (
        <div
          key={t.id}
          className={clsx(
            "flex items-start gap-3 px-4 py-3 rounded-xl border shadow-xl",
            "bg-surface-50 pointer-events-auto min-w-[260px] max-w-sm animate-slide-up",
            t.type === "error" ? "border-danger/30" : "border-gray-700/60"
          )}
        >
          {icons[t.type]}
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-white">{t.title}</p>
            {t.message && <p className="text-xs text-gray-400 mt-0.5">{t.message}</p>}
          </div>
          <button onClick={() => dismiss(t.id)} className="text-gray-500 hover:text-white transition-colors shrink-0">
            <X size={14} />
          </button>
        </div>
      ))}
    </div>
  );
}
