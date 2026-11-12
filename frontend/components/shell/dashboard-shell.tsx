"use client";

import { Menu, X } from "lucide-react";
import { usePathname } from "next/navigation";
import {
  useEffect,
  useLayoutEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { NeonWordmark } from "@/components/brand/neon-wordmark";
import type { Profile } from "@/lib/auth/profile";
import { isLocale } from "@/lib/i18n/config";
import { useLocale, useSwitchLocale, useT } from "@/lib/i18n/provider";
import type { MessageKey } from "@/lib/i18n/translate";
import { useCable } from "@/lib/realtime/use-cable";
import { cn } from "@/lib/utils";

import { AccountSwitcher } from "./account-switcher";
import { AgentMenu } from "./agent-menu";
import { SidebarCollapseIcon, SidebarExpandIcon } from "./app-icons";
import { activeNavItemKey, NAV_ITEMS, navHref } from "./nav";
import { NotificationBell } from "./notification-bell";
import { PageSignContext } from "./page-header";
import { SidebarNav } from "./sidebar-nav";
import { ThemeToggle } from "./theme-toggle";

export const SIDEBAR_COLLAPSED_STORAGE_KEY = "alostudio:sidebar-collapsed";

const useIsomorphicLayoutEffect =
  typeof window !== "undefined" ? useLayoutEffect : useEffect;

function readSidebarCollapsed(): boolean {
  if (typeof window === "undefined") return false;
  try {
    const raw = window.localStorage.getItem(SIDEBAR_COLLAPSED_STORAGE_KEY);
    return raw === "1" || raw === "true";
  } catch {
    return false;
  }
}

function writeSidebarCollapsed(collapsed: boolean): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(
      SIDEBAR_COLLAPSED_STORAGE_KEY,
      collapsed ? "1" : "0",
    );
  } catch {
    // Ignore storage failures (private mode / quota).
  }
}

function Brand({
  href,
  onClick,
  collapsed = false,
}: {
  href: string;
  onClick?: () => void;
  collapsed?: boolean;
}) {
  return (
    <NeonWordmark
      href={href}
      onClick={onClick}
      collapsed={collapsed}
      className="rounded-sm text-[36px]"
    />
  );
}

function resolveDefaultSign(pathname: string, accountId: string): MessageKey {
  const base = `/accounts/${accountId}`;
  if (
    pathname === `${base}/notifications` ||
    pathname.startsWith(`${base}/notifications/`)
  ) {
    return "nav.notifications";
  }
  const activeKey = activeNavItemKey(pathname, accountId);
  if (activeKey) {
    const matched = NAV_ITEMS.find((item) => item.key === activeKey);
    if (matched) return matched.label;
  }
  return "nav.home";
}

