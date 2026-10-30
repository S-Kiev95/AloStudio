"use client";

import { usePathname } from "next/navigation";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { cn } from "@/lib/utils";

type AgentShellContextValue = {
  mobileListOpen: boolean;
  openMobileList: () => void;
  closeMobileList: () => void;
  newChatResetKey: number;
  triggerNewChatReset: () => void;
};

const AgentShellContext = createContext<AgentShellContextValue | null>(null);

export function useAgentShell() {
  return useContext(AgentShellContext);
}

/**
 * Two-column frame for `/agent` and `/agent/[threadId]`.
 *
 * Keeping `list` mounted in the layout prevents refetching or unmounting the
 * chat list when switching between conversations. Below `md`, the chat list is
 * hidden by default and opened from the "Chats" button in the conversation
 * header (mirroring `InboxShell`'s single-column mobile behavior).
 */
export function AgentShell({
  list,
  children,
}: {
  list: ReactNode;
  children: ReactNode;
}) {
  const pathname = usePathname() ?? "";
  const [mobileListOpen, setMobileListOpen] = useState(false);
  const [newChatResetKey, setNewChatResetKey] = useState(0);

  useEffect(() => {
    setMobileListOpen(false);
  }, [pathname]);

  const openMobileList = useCallback(() => setMobileListOpen(true), []);
  const closeMobileList = useCallback(() => setMobileListOpen(false), []);
  const triggerNewChatReset = useCallback(
    () => setNewChatResetKey((n) => n + 1),
    [],
  );

  const ctx = useMemo<AgentShellContextValue>(
    () => ({
      mobileListOpen,
      openMobileList,
      closeMobileList,
      newChatResetKey,
      triggerNewChatReset,
    }),
    [
      mobileListOpen,
      openMobileList,
      closeMobileList,
      newChatResetKey,
      triggerNewChatReset,
    ],
  );

  return (
    <AgentShellContext.Provider value={ctx}>
      <div className="flex min-h-[calc(100dvh-10rem)] overflow-hidden rounded-md border border-glass bg-surface md:h-[calc(100dvh-10rem)]">
        <div
          data-testid="agent-threads-column"
          className={cn(
            "min-h-0 w-full flex-col md:flex md:w-64 md:shrink-0 md:border-r md:border-glass",
            mobileListOpen ? "flex" : "hidden",
          )}
        >
          {list}
        </div>
        <div
          data-testid="agent-conversation-column"
          className={cn(
            "min-h-0 min-w-0 flex-1 flex-col md:flex",
            mobileListOpen ? "hidden" : "flex",
          )}
        >
          {children}
        </div>
      </div>
    </AgentShellContext.Provider>
  );
}
