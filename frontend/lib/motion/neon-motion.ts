import { animate, cubicBezier } from "animejs";

/** Ignition Rule curve from docs/design-neon/DESIGN.md */
export const NEON_EASE = cubicBezier(0.16, 1, 0.3, 1);
export const NEON_IGNITE_MS = 360;
export const NEON_ENTER_MS = 220;

export function prefersReducedMotion(): boolean {
  if (typeof window === "undefined" || typeof window.matchMedia !== "function") {
    return false;
  }
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

/**
 * Slides the mobile drawer in from the left and fades its backdrop using
 * Anime.js v4, honouring `prefers-reduced-motion: reduce`.
 */
export function animateMobileDrawerIn(
  backdropEl: HTMLElement | null,
  drawerEl: HTMLElement | null,
): () => void {
  if (prefersReducedMotion()) return () => {};
  const anims: Array<{ cancel?: () => void }> = [];
  if (backdropEl) {
    anims.push(
      animate(backdropEl, {
        opacity: [0, 1],
        duration: 180,
        ease: "outQuad",
      }),
    );
  }
  if (drawerEl) {
    anims.push(
      animate(drawerEl, {
        translateX: ["-100%", "0%"],
        duration: NEON_ENTER_MS,
        ease: NEON_EASE,
      }),
    );
  }
  return () => {
    for (const a of anims) a.cancel?.();
  };
}
