import { clsx } from "clsx";
import { X } from "lucide-react";
import type { ReactNode } from "react";
import { useEffect } from "react";

interface Props {
  open: boolean;
  onClose: () => void;
  title: string;
  subtitle?: string;
  children: ReactNode;
  size?: "sm" | "md" | "lg" | "xl";
  className?: string;
}

const sizes = {
  sm: "max-w-sm",
  md: "max-w-md",
  lg: "max-w-lg",
  xl: "max-w-2xl",
};

export function Modal({ open, onClose, title, subtitle, children, size = "md", className }: Props) {
  // Close on Escape
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 animate-fade-in">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/70 backdrop-blur-sm"
        onClick={onClose}
      />
      {/* Panel */}
      <div
        className={clsx(
          "relative z-10 w-full rounded-2xl bg-surface-50 border border-gray-700/60",
          "shadow-2xl animate-slide-up",
          sizes[size],
          className
        )}
      >
        {/* Header */}
        <div className="flex items-start justify-between p-5 border-b border-gray-700/50">
          <div>
            <h2 className="text-base font-semibold text-white">{title}</h2>
            {subtitle && <p className="text-sm text-gray-400 mt-0.5">{subtitle}</p>}
          </div>
          <button
            onClick={onClose}
            className="text-gray-500 hover:text-white transition-colors -mt-0.5 -mr-1 p-1 rounded-lg hover:bg-surface-200"
          >
            <X size={18} />
          </button>
        </div>
        {/* Body */}
        <div className="p-5">{children}</div>
      </div>
    </div>
  );
}
