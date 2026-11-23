"use client";

import Link from "next/link";
import {
  createContext,
  useContext,
  useEffect,
  useRef,
  type HTMLAttributes,
  type KeyboardEvent,
  type ReactNode,
} from "react";

import { cn } from "@/lib/utils";
import { animateTabTube, prefersReducedMotion } from "@/lib/motion/neon-motion";

const TAB_TUBE_INSET_PX = 14;

/**
 * Animates a 2px glowing cobalt indicator bar smoothly from the previously
 * active tab to the newly active one using Anime.js v4 (180ms, NEON_EASE).
 * Falls back cleanly to the CSS `::after` bar on SSR, jsdom (zero-width rects)
 * and when `prefers-reduced-motion: reduce` is enabled.
 */
function useTabTubeGlide(
  railRef: React.RefObject<HTMLElement | null>,
  tubeRef: React.RefObject<HTMLSpanElement | null>,
  activeKey: string | null,
  activeSelector: string,
) {
  const prevRectRef = useRef<{ left: number; width: number } | null>(null);

  useEffect(() => {
    const rail = railRef.current;
    if (!rail) return;
    const activeEl = rail.querySelector<HTMLElement>(activeSelector);
    if (!activeEl) return;

    const railRect = rail.getBoundingClientRect();
    const elRect = activeEl.getBoundingClientRect();
    const next = {
      left:
        elRect.left - railRect.left + rail.scrollLeft + TAB_TUBE_INSET_PX,
      width: Math.max(0, elRect.width - TAB_TUBE_INSET_PX * 2),
    };
    const prev = prevRectRef.current;
    prevRectRef.current = next;

    if (
      !prev ||
      prev.width <= 0 ||
      next.width <= 0 ||
      (Math.abs(prev.left - next.left) < 1 &&
        Math.abs(prev.width - next.width) < 1) ||
      prefersReducedMotion()
    ) {
      return;
    }

    rail.setAttribute("data-gliding", "true");
    const cancel = animateTabTube(tubeRef.current, prev, next, () => {
      rail.removeAttribute("data-gliding");
    });
    return () => {
      cancel();
      rail.removeAttribute("data-gliding");
    };
  }, [activeKey, activeSelector, railRef, tubeRef]);
}

/**
 * Tabs — section tab rail (DESIGN.md §Tabs).
 * Tilt Neon 17px on a 1px Unlit Glass bottom rule, 4px apart, 10x14px padding;
 * the active tab carries Lit Text over a 2px glowing cobalt tube on the rail.
 * Wraps on desktop (`sm:flex-wrap`) and scrolls horizontally in one clean row
 * on mobile so the active tube never floats between wrapped rows.
 */
export function tabItemClassName(active: boolean, className?: string) {
  return cn(
    "neon-tab inline-flex shrink-0 items-center gap-1.5 whitespace-nowrap px-[14px] py-[10px] font-display text-[17px] font-normal leading-snug transition-colors",
    "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-neon",
    active ? "neon-tab-active text-lit" : "text-fg-muted hover:text-fg",
    className,
  );
}

type TabsContextValue = {
  value: string;
  onValueChange: (next: string) => void;
};

const TabsContext = createContext<TabsContextValue | null>(null);

export function Tabs({
  value,
  onValueChange,
  className,
  children,
}: {
  value: string;
  onValueChange: (next: string) => void;
  className?: string;
  children: ReactNode;
}) {
  return (
    <TabsContext.Provider value={{ value, onValueChange }}>
      <div className={className}>{children}</div>
    </TabsContext.Provider>
  );
}

