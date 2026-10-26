import { type HTMLAttributes } from "react";

import { cn } from "@/lib/utils";

/**
 * Card — unlit cobalt-glass container (8px corners, 1px Unlit Glass border,
 * zero shadow and zero glow — DESIGN.md Light-Not-Lift Rule).
 */
export function Card({
  className,
  interactive = false,
  ...props
}: HTMLAttributes<HTMLDivElement> & { interactive?: boolean }) {
  return (
    <div
      className={cn(
        "rounded-md border border-glass bg-surface",
        interactive &&
          "transition-colors duration-200 hover:border-border-strong hover:bg-hover-glass",
        className,
      )}
      {...props}
    />
  );
}

export function CardHeader({
  className,
  ...props
}: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("p-5 pb-3", className)} {...props} />;
}

export function CardTitle({
  className,
  ...props
}: HTMLAttributes<HTMLHeadingElement>) {
  return (
    <h2
      className={cn(
        "text-base font-medium leading-[1.4] text-fg text-balance",
        className,
      )}
      {...props}
    />
  );
}

export function CardDescription({
  className,
  ...props
}: HTMLAttributes<HTMLParagraphElement>) {
  return (
    <p
      className={cn("mt-1 text-sm leading-[1.45] text-fg-muted text-pretty", className)}
      {...props}
    />
  );
}

export function CardContent({
  className,
  ...props
}: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("p-5", className)} {...props} />;
}
