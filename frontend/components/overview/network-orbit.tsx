import type { CSSProperties } from "react";

import {
  Facebook,
  Gmail,
  type IconComponent,
  Instagram,
  Messenger,
  Telegram,
  Threads,
  TikTok,
  WhatsApp,
  XLogo,
  YouTube,
} from "@/components/ui/brand-icons";
import { cn } from "@/lib/utils";

/**
 * Two concentric -14deg tilted ellipses inside a 380x244 stage (center 190,122).
 * Sharing the exact SVG path string between `<svg><path>` and CSS `offset-path`
 * keeps every network bubble centered on the 1px `--neon-glass` orbit line.
 */
const STAGE_W = 380;
const STAGE_H = 244;
const INNER_PATH =
  "M 98.79 144.74 A 94 56 -14 1 1 281.21 99.26 A 94 56 -14 1 1 98.79 144.74 Z";
const OUTER_PATH =
  "M 42.52 158.77 A 152 92 -14 1 1 337.48 85.23 A 152 92 -14 1 1 42.52 158.77 Z";

const INNER_DURATION_S = 46;
const OUTER_DURATION_S = 58;

interface OrbitNode {
  key: string;
  icon: IconComponent;
  iconClassName?: string;
  ring: string;
  glow: string;
  /** Fraction [0..1) along the keyframe cycle at t = 0. */
  phase: number;
}

const INNER_NODES: readonly OrbitNode[] = [
  {
    key: "whatsapp",
    icon: WhatsApp,
    ring: "rgba(37, 211, 102, 0.48)",
    glow: "rgba(37, 211, 102, 0.32)",
    phase: 0.08,
  },
  {
    key: "instagram",
    icon: Instagram,
    ring: "rgba(225, 48, 108, 0.50)",
    glow: "rgba(225, 48, 108, 0.34)",
    phase: 0.33,
  },
  {
    key: "messenger",
    icon: Messenger,
    ring: "rgba(0, 132, 255, 0.50)",
    glow: "rgba(0, 132, 255, 0.34)",
    phase: 0.58,
  },
  {
    key: "telegram",
    icon: Telegram,
    ring: "rgba(38, 165, 228, 0.50)",
    glow: "rgba(38, 165, 228, 0.32)",
    phase: 0.83,
  },
];

const OUTER_NODES: readonly OrbitNode[] = [
  {
    key: "threads",
    icon: Threads,
    iconClassName: "text-fg",
    ring: "rgba(231, 236, 255, 0.34)",
    glow: "rgba(231, 236, 255, 0.20)",
    phase: 0.88,
  },
  {
    key: "gmail",
    icon: Gmail,
    ring: "rgba(234, 67, 53, 0.50)",
    glow: "rgba(234, 67, 53, 0.32)",
    phase: 0.71,
  },
  {
    key: "tiktok",
    icon: TikTok,
    iconClassName: "text-[#009995] dark:text-[#25F4EE]",
    ring: "rgba(37, 244, 238, 0.46)",
    glow: "rgba(37, 244, 238, 0.30)",
    phase: 0.55,
  },
  {
    key: "facebook",
    icon: Facebook,
    ring: "rgba(8, 102, 255, 0.52)",
    glow: "rgba(8, 102, 255, 0.34)",
    phase: 0.38,
  },
  {
    key: "youtube",
    icon: YouTube,
    ring: "rgba(255, 0, 0, 0.50)",
    glow: "rgba(255, 0, 0, 0.32)",
    phase: 0.21,
  },
  {
    key: "x",
    icon: XLogo,
    iconClassName: "text-fg",
    ring: "rgba(231, 236, 255, 0.34)",
    glow: "rgba(231, 236, 255, 0.20)",
    phase: 0.04,
  },
];

function OrbitBubble({
  node,
  path,
  durationS,
  direction,
}: {
  node: OrbitNode;
  path: string;
  durationS: number;
  direction: "cw" | "ccw";
}) {
  const Icon = node.icon;
  const startPct =
    direction === "cw" ? node.phase * 100 : (1 - node.phase) * 100;
  const style = {
    "--orbit-path": `path("${path}")`,
    "--orbit-start": `${startPct.toFixed(2)}%`,
    "--orbit-duration": `${durationS}s`,
    "--orbit-delay": `${(-node.phase * durationS).toFixed(2)}s`,
    "--bubble-ring": node.ring,
    "--bubble-glow": node.glow,
  } as CSSProperties;

  return (
    <span
      data-network={node.key}
      style={style}
      className={cn(
        "orbit-bubble",
        direction === "cw" ? "orbit-bubble-cw" : "orbit-bubble-ccw",
      )}
    >
      <Icon
        aria-hidden="true"
        className={cn("h-4 w-4", node.iconClassName)}
      />
    </span>
  );
}

/**
 * Decorative network orbit for Inicio (PLAN.motion-neon §5).
 * Marked `aria-hidden` and pointer-inert with zero focusable controls.
 */
export function NetworkOrbit({ className }: { className?: string }) {
  return (
    <div
      aria-hidden="true"
      className={cn(
        "pointer-events-none relative h-[172px] w-[268px] shrink-0 select-none sm:h-[205px] sm:w-[320px] xl:h-[244px] xl:w-[380px]",
        className,
      )}
    >
      <div className="relative h-[244px] w-[380px] origin-top-left scale-[0.705] sm:scale-[0.842] xl:scale-100">
        <svg
          viewBox={`0 0 ${STAGE_W} ${STAGE_H}`}
          className="h-full w-full overflow-visible"
        >
          <path
            d={OUTER_PATH}
            fill="none"
            stroke="var(--neon-glass)"
            strokeWidth="1"
          />
          <path
            d={INNER_PATH}
            fill="none"
            stroke="var(--neon-glass)"
            strokeWidth="1"
          />
        </svg>

        {OUTER_NODES.map((node) => (
          <OrbitBubble
            key={node.key}
            node={node}
            path={OUTER_PATH}
            durationS={OUTER_DURATION_S}
            direction="ccw"
          />
        ))}

        {INNER_NODES.map((node) => (
          <OrbitBubble
            key={node.key}
            node={node}
            path={INNER_PATH}
            durationS={INNER_DURATION_S}
            direction="cw"
          />
        ))}

        <div className="orbit-core absolute left-1/2 top-1/2 h-[72px] w-[72px] -translate-x-1/2 -translate-y-1/2 overflow-hidden rounded-full">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src="/brand/alostudio-icon-512.png"
            alt=""
            draggable={false}
            className="h-full w-full scale-[1.3] object-cover"
          />
        </div>
      </div>
    </div>
  );
}
