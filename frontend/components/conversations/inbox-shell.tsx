"use client";

import { PanelLeftClose, PanelLeftOpen } from "lucide-react";
import { usePathname } from "next/navigation";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
  type KeyboardEvent as ReactKeyboardEvent,
  type PointerEvent as ReactPointerEvent,
  type ReactNode,
} from "react";

import { cn } from "@/lib/utils";

export const INBOX_LIST_COLLAPSED_KEY = "alostudio:inbox-list-collapsed";
export const INBOX_CONTACT_COLLAPSED_KEY = "alostudio:inbox-contact-collapsed";
export const INBOX_DETAILS_COLLAPSED_KEY = "alostudio:inbox-details-collapsed";
export const INBOX_HEIGHT_OFFSET_KEY = "alostudio:inbox-height-offset";
export const DEFAULT_INBOX_MAX_STRETCH_PX = 120;
export const INBOX_STRETCH_STEP_PX = 24;

const useIsomorphicLayoutEffect =
  typeof window !== "undefined" ? useLayoutEffect : useEffect;

export function readStoredPanelCollapsed(key: string): boolean {
  if (typeof window === "undefined") return false;
  try {
    const raw = window.localStorage.getItem(key);
    return raw === "1" || raw === "true";
  } catch {
    return false;
  }
}

export function writeStoredPanelCollapsed(
  key: string,
  collapsed: boolean,
): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(key, collapsed ? "1" : "0");
  } catch {
    // Ignore storage errors (private mode / quota).
  }
}

export function clampInboxStretch(
  value: number,
  maxStretch: number = DEFAULT_INBOX_MAX_STRETCH_PX,
): number {
  if (!Number.isFinite(value)) return 0;
  const safeMax = Number.isFinite(maxStretch)
    ? Math.max(0, Math.round(maxStretch))
    : 0;
  return Math.min(safeMax, Math.max(0, Math.round(value)));
}

export function readStoredPanelStretch(
  key: string = INBOX_HEIGHT_OFFSET_KEY,
): number {
  if (typeof window === "undefined") return 0;
  try {
    const raw = window.localStorage.getItem(key);
    if (raw === null || raw.trim() === "") return 0;
    const parsed = Number(raw);
    if (!Number.isFinite(parsed) || parsed <= 0) return 0;
    return Math.round(parsed);
  } catch {
    return 0;
  }
}

export function writeStoredPanelStretch(
  key: string,
  stretchPx: number,
): void {
  if (typeof window === "undefined") return;
  try {
    const normalized = Number.isFinite(stretchPx)
      ? Math.max(0, Math.round(stretchPx))
      : 0;
    window.localStorage.setItem(key, String(normalized));
  } catch {
    // Ignore storage errors (private mode / quota).
  }
}

function measureMaxInboxStretch(anchorEl: HTMLElement | null): number {
  if (typeof window === "undefined") return DEFAULT_INBOX_MAX_STRETCH_PX;
  if (anchorEl) {
    const anchorRect = anchorEl.getBoundingClientRect();
    const mainEl =
      anchorEl.closest("#main-content") ??
      anchorEl.closest("main") ??
      document.getElementById("main-content") ??
      anchorEl.parentElement;
    if (mainEl) {
      const mainRect = mainEl.getBoundingClientRect();
      const diff = Math.round(anchorRect.top - mainRect.top);
      if (diff > 0) return diff;
    }
    if (anchorRect.top > 0) {
      return Math.round(anchorRect.top);
    }
  }
  const vh = window.innerHeight;
  if (Number.isFinite(vh) && vh > 0 && vh < 720) {
    return Math.max(
      INBOX_STRETCH_STEP_PX,
      Math.min(DEFAULT_INBOX_MAX_STRETCH_PX, Math.round((vh - 480) * 0.5)),
    );
  }
  return DEFAULT_INBOX_MAX_STRETCH_PX;
}

