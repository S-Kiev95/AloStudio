"use client";

import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

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

  return (
    <div className="flex min-h-[calc(100dvh-13.5rem)] overflow-hidden rounded-md border border-glass bg-surface lg:h-[calc(100dvh-13.5rem)]">
      <div
        className={cn(
          "flex min-h-0 w-full flex-col lg:w-[320px] lg:shrink-0 lg:border-r lg:border-glass",
          hasConversation && "hidden lg:flex",
        )}
      >
        {list}
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
  );
}
