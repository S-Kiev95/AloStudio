"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { cn } from "@/lib/utils";

import { NAV_ITEMS, navHref } from "./nav";

/** The nav link list, shared by the desktop sidebar + the mobile drawer. */
export function SidebarNav({
  accountId,
  onNavigate,
}: {
  accountId: string;
  onNavigate?: () => void;
}) {
  const pathname = usePathname();

  return (
    <nav className="flex flex-col gap-1 p-3" aria-label="Principal">
      {NAV_ITEMS.map((item) => {
        const href = navHref(accountId, item.segment);
        const active =
          item.segment === ""
            ? pathname === href
            : pathname === href || pathname.startsWith(`${href}/`);
        const Icon = item.icon;
        return (
          <Link
            key={item.key}
            href={href}
            onClick={onNavigate}
            aria-current={active ? "page" : undefined}
            className={cn(
              "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-bg",
              active
                ? "bg-primary text-primary-fg"
                : "text-fg-muted hover:bg-surface-2 hover:text-fg",
            )}
          >
            <Icon className="h-5 w-5 shrink-0" aria-hidden />
            {item.label}
          </Link>
        );
      })}
    </nav>
  );
}
