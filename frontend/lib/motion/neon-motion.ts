"use client";

import {
  animate,
  createScope,
  cubicBezier,
  stagger,
  type Scope,
} from "animejs";
import {
  useEffect,
  useState,
  type DependencyList,
  type RefObject,
} from "react";

/** Ignition Rule curve & timings from docs/design-neon/DESIGN.md */
export const NEON_EASE = cubicBezier(0.16, 1, 0.3, 1);
export const NEON_IGNITE_MS = 360;
export const NEON_ENTER_MS = 220;
export const NEON_POPOVER_MS = 180;
export const NEON_COUNTER_MS = 420;
export const NEON_STAGGER_MAX_DELAY_MS = 240;

type Cancellable = { cancel?: () => void };

export function prefersReducedMotion(): boolean {
  if (typeof window === "undefined" || typeof window.matchMedia !== "function") {
    return false;
  }
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

/**
 * Reactive hook tracking `(prefers-reduced-motion: reduce)`.
 */
export function usePrefersReducedMotion(): boolean {
  const [reduced, setReduced] = useState<boolean>(() => prefersReducedMotion());

  useEffect(() => {
    if (typeof window === "undefined" || typeof window.matchMedia !== "function") {
      return;
    }
    const mql = window.matchMedia("(prefers-reduced-motion: reduce)");
    setReduced(mql.matches);
    const onChange = (e: MediaQueryListEvent) => setReduced(e.matches);
    mql.addEventListener?.("change", onChange);
    return () => {
      mql.removeEventListener?.("change", onChange);
    };
  }, []);

  return reduced;
}

/**
 * React wrapper over Anime.js v4 `createScope()` with built-in
 * `(prefers-reduced-motion: reduce)` awareness and automatic `scope.revert()`
 * on unmount or dependency changes (zero leaks in StrictMode / Vitest).
 */
export function useNeonScope(
  rootRef: RefObject<HTMLElement | null>,
  setup: (ctx: { scope: Scope; reduced: boolean }) => void,
  deps: DependencyList,
): void {
  useEffect(() => {
    const root = rootRef.current;
    if (!root) return;
    if (prefersReducedMotion()) {
      return;
    }
    const scope = createScope({
      root,
      mediaQueries: { reduced: "(prefers-reduced-motion: reduce)" },
    });
    scope.add((self) => {
      const reduced = Boolean(self?.matches?.reduced) || prefersReducedMotion();
      setup({ scope, reduced });
    });
    return () => {
      scope.revert();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
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
  const anims: Cancellable[] = [];
  if (backdropEl) {
    anims.push(
      animate(backdropEl, {
        opacity: [0, 1],
        duration: NEON_POPOVER_MS,
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

/**
 * Subtle scale + translate entrance for native `<dialog>` modals (180ms).
 */
export function animateDialogIn(dialogEl: HTMLElement | null): () => void {
  if (!dialogEl || prefersReducedMotion()) return () => {};
  const anim = animate(dialogEl, {
    opacity: [0, 1],
    scale: [0.97, 1],
    translateY: [6, 0],
    duration: NEON_POPOVER_MS,
    ease: NEON_EASE,
  });
  return () => {
    anim.cancel();
  };
}

/**
 * Subtle pop-in for topbar / composer popovers and menus (180ms).
 */
export function animatePopoverIn(
  panelEl: HTMLElement | null,
  direction: "down" | "up" = "down",
): () => void {
  if (!panelEl || prefersReducedMotion()) return () => {};
  const anim = animate(panelEl, {
    opacity: [0, 1],
    scale: [0.98, 1],
    translateY: [direction === "up" ? 4 : -4, 0],
    duration: NEON_POPOVER_MS,
    ease: NEON_EASE,
  });
  return () => {
    anim.cancel();
  };
}

/**
 * One-shot staggered entrance for card grids, Overview panels and Kanban
 * columns (`opacity: [0, 1]`, `translateY: [8, 0]`, strict delay cap of 240ms).
 */
export function animateStaggerIn(
  targets: HTMLElement[] | NodeListOf<HTMLElement> | null,
  options?: { stepMs?: number; maxDelayMs?: number; duration?: number },
): () => void {
  if (!targets || prefersReducedMotion()) return () => {};
  const nodes = Array.from(targets);
  if (nodes.length === 0) return () => {};
  const stepMs = options?.stepMs ?? 35;
  const maxDelayMs = options?.maxDelayMs ?? NEON_STAGGER_MAX_DELAY_MS;
  const duration = options?.duration ?? 280;

  const anim = animate(nodes, {
    opacity: [0, 1],
    translateY: [8, 0],
    duration,
    delay: (_el, i) => Math.min((i ?? 0) * stepMs, maxDelayMs),
    ease: NEON_EASE,
  });
  return () => {
    anim.cancel();
  };
}

/**
 * First-render numeric count-up for live KPI cards (`tabular-nums`, 420ms).
 * Immediately displays the final value when `prefers-reduced-motion` is set.
 */
export function animateCounter(
  el: HTMLElement | null,
  target: number,
  format: (n: number) => string,
): () => void {
  if (!el) return () => {};
  if (prefersReducedMotion() || !Number.isFinite(target) || target <= 0) {
    el.textContent = format(target);
    return () => {};
  }
  const state = { val: 0 };
  const anim = animate(state, {
    val: target,
    duration: NEON_COUNTER_MS,
    ease: NEON_EASE,
    onUpdate: () => {
      el.textContent = format(Math.round(state.val));
    },
    onComplete: () => {
      el.textContent = format(target);
    },
  });
  return () => {
    anim.cancel();
  };
}

/**
 * One-shot Ignition Rule cobalt flash (360ms) for a newly arrived realtime
 * conversation row in the Inbox list.
 */
export function animateRowIgnite(rowEl: HTMLElement | null): () => void {
  if (!rowEl || prefersReducedMotion()) return () => {};
  const anim = animate(rowEl, {
    boxShadow: [
      "inset 2px 0 0 0 rgba(47, 91, 240, 0.95), inset 0 0 18px 0 rgba(47, 91, 240, 0.22)",
      "inset 2px 0 0 0 rgba(47, 91, 240, 0), inset 0 0 0px 0 rgba(47, 91, 240, 0)",
    ],
    duration: NEON_IGNITE_MS,
    ease: NEON_EASE,
    onComplete: () => {
      rowEl.style.boxShadow = "";
    },
  });
  return () => {
    anim.cancel();
    rowEl.style.boxShadow = "";
  };
}

/**
 * Soft entrance for Agent chat messages and PendingActionCard (220ms).
 */
export function animateMessageIn(el: HTMLElement | null): () => void {
  if (!el || prefersReducedMotion()) return () => {};
  const anim = animate(el, {
    opacity: [0, 1],
    translateY: [6, 0],
    duration: NEON_ENTER_MS,
    ease: NEON_EASE,
  });
  return () => {
    anim.cancel();
  };
}

/**
 * Staggered Electrode Orange dots pulse for the AI Agent "Thinking..." state.
 */
export function animateElectrodeDots(
  dots: HTMLElement[] | NodeListOf<HTMLElement> | null,
): () => void {
  if (!dots || prefersReducedMotion()) return () => {};
  const nodes = Array.from(dots);
  if (nodes.length === 0) return () => {};
  const anim = animate(nodes, {
    opacity: [0.35, 1, 0.35],
    scale: [0.8, 1.15, 0.8],
    duration: 900,
    delay: stagger(120),
    loop: true,
    ease: "inOutSine",
  });
  return () => {
    anim.cancel();
  };
}

/**
 * Glides the 2px neon cobalt tube along a tab rail from the previous active
 * tab to the newly selected one (`180ms`, GPU transform-only).
 */
export function animateTabTube(
  tubeEl: HTMLElement | null,
  from: { left: number; width: number },
  to: { left: number; width: number },
  onComplete?: () => void,
): () => void {
  if (
    !tubeEl ||
    prefersReducedMotion() ||
    from.width <= 0 ||
    to.width <= 0
  ) {
    onComplete?.();
    return () => {};
  }
  tubeEl.style.opacity = "1";
  const anim = animate(tubeEl, {
    translateX: [from.left, to.left],
    width: [from.width, to.width],
    duration: NEON_POPOVER_MS,
    ease: NEON_EASE,
    onComplete: () => {
      tubeEl.style.opacity = "0";
      onComplete?.();
    },
  });
  return () => {
    anim.cancel();
    tubeEl.style.opacity = "0";
  };
}
