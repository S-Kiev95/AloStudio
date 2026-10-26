import { type VariantProps, cva } from "class-variance-authority";
import { Loader2 } from "lucide-react";
import { type ButtonHTMLAttributes, forwardRef } from "react";

import { cn } from "@/lib/utils";

/**
 * Button — "The Hand-Bent Neon Room" (docs/design-neon/DESIGN.md).
 * Primary is the cobalt lit tube (40px tall, 10px radius, 24px horizontal
 * padding, >=44px touch target). Secondary, simple, ghost and destructive
 * drop the cobalt tube; `ai` uses Electrode Orange exclusively for AI actions.
 */
const buttonVariants = cva(
  "relative inline-flex select-none touch-manipulation items-center justify-center gap-2 rounded-control text-sm font-medium transition-[color,background-color,border-color,box-shadow,opacity] duration-200 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-neon disabled:pointer-events-none disabled:opacity-50 disabled:shadow-none",
  {
    variants: {
      variant: {
        primary: "lit-tube-solid",
        secondary:
          "border border-glass bg-surface-2 text-fg hover:border-border-strong hover:bg-hover-glass",
        simple:
          "border border-glass bg-btn-simple text-fg hover:opacity-85",
        ghost: "text-fg-muted hover:bg-hover-glass hover:text-fg",
        destructive: "bg-danger-solid text-white hover:opacity-90",
        ai: "bg-electrode text-white hover:opacity-90",
      },
      size: {
        sm: "h-9 px-3.5 after:absolute after:-inset-y-1 after:inset-x-0 after:content-['']",
        md: "h-10 px-6 after:absolute after:-inset-y-0.5 after:inset-x-0 after:content-['']",
        icon: "h-10 w-10 after:absolute after:-inset-0.5 after:content-['']",
      },
    },
    defaultVariants: { variant: "primary", size: "md" },
  },
);

export interface ButtonProps
  extends ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  loading?: boolean;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, loading, disabled, children, ...props }, ref) => (
    <button
      ref={ref}
      className={cn(buttonVariants({ variant, size }), className)}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      {...props}
    >
      {loading ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> : null}
      {children}
    </button>
  ),
);
Button.displayName = "Button";

export { buttonVariants };
