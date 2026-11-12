"use client";

import { useState } from "react";

import { cn } from "@/lib/utils";

/**
 * Avatar — deterministic cool-spectrum hue per contact name within the
 * cobalt-glass palette (never Electrode Orange, never warning).
 */
const HUES = [
  "#3d6bff", // cobalt
  "#0ea5e9", // sky
  "#14b8a6", // teal
  "#10b981", // emerald
  "#38bdf8", // cyan
  "#818cf8", // periwinkle
  "#2dd4bf", // mint
  "#fb7185", // rose
];

function hueFor(seed: string): string {
  let h = 0;
  for (let i = 0; i < seed.length; i += 1) {
    h = (h * 31 + seed.charCodeAt(i)) >>> 0;
  }
  return HUES[h % HUES.length];
}

const SIZES = {
  sm: "h-8 w-8 text-xs",
  md: "h-9 w-9 text-sm",
  lg: "h-11 w-11 text-base",
  xl: "h-16 w-16 text-lg",
} as const;

/** First letter (or digit) of the first and last word. Symbols and asides
 *  in brackets don't count, so "Lucía Pereira (demo)" gives "LP", not "L(". */
export function initialsFor(name: string): string {
  const withoutAsides = name.replace(/[([{][^)\]}]*[)\]}]/g, " ");
  const firsts = (withoutAsides.trim() ? withoutAsides : name)
    .split(/\s+/)
    .map((word) => word.match(/[\p{L}\p{N}]/u)?.[0])
    .filter((c): c is string => Boolean(c));
  if (firsts.length === 0) return "?";
  const pair =
    firsts.length >= 2 ? firsts[0] + firsts[firsts.length - 1] : firsts[0];
  return pair.toLocaleUpperCase();
}

export function Avatar({
  name,
  src,
  size = "md",
  className,
}: {
  name: string;
  /** Profile picture; the initials show without one or if it fails to load. */
  src?: string | null;
  size?: keyof typeof SIZES;
  className?: string;
}) {
  const trimmed = name.trim();
  const initial = initialsFor(trimmed);
  const hue = hueFor(trimmed || "?");
  // Remembers which picture failed, so a new one gets its own try.
  const [failed, setFailed] = useState<string | null>(null);
  const showImage = Boolean(src) && failed !== src;
  return (
    <span
      aria-hidden
      className={cn(
        "relative grid shrink-0 place-items-center overflow-hidden rounded-full font-medium ring-1 ring-inset ring-glass",
        SIZES[size],
        className,
      )}
      style={{
        background: `color-mix(in srgb, ${hue} 20%, var(--neon-focused-glass))`,
        color: hue,
      }}
    >
      {initial}
      {showImage ? (
        // A plain img: the picture comes through the authenticated proxy,
        // which next/image's optimizer can't reach with the session.
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={src!}
          alt=""
          loading="lazy"
          decoding="async"
          onError={() => setFailed(src!)}
          className="absolute inset-0 h-full w-full object-cover"
        />
      ) : null}
    </span>
  );
}
