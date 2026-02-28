import { clsx } from "clsx";
import { Spinner } from "./Spinner";
import type { ButtonHTMLAttributes, ReactNode } from "react";

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "ghost" | "danger" | "outline";
  size?: "sm" | "md" | "lg";
  loading?: boolean;
  children: ReactNode;
}

const base =
  "inline-flex items-center justify-center gap-2 rounded-lg font-medium transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand/70 disabled:opacity-50 disabled:cursor-not-allowed";

const variants = {
  primary: "bg-brand text-white hover:bg-brand-600 active:scale-[.98]",
  ghost: "text-gray-300 hover:bg-surface-200 hover:text-white",
  danger: "bg-danger/10 text-danger border border-danger/30 hover:bg-danger/20",
  outline: "border border-gray-700 text-gray-300 hover:border-gray-500 hover:text-white",
};

const sizes = { sm: "text-xs px-3 py-1.5", md: "text-sm px-4 py-2", lg: "text-base px-5 py-2.5" };

export function Button({ variant = "primary", size = "md", loading, children, className, disabled, ...rest }: Props) {
  return (
    <button className={clsx(base, variants[variant], sizes[size], className)} disabled={disabled || loading} {...rest}>
      {loading && <Spinner size="sm" />}
      {children}
    </button>
  );
}