type InboxPanelsContextValue = {
  listCollapsed: boolean;
  toggleListCollapsed: () => void;
  contactCollapsed: boolean;
  toggleContactCollapsed: () => void;
  detailsCollapsed: boolean;
  toggleDetailsCollapsed: () => void;
  stretchPx: number;
  maxStretchPx: number;
  setStretchPx: (next: number) => void;
  resetStretchPx: () => void;
};

const InboxPanelsContext = createContext<InboxPanelsContextValue | null>(null);

export function useInboxPanels(): InboxPanelsContextValue {
  const ctx = useContext(InboxPanelsContext);
  const [fallbackList, setFallbackList] = useState<boolean>(() =>
    readStoredPanelCollapsed(INBOX_LIST_COLLAPSED_KEY),
  );
  const [fallbackContact, setFallbackContact] = useState<boolean>(() =>
    readStoredPanelCollapsed(INBOX_CONTACT_COLLAPSED_KEY),
  );
  const [fallbackDetails, setFallbackDetails] = useState<boolean>(() =>
    readStoredPanelCollapsed(INBOX_DETAILS_COLLAPSED_KEY),
  );
  const [fallbackStretch, setFallbackStretch] = useState<number>(() =>
    clampInboxStretch(readStoredPanelStretch(INBOX_HEIGHT_OFFSET_KEY)),
  );

  const toggleFallbackList = useCallback(() => {
    setFallbackList((prev) => {
      const next = !prev;
      writeStoredPanelCollapsed(INBOX_LIST_COLLAPSED_KEY, next);
      return next;
    });
  }, []);

  const toggleFallbackContact = useCallback(() => {
    setFallbackContact((prev) => {
      const next = !prev;
      writeStoredPanelCollapsed(INBOX_CONTACT_COLLAPSED_KEY, next);
      return next;
    });
  }, []);

  const toggleFallbackDetails = useCallback(() => {
    setFallbackDetails((prev) => {
      const next = !prev;
      writeStoredPanelCollapsed(INBOX_DETAILS_COLLAPSED_KEY, next);
      return next;
    });
  }, []);

  const setFallbackStretchClamped = useCallback((next: number) => {
    const clamped = clampInboxStretch(next, DEFAULT_INBOX_MAX_STRETCH_PX);
    setFallbackStretch(clamped);
    writeStoredPanelStretch(INBOX_HEIGHT_OFFSET_KEY, clamped);
  }, []);

  const resetFallbackStretch = useCallback(() => {
    setFallbackStretch(0);
    writeStoredPanelStretch(INBOX_HEIGHT_OFFSET_KEY, 0);
  }, []);

  if (ctx) return ctx;
  return {
    listCollapsed: fallbackList,
    toggleListCollapsed: toggleFallbackList,
    contactCollapsed: fallbackContact,
    toggleContactCollapsed: toggleFallbackContact,
    detailsCollapsed: fallbackDetails,
    toggleDetailsCollapsed: toggleFallbackDetails,
    stretchPx: fallbackStretch,
    maxStretchPx: DEFAULT_INBOX_MAX_STRETCH_PX,
    setStretchPx: setFallbackStretchClamped,
    resetStretchPx: resetFallbackStretch,
  };
}

/**
 * Shared three-column frame for `/conversations` and `/conversations/[id]`.
 *
 * Keeping `list` mounted in the route-group layout means clicking from one
 * conversation to another updates only `children` (center + contact panel)
 * without unmounting or refetching the conversation list. Below `lg`, one
 * column is visible at a time with the conversation header's "Volver" link.
 */
