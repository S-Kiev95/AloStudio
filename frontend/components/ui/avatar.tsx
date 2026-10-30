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

function initialsFor(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length >= 2) {
    return `${parts[0].charAt(0)}${parts[parts.length - 1].charAt(0)}`.toUpperCase();
  }
  return (parts[0]?.charAt(0) || "?").toUpperCase();
}

export function Avatar({
  name,
  size = "md",
  className,
}: {
  name: string;
  size?: keyof typeof SIZES;
  className?: string;
}) {
  const trimmed = name.trim();
  const initial = initialsFor(trimmed);
  const hue = hueFor(trimmed || "?");
  return (
    <span
      aria-hidden
      className={cn(
        "grid shrink-0 place-items-center rounded-full font-medium ring-1 ring-inset ring-glass",
        SIZES[size],
        className,
      )}
      style={{
        background: `color-mix(in srgb, ${hue} 20%, var(--neon-focused-glass))`,
        color: hue,
      }}
    >
      {initial}
    </span>
  );
}
