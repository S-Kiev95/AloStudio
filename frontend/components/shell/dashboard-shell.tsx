"use client";

import { Menu, X } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useMemo, useState, type ReactNode } from "react";

import type { Profile } from "@/lib/auth/profile";
import { useCable } from "@/lib/realtime/use-cable";

import { AccountSwitcher } from "./account-switcher";
import { AgentMenu } from "./agent-menu";
import { NAV_ITEMS, navHref } from "./nav";
import { NotificationBell } from "./notification-bell";
import { PageSignContext } from "./page-header";
import { SidebarNav } from "./sidebar-nav";
import { ThemeToggle } from "./theme-toggle";

function Brand({
  href,
  onClick,
}: {
  href: string;
  onClick?: () => void;
}) {
  return (
    <Link
      href={href}
      onClick={onClick}
      className="neon-wordmark inline-block select-none rounded-sm text-[36px] leading-none"
    >
      AloStudio
    </Link>
  );
}

function resolveDefaultSign(pathname: string, accountId: string): string {
  const base = `/accounts/${accountId}`;
  if (pathname === `${base}/notifications` || pathname.startsWith(`${base}/notifications/`)) {
    return "Notificaciones";
  }
  for (const item of NAV_ITEMS) {
    if (!item.segment) continue;
    const href = navHref(accountId, item.segment);
    if (pathname === href || pathname.startsWith(`${href}/`)) {
      return item.label;
    }
  }
  return "Inicio";
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
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [customSign, setCustomSign] = useState<string | null>(null);

  useCable({
    pubsubToken: profile.pubsubToken,
    userId: profile.id,
    accountId,
  });

  const signCtx = useMemo(() => ({ setSignTitle: setCustomSign }), []);
  const signTitle = customSign ?? resolveDefaultSign(pathname, accountId);
  const homeHref = navHref(accountId, "");

  return (
    <PageSignContext.Provider value={signCtx}>
      <div className="flex min-h-dvh gap-3 p-2 text-fg lg:p-3">
        {/* Desktop glass sidebar (236px) */}
        <aside className="glass-panel hidden rounded-panel bg-surface lg:sticky lg:top-3 lg:flex lg:h-[calc(100dvh-24px)] lg:w-[236px] lg:shrink-0 lg:flex-col">
          <div className="px-[14px] pb-[28px] pt-[18px]">
            <Brand href={homeHref} />
          </div>
          <SidebarNav accountId={accountId} />
        </aside>

        {/* Mobile full-height drawer */}
        {mobileOpen ? (
          <div className="fixed inset-0 z-40 lg:hidden">
            <button
              type="button"
              aria-label="Cerrar menú"
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
                  aria-label="Cerrar menú"
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
          <header className="flex h-16 shrink-0 items-center gap-3 border-b border-glass px-4 lg:h-20 lg:px-6">
            <button
              type="button"
              aria-label="Abrir menú"
              onClick={() => setMobileOpen(true)}
              className="inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-control text-fg-muted hover:bg-hover-glass hover:text-fg lg:hidden"
            >
              <Menu className="h-5 w-5" aria-hidden />
            </button>

            <div className="neon-sign min-w-0">
              <h1 className="text-[24px] leading-[1.2] lg:text-[34px]">
                {signTitle}
              </h1>
            </div>

            <div className="ml-auto flex items-center gap-1.5 sm:gap-2">
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
