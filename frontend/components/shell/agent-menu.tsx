"use client";

import { LogOut, UserCircle2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { useDismissOnOutsideAndEscape } from "@/lib/hooks/use-dismiss";
import { useT } from "@/lib/i18n/provider";
import { animatePopoverIn } from "@/lib/motion/neon-motion";
import { cn } from "@/lib/utils";

export function AgentMenu({
  name,
  email,
}: {
  name: string;
  email: string;
}) {
  const router = useRouter();
  const t = useT();
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);
  const detailsRef = useRef<HTMLDetailsElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    return animatePopoverIn(menuRef.current);
  }, [open]);

  useDismissOnOutsideAndEscape(detailsRef, open, () => {
    detailsRef.current?.removeAttribute("open");
    setOpen(false);
  });

  const initials =
    name
      .split(" ")
      .map((p) => p[0])
      .filter(Boolean)
      .slice(0, 2)
      .join("")
      .toUpperCase() || "?";

  async function onLogout() {
    setLoading(true);
    await fetch("/api/auth/logout", { method: "POST" });
    router.push("/login");
    router.refresh();
  }

  return (
    <details
      ref={detailsRef}
      className="group relative"
      onToggle={(e) => setOpen((e.currentTarget as HTMLDetailsElement).open)}
    >
      <summary
        className={cn(
          "relative flex h-10 cursor-pointer list-none items-center gap-2 rounded-control px-1.5 text-sm text-fg transition-colors",
          "after:absolute after:-inset-y-0.5 after:inset-x-0 after:content-['']",
          "hover:bg-hover-glass focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-neon",
        )}
        aria-label={t("shell.userMenu")}
      >
        <span className="flex h-8 w-8 items-center justify-center rounded-full bg-focused text-xs font-medium text-lit ring-1 ring-inset ring-glass">
          {initials}
        </span>
      </summary>
      <div
        ref={menuRef}
        className="glass-dialog z-30 overflow-hidden rounded-md max-sm:fixed max-sm:right-3 max-sm:top-[4.5rem] max-sm:w-60 sm:absolute sm:right-0 sm:mt-1.5 sm:w-60"
        role="menu"
      >
        <div className="border-b border-glass px-3 py-3">
          <p className="flex items-center gap-2 text-sm font-medium text-fg">
            <UserCircle2 className="h-4 w-4 text-fg-muted" aria-hidden />
            <span className="truncate">{name || t("shell.user")}</span>
          </p>
          <p className="mt-0.5 truncate text-xs text-fg-muted">{email}</p>
        </div>
        <button
          type="button"
          onClick={onLogout}
          disabled={loading}
          role="menuitem"
          className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-danger transition-colors hover:bg-hover-glass disabled:opacity-50"
        >
          <LogOut className="h-4 w-4" aria-hidden />
          {t("shell.logout")}
        </button>
      </div>
    </details>
  );
}
