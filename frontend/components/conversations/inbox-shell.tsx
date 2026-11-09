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
  useState,
  type ReactNode,
} from "react";

import { cn } from "@/lib/utils";

export const INBOX_LIST_COLLAPSED_KEY = "alostudio:inbox-list-collapsed";
export const INBOX_CONTACT_COLLAPSED_KEY = "alostudio:inbox-contact-collapsed";

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

type InboxPanelsContextValue = {
  listCollapsed: boolean;
  toggleListCollapsed: () => void;
  contactCollapsed: boolean;
  toggleContactCollapsed: () => void;
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

  if (ctx) return ctx;
  return {
    listCollapsed: fallbackList,
    toggleListCollapsed: toggleFallbackList,
    contactCollapsed: fallbackContact,
    toggleContactCollapsed: toggleFallbackContact,
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

  const [listCollapsed, setListCollapsed] = useState<boolean>(() =>
    readStoredPanelCollapsed(INBOX_LIST_COLLAPSED_KEY),
  );
  const [contactCollapsed, setContactCollapsed] = useState<boolean>(() =>
    readStoredPanelCollapsed(INBOX_CONTACT_COLLAPSED_KEY),
  );

  useIsomorphicLayoutEffect(() => {
    setListCollapsed(readStoredPanelCollapsed(INBOX_LIST_COLLAPSED_KEY));
    setContactCollapsed(readStoredPanelCollapsed(INBOX_CONTACT_COLLAPSED_KEY));
  }, []);

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

  const ctxValue = useMemo<InboxPanelsContextValue>(
    () => ({
      listCollapsed,
      toggleListCollapsed,
      contactCollapsed,
      toggleContactCollapsed,
    }),
    [
      listCollapsed,
      toggleListCollapsed,
      contactCollapsed,
      toggleContactCollapsed,
    ],
  );

  return (
    <InboxPanelsContext.Provider value={ctxValue}>
      <div className="flex min-h-[calc(100dvh-13.5rem)] overflow-hidden rounded-md border border-glass bg-surface lg:h-[calc(100dvh-13.5rem)]">
        <div
          data-testid="inbox-list-panel"
          data-collapsed={listCollapsed ? "true" : "false"}
          className={cn(
            "flex min-h-0 w-full flex-col lg:shrink-0 lg:border-r lg:border-glass lg:transition-[width] lg:duration-200 lg:ease-out motion-reduce:transition-none",
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
                <PanelLeftOpen className="h-4 w-4" aria-hidden />
              </button>
            </div>
          ) : null}
          <div
            className={cn(
              "flex min-h-0 flex-1 flex-col",
              listCollapsed && "lg:hidden",
            )}
          >
            {list}
          </div>
        </div>
        <div
          className={cn(
            "flex min-h-0 min-w-0 flex-1 flex-col",
            !hasConversation && "hidden lg:flex",
          )}
        >
          {children}
        </div>
      </div>
    </InboxPanelsContext.Provider>
  );
}

export { PanelLeftClose };
