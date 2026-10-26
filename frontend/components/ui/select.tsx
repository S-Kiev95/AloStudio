import { type SelectHTMLAttributes, forwardRef } from "react";

import { cn } from "@/lib/utils";

export interface SelectProps
  extends Omit<SelectHTMLAttributes<HTMLSelectElement>, "size"> {
  size?: "sm" | "md";
}

export const selectClassName = (size: "sm" | "md" = "md") =>
  cn(
    "glass-field rounded-control border border-glass bg-field text-fg",
    "disabled:cursor-not-allowed disabled:opacity-50",
    "aria-[invalid=true]:border-danger aria-[invalid=true]:shadow-none",
    size === "sm" ? "h-9 px-2.5 text-xs sm:text-sm" : "h-11 w-full px-3 text-sm",
  );

export const Select = forwardRef<HTMLSelectElement, SelectProps>(
  ({ className, size = "md", ...props }, ref) => (
    <select
      ref={ref}
      className={cn(selectClassName(size), className)}
      {...props}
    />
  ),
);
Select.displayName = "Select";
