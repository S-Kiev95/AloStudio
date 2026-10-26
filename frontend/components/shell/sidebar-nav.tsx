"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { cn } from "@/lib/utils";

import { NAV_GROUPS, NAV_ITEMS, navHref } from "./nav";

const BY_KEY = new Map(NAV_ITEMS.map((item) => [item.key, item]));

/**
 * Main sidebar navigation (DESIGN.md Humming Sidebar Exception).
 * Tilt Neon 16px, 44px height, 10px radius. Unlit rows hum in night mode,
 * hover lights up the lettering, and the active row outlines in a lit cobalt
 * tube with ignition on arrival. Daylight drops all glows automatically.
 */
export function SidebarNav({
  accountId,
  onNavigate,
}: {
  accountId: string;
  onNavigate?: () => void;
}) {
  const pathname = usePathname();

  return (
    <nav
      className="flex flex-1 flex-col gap-3 overflow-y-auto px-[10px] pb-3"
      aria-label="Principal"
    >
      {NAV_GROUPS.map((group, i) => {
        const isLast = i === NAV_GROUPS.length - 1;
        return (
          <div
            key={group.label ?? `g${i}`}
            className={cn(
              "flex flex-col gap-1.5",
              isLast && "mt-auto pt-2",
            )}
          >
            {group.label ? (
              <p className="px-[14px] pb-0.5 pt-2 text-[11px] font-medium uppercase tracking-[0.08em] text-fg-muted">
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
                    "group relative flex h-11 items-center gap-3 rounded-control px-[14px] font-display text-[16px] font-normal leading-none",
                    "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-neon",
                    active
                      ? "lit-tube lit-tube-ignite neon-nav-lit bg-focused/60 dark:bg-transparent"
                      : "neon-nav hover:bg-hover-glass",
                  )}
                >
                  <Icon className="h-5 w-5 shrink-0" aria-hidden />
                  {item.label}
                </Link>
              );
            })}
          </div>
        );
      })}
    </nav>
  );
}
