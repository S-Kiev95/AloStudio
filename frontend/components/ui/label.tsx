import { type LabelHTMLAttributes, forwardRef } from "react";

import { cn } from "@/lib/utils";

export const Label = forwardRef<
  HTMLLabelElement,
  LabelHTMLAttributes<HTMLLabelElement> & { required?: boolean }
>(({ className, required, children, ...props }, ref) => (
  <label
    ref={ref}
    className={cn("block text-sm font-medium text-fg", className)}
    {...props}
  >
    {children}
    {required ? (
      <span className="ml-0.5 text-danger" aria-hidden>
        *
      </span>
    ) : null}
  </label>
));
Label.displayName = "Label";