export function InboxShell({
  list,
  children,
}: {
  list: ReactNode;
  children: ReactNode;
}) {
  const pathname = usePathname() ?? "";
  const hasConversation =
    /^\/accounts\/[^/]+\/conversations\/\d+(?:\/|$)/.test(pathname);

  const anchorRef = useRef<HTMLDivElement>(null);
  const dragStateRef = useRef<{
    pointerId: number;
    startY: number;
    startStretch: number;
    maxStretch: number;
  } | null>(null);

  const [listCollapsed, setListCollapsed] = useState<boolean>(() =>
    readStoredPanelCollapsed(INBOX_LIST_COLLAPSED_KEY),
  );
  const [contactCollapsed, setContactCollapsed] = useState<boolean>(() =>
    readStoredPanelCollapsed(INBOX_CONTACT_COLLAPSED_KEY),
  );
  const [detailsCollapsed, setDetailsCollapsed] = useState<boolean>(() =>
    readStoredPanelCollapsed(INBOX_DETAILS_COLLAPSED_KEY),
  );
  const [maxStretchPx, setMaxStretchPx] = useState<number>(
    DEFAULT_INBOX_MAX_STRETCH_PX,
  );
  const [stretchPx, setStretchPxState] = useState<number>(() =>
    clampInboxStretch(
      readStoredPanelStretch(INBOX_HEIGHT_OFFSET_KEY),
      DEFAULT_INBOX_MAX_STRETCH_PX,
    ),
  );
  const [isDragging, setIsDragging] = useState(false);

  useIsomorphicLayoutEffect(() => {
    setListCollapsed(readStoredPanelCollapsed(INBOX_LIST_COLLAPSED_KEY));
    setContactCollapsed(readStoredPanelCollapsed(INBOX_CONTACT_COLLAPSED_KEY));
    setDetailsCollapsed(readStoredPanelCollapsed(INBOX_DETAILS_COLLAPSED_KEY));
    const measuredMax = measureMaxInboxStretch(anchorRef.current);
    setMaxStretchPx(measuredMax);
    const stored = readStoredPanelStretch(INBOX_HEIGHT_OFFSET_KEY);
    const clamped = clampInboxStretch(stored, measuredMax);
    setStretchPxState(clamped);
    if (clamped !== stored) {
      writeStoredPanelStretch(INBOX_HEIGHT_OFFSET_KEY, clamped);
    }
  }, []);

  useEffect(() => {
    function handleResize() {
      const nextMax = measureMaxInboxStretch(anchorRef.current);
      setMaxStretchPx(nextMax);
      setStretchPxState((prev) => {
        const clamped = clampInboxStretch(prev, nextMax);
        if (clamped !== prev) {
          writeStoredPanelStretch(INBOX_HEIGHT_OFFSET_KEY, clamped);
        }
        return clamped;
      });
    }
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  useEffect(() => {
    if (!isDragging || typeof document === "undefined") return;
    const prevUserSelect = document.body.style.userSelect;
    const prevCursor = document.body.style.cursor;
    document.body.style.userSelect = "none";
    document.body.style.cursor = "row-resize";
    return () => {
      document.body.style.userSelect = prevUserSelect;
      document.body.style.cursor = prevCursor;
    };
  }, [isDragging]);

  const toggleListCollapsed = useCallback(() => {
    setListCollapsed((prev) => {
      const next = !prev;
      writeStoredPanelCollapsed(INBOX_LIST_COLLAPSED_KEY, next);
      return next;
    });
  }, []);

  const toggleContactCollapsed = useCallback(() => {
    setContactCollapsed((prev) => {
      const next = !prev;
      writeStoredPanelCollapsed(INBOX_CONTACT_COLLAPSED_KEY, next);
      return next;
    });
  }, []);

  const toggleDetailsCollapsed = useCallback(() => {
    setDetailsCollapsed((prev) => {
      const next = !prev;
      writeStoredPanelCollapsed(INBOX_DETAILS_COLLAPSED_KEY, next);
      return next;
    });
  }, []);

  const setStretchPx = useCallback((next: number) => {
    const currentMax = measureMaxInboxStretch(anchorRef.current);
    setMaxStretchPx(currentMax);
    const clamped = clampInboxStretch(next, currentMax);
    setStretchPxState(clamped);
    writeStoredPanelStretch(INBOX_HEIGHT_OFFSET_KEY, clamped);
  }, []);

  const resetStretchPx = useCallback(() => {
    const currentMax = measureMaxInboxStretch(anchorRef.current);
    setMaxStretchPx(currentMax);
    setStretchPxState(0);
    writeStoredPanelStretch(INBOX_HEIGHT_OFFSET_KEY, 0);
  }, []);

  const handlePointerDown = useCallback(
    (event: ReactPointerEvent<HTMLDivElement>) => {
      if (event.pointerType === "mouse" && event.button !== 0) return;
      const pointerId = event.pointerId ?? 0;
      const currentMax = measureMaxInboxStretch(anchorRef.current);
      setMaxStretchPx(currentMax);
      dragStateRef.current = {
        pointerId,
        startY: event.clientY,
        startStretch: clampInboxStretch(stretchPx, currentMax),
        maxStretch: currentMax,
      };
      setIsDragging(true);
      try {
        event.currentTarget.setPointerCapture?.(pointerId);
      } catch {
        // Ignore in synthetic test environments where pointer capture is unavailable.
      }
    },
    [stretchPx],
  );

  const handlePointerMove = useCallback(
    (event: ReactPointerEvent<HTMLDivElement>) => {
      const drag = dragStateRef.current;
      const pointerId = event.pointerId ?? 0;
      if (!drag || drag.pointerId !== pointerId) return;
      const deltaUp = drag.startY - event.clientY;
      const next = clampInboxStretch(
        drag.startStretch + deltaUp,
        drag.maxStretch,
      );
      setStretchPxState(next);
      writeStoredPanelStretch(INBOX_HEIGHT_OFFSET_KEY, next);
    },
    [],
  );

  const finishDrag = useCallback(
    (event: ReactPointerEvent<HTMLDivElement>) => {
      const drag = dragStateRef.current;
      const pointerId = event.pointerId ?? 0;
      if (!drag || drag.pointerId !== pointerId) return;
      dragStateRef.current = null;
      setIsDragging(false);
      try {
        if (event.currentTarget.hasPointerCapture?.(pointerId)) {
          event.currentTarget.releasePointerCapture(pointerId);
        }
      } catch {
        // Ignore in synthetic test environments.
      }
    },
    [],
  );

  const handleKeyDown = useCallback(
    (event: ReactKeyboardEvent<HTMLDivElement>) => {
      const currentMax = measureMaxInboxStretch(anchorRef.current);
      setMaxStretchPx(currentMax);
      if (event.key === "ArrowUp") {
        event.preventDefault();
        const next = clampInboxStretch(
          stretchPx + INBOX_STRETCH_STEP_PX,
          currentMax,
        );
        setStretchPxState(next);
        writeStoredPanelStretch(INBOX_HEIGHT_OFFSET_KEY, next);
      } else if (event.key === "ArrowDown") {
        event.preventDefault();
        const next = clampInboxStretch(
          stretchPx - INBOX_STRETCH_STEP_PX,
          currentMax,
        );
        setStretchPxState(next);
        writeStoredPanelStretch(INBOX_HEIGHT_OFFSET_KEY, next);
      } else if (event.key === "Home") {
        event.preventDefault();
        setStretchPxState(0);
        writeStoredPanelStretch(INBOX_HEIGHT_OFFSET_KEY, 0);
      } else if (event.key === "End") {
        event.preventDefault();
        setStretchPxState(currentMax);
        writeStoredPanelStretch(INBOX_HEIGHT_OFFSET_KEY, currentMax);
      }
    },
    [stretchPx],
  );

  const ctxValue = useMemo<InboxPanelsContextValue>(
    () => ({
      listCollapsed,
      toggleListCollapsed,
      contactCollapsed,
      toggleContactCollapsed,
      detailsCollapsed,
      toggleDetailsCollapsed,
      stretchPx,
      maxStretchPx,
      setStretchPx,
      resetStretchPx,
    }),
    [
      listCollapsed,
      toggleListCollapsed,
      contactCollapsed,
      toggleContactCollapsed,
      detailsCollapsed,
      toggleDetailsCollapsed,
      stretchPx,
      maxStretchPx,
      setStretchPx,
      resetStretchPx,
    ],
  );

  const shellStyle = useMemo<CSSProperties>(
    () =>
      ({
        "--inbox-stretch": `${stretchPx}px`,
      }) as CSSProperties,
    [stretchPx],
  );

  return (
    <InboxPanelsContext.Provider value={ctxValue}>
      <div ref={anchorRef} className="flex flex-col">
        <div
          data-testid="inbox-shell"
          data-stretch={String(stretchPx)}
          style={shellStyle}
          onScroll={(e) => {
            if (e.currentTarget === e.target && e.currentTarget.scrollTop !== 0) {
              e.currentTarget.scrollTop = 0;
            }
          }}
          className={cn(
            "relative z-20 flex min-h-[calc(100dvh-13.5rem)] overflow-hidden rounded-md border border-glass bg-surface lg:mt-[calc(var(--inbox-stretch,0px)*-1)] lg:h-[max(26rem,calc(100dvh-13.5rem+var(--inbox-stretch,0px)))] lg:min-h-[max(26rem,calc(100dvh-13.5rem+var(--inbox-stretch,0px)))]",
            isDragging && "select-none",
          )}
        >
          <div
            role="separator"
            tabIndex={0}
            aria-orientation="horizontal"
            aria-label="Cambiar el alto de la bandeja"
            aria-valuemin={0}
            aria-valuemax={maxStretchPx}
            aria-valuenow={stretchPx}
            data-testid="inbox-resize-handle"
            data-dragging={isDragging ? "true" : "false"}
            onPointerDown={handlePointerDown}
            onPointerMove={handlePointerMove}
            onPointerUp={finishDrag}
            onPointerCancel={finishDrag}
            onLostPointerCapture={finishDrag}
            onDoubleClick={resetStretchPx}
            onKeyDown={handleKeyDown}
            className="group absolute inset-x-0 top-0 z-30 hidden h-2 cursor-row-resize select-none items-center justify-center touch-none focus-visible:outline-none lg:flex"
          >
            <span
              aria-hidden
              className={cn(
                "pointer-events-none absolute inset-x-0 top-0 h-0.5 transition-opacity duration-150 motion-reduce:transition-none",
                isDragging
                  ? "bg-neon opacity-100"
                  : "bg-border-strong opacity-0 group-hover:opacity-100 group-focus-visible:bg-neon group-focus-visible:opacity-100",
              )}
            />
            <span
              aria-hidden
              className={cn(
                "pointer-events-none h-1 w-10 rounded-pill transition-colors duration-150 motion-reduce:transition-none",
                isDragging
                  ? "bg-neon"
                  : "bg-transparent group-hover:bg-border-strong group-focus-visible:bg-neon",
              )}
            />
          </div>
          <div
            data-testid="inbox-list-panel"
            data-collapsed={listCollapsed ? "true" : "false"}
            className={cn(
              "flex min-h-0 w-full flex-col overflow-hidden lg:shrink-0 lg:border-r lg:border-glass lg:transition-[width] lg:duration-200 lg:ease-out motion-reduce:transition-none",
              listCollapsed ? "lg:w-11" : "lg:w-[320px]",
              hasConversation && "hidden lg:flex",
            )}
          >
            {listCollapsed ? (
              <div className="hidden lg:flex lg:flex-col lg:items-center lg:py-2">
                <button
                  type="button"
                  onClick={toggleListCollapsed}
                  aria-expanded={false}
                  aria-label="Expandir lista de conversaciones"
                  title="Expandir lista de conversaciones"
                  className="inline-flex h-8 w-8 items-center justify-center rounded-control text-fg-muted transition-colors hover:bg-hover-glass hover:text-fg focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-neon"
                >
                  <PanelLeftOpen className="h-5 w-5" aria-hidden />
                </button>
              </div>
            ) : null}
            <div
              className={cn(
                "flex min-h-0 flex-1 flex-col overflow-hidden",
                listCollapsed && "lg:hidden",
              )}
            >
              {list}
            </div>
          </div>
          <div
            className={cn(
              "flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden",
              !hasConversation && "hidden lg:flex",
            )}
          >
            {children}
          </div>
        </div>
      </div>
    </InboxPanelsContext.Provider>
  );
}

export { PanelLeftClose };
