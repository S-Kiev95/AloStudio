import { type TextareaHTMLAttributes, forwardRef } from "react";

import { cn } from "@/lib/utils";

export const Textarea = forwardRef<
  HTMLTextAreaElement,
  TextareaHTMLAttributes<HTMLTextAreaElement>
>(({ className, ...props }, ref) => (
  <textarea
    ref={ref}
    className={cn(
      "glass-field w-full resize-none rounded-control border border-glass bg-field px-3.5 py-2.5 text-sm text-fg",
      "placeholder:text-fg-muted",
      "disabled:cursor-not-allowed disabled:opacity-50",
      "aria-[invalid=true]:border-danger aria-[invalid=true]:shadow-none",
      className,
    )}
    {...props}
  />
));
Textarea.displayName = "Textarea";