export function TabsList({
  className,
  onKeyDown,
  children,
  ...props
}: HTMLAttributes<HTMLDivElement>) {
  const ctx = useContext(TabsContext);
  const railRef = useRef<HTMLDivElement>(null);
  const tubeRef = useRef<HTMLSpanElement>(null);

  useTabTubeGlide(
    railRef,
    tubeRef,
    ctx?.value ?? null,
    '[role="tab"][aria-selected="true"]',
  );

  function handleKeyDown(e: KeyboardEvent<HTMLDivElement>) {
    onKeyDown?.(e);
    if (e.defaultPrevented) return;
    if (
      e.key !== "ArrowRight" &&
      e.key !== "ArrowLeft" &&
      e.key !== "Home" &&
      e.key !== "End"
    ) {
      return;
    }
    const tabs = Array.from(
      e.currentTarget.querySelectorAll<HTMLButtonElement>(
        '[role="tab"]:not([disabled])',
      ),
    );
    if (tabs.length === 0) return;
    const currentIdx = tabs.indexOf(document.activeElement as HTMLButtonElement);
    if (currentIdx === -1) return;
    e.preventDefault();
    let nextIdx = currentIdx;
    if (e.key === "ArrowRight") nextIdx = (currentIdx + 1) % tabs.length;
    else if (e.key === "ArrowLeft")
      nextIdx = (currentIdx - 1 + tabs.length) % tabs.length;
    else if (e.key === "Home") nextIdx = 0;
    else if (e.key === "End") nextIdx = tabs.length - 1;
    tabs[nextIdx]?.focus();
    tabs[nextIdx]?.click();
  }

  return (
    <div
      ref={railRef}
      role="tablist"
      onKeyDown={handleKeyDown}
      className={cn(
        "neon-tab-rail relative flex flex-nowrap items-center gap-1 overflow-x-auto border-b border-glass sm:flex-wrap sm:overflow-visible",
        className,
      )}
      {...props}
    >
      {children}
      <span
        ref={tubeRef}
        aria-hidden="true"
        data-tab-glide=""
        className="pointer-events-none absolute bottom-0 left-0 h-[2px] rounded-[2px] bg-neon opacity-0"
        style={{ boxShadow: "var(--neon-tube-shadow)" }}
      />
    </div>
  );
}

export function TabsTrigger({
  value,
  className,
  children,
  disabled,
}: {
  value: string;
  className?: string;
  children: ReactNode;
  disabled?: boolean;
}) {
  const ctx = useContext(TabsContext);
  if (!ctx) {
    throw new Error("TabsTrigger must be used inside <Tabs>");
  }
  const active = ctx.value === value;
  return (
    <button
      type="button"
      role="tab"
      aria-selected={active}
      disabled={disabled}
      onClick={() => ctx.onValueChange(value)}
      className={cn(
        tabItemClassName(active),
        "disabled:pointer-events-none disabled:opacity-40",
        className,
      )}
    >
      {children}
    </button>
  );
}

export type NavTabItem = {
  href: string;
  label: ReactNode;
  active: boolean;
};

export function NavTabs({
  items,
  ariaLabel,
  className,
}: {
  items: NavTabItem[];
  ariaLabel?: string;
  className?: string;
}) {
  const navRef = useRef<HTMLElement>(null);
  const tubeRef = useRef<HTMLSpanElement>(null);
  const activeHref = items.find((i) => i.active)?.href ?? null;

  useTabTubeGlide(navRef, tubeRef, activeHref, '[aria-current="page"]');

  useEffect(() => {
    const activeEl = navRef.current?.querySelector<HTMLElement>(
      '[aria-current="page"]',
    );
    if (!activeEl || typeof activeEl.scrollIntoView !== "function") return;
    const reduced = prefersReducedMotion();
    activeEl.scrollIntoView({
      inline: "nearest",
      block: "nearest",
      behavior: reduced ? "auto" : "smooth",
    });
  }, [activeHref]);

  return (
    <nav
      ref={navRef}
      aria-label={ariaLabel}
      className={cn(
        "neon-tab-rail relative flex flex-nowrap items-center gap-1 overflow-x-auto border-b border-glass sm:flex-wrap sm:overflow-visible",
        className,
      )}
    >
      {items.map((item) => (
        <Link
          key={item.href}
          href={item.href}
          aria-current={item.active ? "page" : undefined}
          className={tabItemClassName(item.active)}
        >
          {item.label}
        </Link>
      ))}
      <span
        ref={tubeRef}
        aria-hidden="true"
        data-tab-glide=""
        className="pointer-events-none absolute bottom-0 left-0 h-[2px] rounded-[2px] bg-neon opacity-0"
        style={{ boxShadow: "var(--neon-tube-shadow)" }}
      />
    </nav>
  );
}
