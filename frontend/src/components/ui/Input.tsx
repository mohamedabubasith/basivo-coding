import { clsx } from "clsx";
import type { InputHTMLAttributes, ReactNode } from "react";
import { forwardRef } from "react";

interface Props extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  hint?: string;
  leftIcon?: ReactNode;
  rightSlot?: ReactNode;
}

export const Input = forwardRef<HTMLInputElement, Props>(
  ({ label, error, hint, leftIcon, rightSlot, className, ...rest }, ref) => (
    <div className="flex flex-col gap-1">
      {label && (
        <label className="text-sm font-medium text-gray-300">{label}</label>
      )}
      <div className="relative flex items-center">
        {leftIcon && (
          <span className="absolute left-3 text-gray-500 pointer-events-none">{leftIcon}</span>
        )}
        <input
          ref={ref}
          className={clsx(
            "w-full rounded-lg bg-surface-200 border text-sm text-gray-100 placeholder-gray-500",
            "px-3 py-2 focus:outline-none focus:ring-2 focus:ring-brand/60 transition-all",
            error ? "border-danger/60 focus:ring-danger/40" : "border-gray-700 focus:border-gray-600",
            leftIcon && "pl-9",
            rightSlot && "pr-10",
            className
          )}
          {...rest}
        />
        {rightSlot && (
          <span className="absolute right-2">{rightSlot}</span>
        )}
      </div>
      {error && <p className="text-xs text-danger">{error}</p>}
      {hint && !error && <p className="text-xs text-gray-500">{hint}</p>}
    </div>
  )
);
Input.displayName = "Input";
