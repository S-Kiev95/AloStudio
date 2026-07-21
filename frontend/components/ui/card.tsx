import { type HTMLAttributes } from "react";

import { cn } from "@/lib/utils";

/**
 * Card — an elevated surface. Soft shadow lifts it off the canvas (flat
 * outlines read as "unfinished"); `interactive` adds a hover lift for cards
 * that are themselves links/buttons.
 */
export function Card({
  className,
  interactive = false,
  ...props
}: HTMLAttributes<HTMLDivElement> & { interactive?: boolean }) {
  return (
    <div
      className={cn(
        "rounded-xl border border-border bg-surface shadow-sm",
        interactive &&
          "transition-[box-shadow,border-color,transform] duration-200 hover:-translate-y-0.5 hover:border-border-strong hover:shadow-md",
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
  // h2, not h1 — a card is a section, and pages carry their own h1. Balanced
  // wrapping keeps multi-word titles from orphaning a single word.
  return (
    <h2
      className={cn(
        "text-lg font-semibold tracking-tight text-fg text-balance",
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
    <p className={cn("mt-1 text-sm text-fg-muted text-pretty", className)} {...props} />
  );
}

export function CardContent({
  className,
  ...props
}: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("p-5", className)} {...props} />;
}
