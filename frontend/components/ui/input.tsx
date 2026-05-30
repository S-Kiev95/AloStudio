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
      "h-11 w-full rounded-md border border-border bg-surface px-3 text-sm text-fg",
      "placeholder:text-fg-muted",
      "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-bg",
      "disabled:cursor-not-allowed disabled:opacity-50",
      "aria-[invalid=true]:border-danger aria-[invalid=true]:ring-danger",
      className,
    )}
    {...props}
  />
));
Input.displayName = "Input";
