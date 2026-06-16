"use client";

import { Menu, X } from "lucide-react";
import { useState, type ReactNode } from "react";

import type { Profile } from "@/lib/auth/profile";
import { useCable } from "@/lib/realtime/use-cable";

import { AccountSwitcher } from "./account-switcher";
import { AgentMenu } from "./agent-menu";
import { NotificationBell } from "./notification-bell";
import { SidebarNav } from "./sidebar-nav";
import { ThemeToggle } from "./theme-toggle";

/** Yellow brand mark + wordmark, shared by the desktop sidebar + mobile drawer. */
function Brand() {
  return (
    <span className="flex items-center gap-2">
      <span className="grid h-7 w-7 place-items-center rounded-md bg-primary text-sm font-bold text-primary-fg">
        A
      </span>
      <span className="text-lg font-semibold tracking-tight">AloStudio</span>
    </span>
  );
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
  const [mobileOpen, setMobileOpen] = useState(false);

  // Realtime: subscribe once per account; events invalidate query caches.
  useCable({
    pubsubToken: profile.pubsubToken,
    userId: profile.id,
    accountId,
  });

  return (
    <div className="min-h-dvh bg-bg text-fg">
      {/* Desktop sidebar */}
      <aside className="fixed inset-y-0 left-0 hidden w-64 border-r border-border bg-surface lg:block">
        <div className="flex h-14 items-center border-b border-border px-5">
          <Brand />
        </div>
        <SidebarNav accountId={accountId} />
      </aside>

      {/* Mobile drawer */}
      {mobileOpen ? (
        <div className="fixed inset-0 z-40 lg:hidden">
          <button
            aria-label="Cerrar menú"
            className="absolute inset-0 bg-black/50"
            onClick={() => setMobileOpen(false)}
          />
          <aside className="absolute inset-y-0 left-0 w-64 border-r border-border bg-surface">
            <div className="flex h-14 items-center justify-between border-b border-border px-5">
              <Brand />
              <button
                aria-label="Cerrar menú"
                onClick={() => setMobileOpen(false)}
                className="rounded-md p-1 text-fg-muted hover:bg-surface-2"
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

      <div className="lg:pl-64">
        {/* Topbar — flat on the canvas with a hairline divider (no
            glassmorphism: Binance trusts color-block contrast over blur). */}
        <header className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b border-border bg-bg px-4">
          <button
            aria-label="Abrir menú"
            onClick={() => setMobileOpen(true)}
            className="rounded-md p-1.5 text-fg-muted hover:bg-surface-2 lg:hidden"
          >
            <Menu className="h-5 w-5" aria-hidden />
          </button>
          <AccountSwitcher accountId={accountId} accounts={profile.accounts} />
          <div className="ml-auto flex items-center gap-1">
            <NotificationBell accountId={accountId} />
            <ThemeToggle />
            <AgentMenu name={profile.name} email={profile.email} />
          </div>
        </header>

        <main id="main-content" className="p-4 sm:p-6">{children}</main>
      </div>
    </div>
  );
}
