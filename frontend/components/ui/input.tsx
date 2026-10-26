import { type InputHTMLAttributes, forwardRef } from "react";

import { cn } from "@/lib/utils";

export const Input = forwardRef<
  HTMLInputElement,
  InputHTMLAttributes<HTMLInputElement>
>(({ className, type = "text", ...props }, ref) => (
  <input
    ref={ref}
    type={type}
    className={cn(
      "glass-field h-11 w-full rounded-control border border-glass bg-field px-3.5 text-sm text-fg",
      "placeholder:text-fg-muted",
      "disabled:cursor-not-allowed disabled:opacity-50",
      "aria-[invalid=true]:border-danger aria-[invalid=true]:shadow-none",
      className,
    )}
    {...props}
  />
));
Input.displayName = "Input";
