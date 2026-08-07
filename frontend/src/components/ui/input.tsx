import * as React from "react";
import { cn } from "@/lib/utils";

type InputProps = React.InputHTMLAttributes<HTMLInputElement>;

export const Input = React.forwardRef<HTMLInputElement, InputProps>(({ className, type, ...props }, ref) => {
  return (
    <input
      type={type}
      className={cn(
        "h-8 w-full rounded-md border border-line-2 bg-surface-content px-3 text-[12px] text-text outline-none transition-colors placeholder:text-text-4 focus:border-brand focus:ring-2 focus:ring-[var(--brand-soft)]",
        className,
      )}
      ref={ref}
      {...props}
    />
  );
});
Input.displayName = "Input";