export function DashboardShell({
  accountId,
  profile,
  children,
}: {
  accountId: string;
  profile: Profile;
  children: ReactNode;
}) {
  const pathname = usePathname() ?? "";
  const [mobileOpen, setMobileOpen] = useState(false);
  const [customSign, setCustomSign] = useState<string | null>(null);
  const [sidebarCollapsed, setSidebarCollapsed] = useState<boolean>(() =>
    readSidebarCollapsed(),
  );
  const [animateSidebar, setAnimateSidebar] = useState(false);

  useIsomorphicLayoutEffect(() => {
    setSidebarCollapsed(readSidebarCollapsed());
  }, []);

  const handleToggleSidebar = () => {
    setAnimateSidebar(true);
    setSidebarCollapsed((prev) => {
      const next = !prev;
      writeSidebarCollapsed(next);
      return next;
    });
  };

  // The language saved in the profile wins over this browser's cookie, so
  // a choice made on another device applies here after signing in.
  const locale = useLocale();
  const switchLocale = useSwitchLocale();
  useEffect(() => {
    if (isLocale(profile.locale) && profile.locale !== locale) {
      switchLocale(profile.locale);
    }
  }, [profile.locale, locale, switchLocale]);

  useCable({
    pubsubToken: profile.pubsubToken,
    userId: profile.id,
    accountId,
  });

  const signCtx = useMemo(() => ({ setSignTitle: setCustomSign }), []);
  const t = useT();
  const signTitle = customSign ?? t(resolveDefaultSign(pathname, accountId));
  const homeHref = navHref(accountId, "");
  const toggleLabel = sidebarCollapsed
    ? t("shell.expandSidebar")
    : t("shell.collapseSidebar");

  return (
    <PageSignContext.Provider value={signCtx}>
      <div className="flex min-h-dvh gap-3 p-2 text-fg lg:p-3">
        {/* Desktop glass sidebar (236px expanded, 68px collapsed) */}
        <aside
          data-collapsed={sidebarCollapsed ? "true" : "false"}
          className={cn(
            "vt-sidebar glass-panel hidden overflow-hidden rounded-panel bg-surface lg:sticky lg:top-3 lg:flex lg:h-[calc(100dvh-24px)] lg:shrink-0 lg:flex-col",
            sidebarCollapsed ? "lg:w-[68px]" : "lg:w-[236px]",
            animateSidebar &&
              "lg:transition-[width] lg:duration-200 lg:ease-out motion-reduce:transition-none",
          )}
        >
          <div
            className={cn(
              "flex items-center pb-[28px] pt-[18px]",
              sidebarCollapsed ? "justify-center px-2" : "px-[14px]",
            )}
          >
            <Brand href={homeHref} collapsed={sidebarCollapsed} />
          </div>
          <SidebarNav accountId={accountId} collapsed={sidebarCollapsed} />
          <div className="border-t border-glass px-[10px] pb-3 pt-2">
            <button
              type="button"
              onClick={handleToggleSidebar}
              aria-expanded={!sidebarCollapsed}
              aria-label={toggleLabel}
              title={toggleLabel}
              className={cn(
                "neon-nav flex h-11 w-full items-center rounded-control hover:bg-hover-glass",
                "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-neon",
                sidebarCollapsed ? "justify-center px-0" : "px-[14px]",
              )}
            >
              {sidebarCollapsed ? (
                <SidebarExpandIcon className="h-5 w-5 shrink-0" aria-hidden />
              ) : (
                <SidebarCollapseIcon className="h-5 w-5 shrink-0" aria-hidden />
              )}
            </button>
          </div>
        </aside>

        {/* Mobile full-height drawer */}
        {mobileOpen ? (
          <div className="fixed inset-0 z-40 lg:hidden">
            <button
              type="button"
              aria-label={t("shell.closeMenu")}
              className="absolute inset-0 bg-backdrop/80"
              onClick={() => setMobileOpen(false)}
            />
            <aside className="glass-panel absolute inset-y-0 left-0 flex w-[236px] flex-col bg-surface">
              <div className="flex items-center justify-between px-[14px] pb-5 pt-[18px]">
                <Brand
                  href={homeHref}
                  onClick={() => setMobileOpen(false)}
                />
                <button
                  type="button"
                  aria-label={t("shell.closeMenu")}
                  onClick={() => setMobileOpen(false)}
                  className="inline-flex h-11 w-11 items-center justify-center rounded-control text-fg-muted hover:bg-hover-glass hover:text-fg"
                >
                  <X className="h-5 w-5" aria-hidden />
                </button>
              </div>
              <SidebarNav
                accountId={accountId}
                onNavigate={() => setMobileOpen(false)}
              />
            </aside>
          </div>
        ) : null}

        {/* Work glass panel */}
        <div className="glass-panel flex min-w-0 flex-1 flex-col rounded-panel bg-surface">
          {/* view-transition-name makes the bar its own stacking layer, so its
              menus (account, notifications, user) can only rise as high as the
              bar itself: z-[35] keeps them above the page's own layers (up to
              z-30) and below the mobile drawer (z-40) and dialogs (z-50). */}
          <header className="vt-topbar relative z-[35] flex h-16 shrink-0 items-center gap-3 border-b border-glass px-4 lg:h-20 lg:px-6">
            <button
              type="button"
              aria-label={t("shell.openMenu")}
              onClick={() => setMobileOpen(true)}
              className="inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-control text-fg-muted hover:bg-hover-glass hover:text-fg lg:hidden"
            >
              <Menu className="h-5 w-5" aria-hidden />
            </button>

            <div className="neon-sign min-w-0 flex-1">
              {/* Below lg the controls leave little room: truncate instead of
                  running under them. On desktop the glow may overflow. */}
              <h1 className="text-[24px] leading-[1.2] max-lg:truncate lg:text-[34px]">
                {signTitle}
              </h1>
            </div>

            <div className="ml-auto flex shrink-0 items-center gap-1.5 sm:gap-2">
              <ThemeToggle />
              <NotificationBell accountId={accountId} />
              <span className="mx-0.5 hidden h-5 w-px bg-glass sm:block" aria-hidden />
              <AccountSwitcher
                accountId={accountId}
                accounts={profile.accounts}
              />
              <AgentMenu name={profile.name} email={profile.email} />
            </div>
          </header>

          <main id="main-content" className="flex-1 p-4 sm:p-5 lg:p-6">
            {children}
          </main>
        </div>
      </div>
    </PageSignContext.Provider>
  );
}
