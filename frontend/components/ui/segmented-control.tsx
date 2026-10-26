"use client";

import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

/**
 * SegmentedControl — unlit glass switcher for view modes, time ranges, and
 * filter pills (DESIGN.md Lit-Means-Current Rule: selection uses Focused Glass
 * and Lit Text, never a halo).
 */
export type SegmentedOption<T extends string | number | undefined> = {
  value: T;
  label: ReactNode;
  disabled?: boolean;
};

export function SegmentedControl<T extends string | number | undefined>({
  value,
  onValueChange,
  options,
  ariaLabel,
  size = "md",
  className,
}: {
  value: T;
  onValueChange: (next: T) => void;
  options: readonly SegmentedOption<T>[];
  ariaLabel?: string;
  size?: "sm" | "md";
  className?: string;
}) {
  return (
    <div
      role={ariaLabel ? "group" : undefined}
      aria-label={ariaLabel}
      className={cn(
        "inline-flex flex-wrap items-center gap-1 rounded-control border border-glass bg-field p-1",
        className,
      )}
    >
      {options.map((opt, idx) => {
        const active = opt.value === value;
        return (
          <button
            key={String(opt.value ?? `opt-${idx}`)}
            type="button"
            disabled={opt.disabled}
            aria-pressed={active}
            onClick={() => onValueChange(opt.value)}
            className={cn(
              "inline-flex items-center gap-1.5 rounded-md font-medium transition-colors",
              "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-neon",
              "disabled:pointer-events-none disabled:opacity-40",
              size === "sm" ? "px-2.5 py-1 text-xs" : "px-3 py-1.5 text-sm",
              active
                ? "bg-focused text-lit"
                : "text-fg-muted hover:bg-hover-glass hover:text-fg",
            )}
          >
            {opt.label}
          </button>
        );
      })}
    </div>
  );
}
