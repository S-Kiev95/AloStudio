"use client";

import { Check, ChevronsUpDown } from "lucide-react";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import type { ProfileAccount } from "@/lib/auth/profile";
import { useDismissOnOutsideAndEscape } from "@/lib/hooks/use-dismiss";
import { useT } from "@/lib/i18n/provider";
import { animatePopoverIn } from "@/lib/motion/neon-motion";
import { cn } from "@/lib/utils";

/**
 * Account switcher. Native <details> disclosure for a zero-dep,
 * keyboard-accessible dropdown; closes on outside click or Escape.
 */
export function AccountSwitcher({
  accountId,
  accounts,
  placement = "down",
  fullWidth = false,
  onSelect,
}: {
  accountId: string;
  accounts: ProfileAccount[];
  placement?: "down" | "up";
  fullWidth?: boolean;
  onSelect?: () => void;
}) {
  const active = accounts.find((a) => String(a.id) === accountId);
  const t = useT();
  const detailsRef = useRef<HTMLDetailsElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!open) return;
    return animatePopoverIn(menuRef.current, placement);
  }, [open, placement]);

  useDismissOnOutsideAndEscape(detailsRef, open, () => {
    detailsRef.current?.removeAttribute("open");
    setOpen(false);
  });

  return (
    <details
      ref={detailsRef}
      className={cn("group relative", fullWidth && "w-full")}
      onToggle={(e) => setOpen((e.currentTarget as HTMLDetailsElement).open)}
    >
      <summary
        className={cn(
          "relative flex h-10 cursor-pointer list-none items-center justify-between gap-2 rounded-control border border-glass bg-field px-3 text-sm font-medium text-fg transition-colors",
          "after:absolute after:-inset-y-0.5 after:inset-x-0 after:content-['']",
          "hover:bg-hover-glass focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-neon",
          fullWidth && "w-full",
        )}
      >
        <span
          className={cn(
            "truncate",
            fullWidth ? "min-w-0 flex-1" : "max-w-[9rem] sm:max-w-[12rem]",
          )}
        >
          {active?.name ?? t("shell.account")}
        </span>
        <ChevronsUpDown className="h-4 w-4 shrink-0 text-fg-muted" aria-hidden />
      </summary>
      <div
        ref={menuRef}
        className={cn(
          "glass-dialog absolute z-30 overflow-hidden rounded-md",
          fullWidth ? "inset-x-0" : "right-0 w-64",
          placement === "up" ? "bottom-full mb-1.5" : "mt-1.5",
        )}
        role="menu"
      >
        {accounts.map((a) => {
          const isActive = String(a.id) === accountId;
          return (
            <Link
              key={a.id}
              href={`/accounts/${a.id}`}
              role="menuitem"
              onClick={() => {
                detailsRef.current?.removeAttribute("open");
                setOpen(false);
                onSelect?.();
              }}
              className={cn(
                "flex items-center justify-between gap-2 px-3 py-2 text-sm transition-colors",
                isActive
                  ? "bg-focused font-medium text-lit"
                  : "text-fg hover:bg-hover-glass",
              )}
            >
              <span className="truncate">{a.name}</span>
              {isActive ? (
                <Check className="h-4 w-4 text-neon" aria-hidden />
              ) : null}
            </Link>
          );
        })}
      </div>
    </details>
  );
}
