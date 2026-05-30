"use client";

import { Check, ChevronsUpDown } from "lucide-react";
import Link from "next/link";

import type { ProfileAccount } from "@/lib/auth/profile";
import { cn } from "@/lib/utils";

/**
 * Account switcher. Native <details> disclosure for a zero-dep,
 * keyboard-accessible dropdown; selecting an account navigates away.
 */
export function AccountSwitcher({
  accountId,
  accounts,
}: {
  accountId: string;
  accounts: ProfileAccount[];
}) {
  const active = accounts.find((a) => String(a.id) === accountId);

  return (
    <details className="group relative">
      <summary
        className={cn(
          "flex cursor-pointer list-none items-center gap-2 rounded-md border border-border bg-surface px-3 py-1.5 text-sm font-medium text-fg",
          "hover:bg-surface-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        )}
      >
        <span className="max-w-[12rem] truncate">
          {active?.name ?? "Cuenta"}
        </span>
        <ChevronsUpDown className="h-4 w-4 text-fg-muted" aria-hidden />
      </summary>
      <div
        className="absolute left-0 z-20 mt-1 w-64 overflow-hidden rounded-md border border-border bg-surface shadow-md"
        role="menu"
      >
        {accounts.map((a) => {
          const isActive = String(a.id) === accountId;
          return (
            <Link
              key={a.id}
              href={`/accounts/${a.id}`}
              role="menuitem"
              className={cn(
                "flex items-center justify-between gap-2 px-3 py-2 text-sm text-fg hover:bg-surface-2",
              )}
            >
              <span className="truncate">{a.name}</span>
              {isActive ? (
                <Check className="h-4 w-4 text-primary" aria-hidden />
              ) : null}
            </Link>
          );
        })}
      </div>
    </details>
  );
}
