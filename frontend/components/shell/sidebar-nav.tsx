"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { useT } from "@/lib/i18n/provider";
import { cn } from "@/lib/utils";

import { activeNavItemKey, NAV_GROUPS, NAV_ITEMS, navHref } from "./nav";

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
  collapsed = false,
  hiddenKeys = [],
}: {
  accountId: string;
  onNavigate?: () => void;
  collapsed?: boolean;
  /** Items this account has nothing for (WhatsApp without a WhatsApp inbox). */
  hiddenKeys?: string[];
}) {
  const pathname = usePathname() ?? "";
  const activeKey = activeNavItemKey(pathname, accountId);
  const t = useT();

  return (
    <nav
      className="flex flex-1 flex-col gap-3 overflow-y-auto overflow-x-hidden px-[10px] pb-3"
      aria-label={t("nav.main")}
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
            {group.label && !collapsed ? (
              <p className="px-[14px] pb-0.5 pt-2 text-[11px] font-medium uppercase tracking-[0.08em] text-fg-muted">
                {group.label}
              </p>
            ) : null}
            {group.keys.map((key) => {
              const item = BY_KEY.get(key);
              if (!item || hiddenKeys.includes(key)) return null;
              const href = navHref(accountId, item.segment);
              const active = activeKey === item.key;
              const Icon = item.icon;
              const label = t(item.label);
              return (
                <Link
                  key={item.key}
                  href={href}
                  onClick={onNavigate}
                  aria-current={active ? "page" : undefined}
                  aria-label={collapsed ? label : undefined}
                  title={collapsed ? label : undefined}
                  className={cn(
                    "group relative flex h-11 items-center whitespace-nowrap rounded-control font-display text-[16px] font-normal leading-none",
                    collapsed ? "justify-center px-0" : "gap-3 px-[14px]",
                    "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-neon",
                    active
                      ? "lit-tube lit-tube-ignite neon-nav-lit bg-focused dark:bg-transparent"
                      : "neon-nav hover:bg-hover-glass",
                  )}
                >
                  <Icon className="h-5 w-5 shrink-0" aria-hidden />
                  {collapsed ? null : label}
                </Link>
              );
            })}
          </div>
        );
      })}
    </nav>
  );
}
