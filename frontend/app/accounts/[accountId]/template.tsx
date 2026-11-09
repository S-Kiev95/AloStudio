"use client";

import { usePathname } from "next/navigation";
import { useEffect, useLayoutEffect, type ReactNode } from "react";

type ViewTransitionDocument = Document & {
  startViewTransition?: (updateCallback: () => Promise<void> | void) => {
    finished?: Promise<void>;
    ready?: Promise<void>;
    updateCallbackDone?: Promise<void>;
    skipTransition?: () => void;
  };
};

const useIsomorphicLayoutEffect =
  typeof window !== "undefined" ? useLayoutEffect : useEffect;

let lastCommittedPathname: string | null = null;
let pendingTransitionResolve: (() => void) | null = null;
let pendingTransitionTimer: ReturnType<typeof setTimeout> | null = null;

function flushPendingTransition(): void {
  if (pendingTransitionTimer !== null) {
    clearTimeout(pendingTransitionTimer);
    pendingTransitionTimer = null;
  }
  if (pendingTransitionResolve) {
    const resolve = pendingTransitionResolve;
    pendingTransitionResolve = null;
    resolve();
  }
}

function canStartViewTransition(): boolean {
  if (typeof document === "undefined" || typeof window === "undefined") {
    return false;
  }
  const doc = document as ViewTransitionDocument;
  if (typeof doc.startViewTransition !== "function") {
    return false;
  }
  if (
    typeof window.matchMedia === "function" &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches
  ) {
    return false;
  }
  return true;
}

export function resetViewTransitionStateForTests(): void {
  flushPendingTransition();
  lastCommittedPathname = null;
}

export default function AccountTemplate({
  children,
}: {
  children: ReactNode;
}) {
  const pathname = usePathname() ?? "";

  useEffect(() => {
    function handleDocumentClick(event: MouseEvent) {
      if (
        event.defaultPrevented ||
        event.button !== 0 ||
        event.metaKey ||
        event.ctrlKey ||
        event.shiftKey ||
        event.altKey
      ) {
        return;
      }
      const target = event.target as Element | null;
      const anchor = target?.closest?.("a[href]") as HTMLAnchorElement | null;
      if (!anchor) return;
      if (anchor.target && anchor.target !== "_self") return;
      if (anchor.hasAttribute("download")) return;

      let url: URL;
      try {
        url = new URL(anchor.href, window.location.href);
      } catch {
        return;
      }
      if (url.origin !== window.location.origin) return;
      if (!url.pathname.startsWith("/accounts/")) return;
      if (
        url.pathname === window.location.pathname &&
        url.search === window.location.search
      ) {
        return;
      }
      if (!canStartViewTransition()) return;

      flushPendingTransition();
      const doc = document as ViewTransitionDocument;
      try {
        doc.startViewTransition?.(
          () =>
            new Promise<void>((resolve) => {
              pendingTransitionResolve = resolve;
              pendingTransitionTimer = setTimeout(() => {
                flushPendingTransition();
              }, 240);
            }),
        );
      } catch {
        flushPendingTransition();
      }
    }

    document.addEventListener("click", handleDocumentClick, true);
    return () => {
      document.removeEventListener("click", handleDocumentClick, true);
    };
  }, []);

  useIsomorphicLayoutEffect(() => {
    if (!pathname) return;

    if (lastCommittedPathname === null) {
      lastCommittedPathname = pathname;
      return;
    }

    if (lastCommittedPathname === pathname) {
      return;
    }

    lastCommittedPathname = pathname;

    if (pendingTransitionResolve) {
      flushPendingTransition();
      return;
    }

    if (!canStartViewTransition()) {
      return;
    }

    const doc = document as ViewTransitionDocument;
    try {
      doc.startViewTransition?.(() => {});
    } catch {
      // Ignore browser view-transition errors so navigation never breaks.
    }
  }, [pathname]);

  return <div className="vt-page page-enter">{children}</div>;
}
