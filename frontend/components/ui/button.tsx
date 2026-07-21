import { type VariantProps, cva } from "class-variance-authority";
import { Loader2 } from "lucide-react";
import { type ButtonHTMLAttributes, forwardRef } from "react";

import { cn } from "@/lib/utils";

/**
 * Button — design-system variants. Visible focus ring, ≥44px hit area on
 * the default size, clear disabled + loading states (DESIGN-SYSTEM §4/§5).
 */
const buttonVariants = cva(
  "inline-flex select-none touch-manipulation items-center justify-center gap-2 rounded-md text-sm font-medium transition-[color,background-color,border-color,box-shadow,transform] duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-bg active:translate-y-px disabled:pointer-events-none disabled:opacity-50 disabled:shadow-none disabled:active:translate-y-0",
  {
    variants: {
      variant: {
        primary:
          "bg-primary text-primary-fg shadow-glow hover:bg-primary-active",
        secondary:
          "border border-border bg-surface text-fg shadow-sm hover:border-border-strong hover:bg-surface-2",
        ghost: "text-fg hover:bg-surface-2",
        destructive: "bg-danger text-white shadow-sm hover:bg-danger/90",
      },
      size: {
        sm: "h-9 px-3",
        md: "h-11 px-4",
        icon: "h-11 w-11",
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
