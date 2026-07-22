"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { cn } from "@/lib/utils";

import { NAV_GROUPS, NAV_ITEMS, navHref } from "./nav";

const BY_KEY = new Map(NAV_ITEMS.map((item) => [item.key, item]));

/** The nav link list, shared by the desktop sidebar + the mobile drawer.
 *  Grouped into labelled sections (see NAV_GROUPS); the active row lifts onto
 *  an elevated surface with a yellow rail and a tinted icon. */
export function SidebarNav({
  accountId,
  onNavigate,
}: {
  accountId: string;
  onNavigate?: () => void;
}) {
  const pathname = usePathname();

  return (
    <nav className="flex flex-col gap-4 p-3" aria-label="Principal">
      {NAV_GROUPS.map((group, i) => (
        <div key={group.label ?? `g${i}`} className="flex flex-col gap-1">
          {group.label ? (
            <p className="px-3 pb-1 pt-2 text-[0.6875rem] font-semibold uppercase tracking-wider text-fg-muted/70">
              {group.label}
            </p>
          ) : null}
          {group.keys.map((key) => {
            const item = BY_KEY.get(key);
            if (!item) return null;
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
                  "group relative flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors",
                  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-bg",
                  active
                    ? "bg-surface-2 font-semibold text-fg shadow-[inset_0_1px_0_rgb(255_255_255/0.04)] before:absolute before:left-0 before:top-1/2 before:h-5 before:w-[3px] before:-translate-y-1/2 before:rounded-r-full before:bg-primary before:shadow-[0_0_8px_rgb(252_213_53/0.5)]"
                    : "font-medium text-fg-muted hover:bg-surface-2/60 hover:text-fg",
                )}
              >
                <Icon
                  className={cn(
                    "h-5 w-5 shrink-0 transition-colors",
                    active
                      ? "text-primary"
                      : "text-fg-muted group-hover:text-fg",
                  )}
                  aria-hidden
                />
                {item.label}
              </Link>
            );
          })}
        </div>
      ))}
    </nav>
  );
}
