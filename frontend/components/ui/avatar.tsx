import { cn } from "@/lib/utils";

/**
 * Avatar — a contact's initial on a colour that's deterministic from their
 * name, so the same person is always the same hue and a list reads as people
 * rather than a column of identical grey discs.
 *
 * The hue is decorative, not semantic (it never means "error"/"ok"), so it
 * lives off the status tokens on its own pleasant, distinct palette. Each chip
 * is `color-mix(hue, --surface)` for the wash + the raw hue for the glyph, so
 * it stays legible in both themes without a per-theme table.
 */
const HUES = [
  "#6366f1", // indigo
  "#0ea5e9", // sky
  "#14b8a6", // teal
  "#10b981", // emerald
  "#f59e0b", // amber
  "#f97316", // orange
  "#f43f5e", // rose
  "#8b5cf6", // violet
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
} as const;

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
  const initial = (trimmed.charAt(0) || "?").toUpperCase();
  const hue = hueFor(trimmed || "?");
  return (
    <span
      aria-hidden
      className={cn(
        "grid shrink-0 place-items-center rounded-full font-semibold",
        SIZES[size],
        className,
      )}
      style={{
        background: `color-mix(in srgb, ${hue} 18%, var(--surface))`,
        color: hue,
      }}
    >
      {initial}
    </span>
  );
}
