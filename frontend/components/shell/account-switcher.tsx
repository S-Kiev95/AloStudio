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
          "relative flex h-10 cursor-pointer list-none items-center gap-2 rounded-control border border-glass bg-field px-3 text-sm font-medium text-fg transition-colors",
          "after:absolute after:-inset-y-0.5 after:inset-x-0 after:content-['']",
          "hover:bg-hover-glass focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-neon",
        )}
      >
        <span className="max-w-[9rem] truncate sm:max-w-[12rem]">
          {active?.name ?? "Cuenta"}
        </span>
        <ChevronsUpDown className="h-4 w-4 text-fg-muted" aria-hidden />
      </summary>
      <div
        className="absolute right-0 z-30 mt-1.5 w-64 overflow-hidden rounded-md border border-glass bg-surface-2 shadow-menu"
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
                "flex items-center justify-between gap-2 px-3 py-2 text-sm transition-colors",
                isActive
                  ? "bg-focused text-lit font-medium"
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
