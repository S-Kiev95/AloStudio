"use client";

import { LogOut, UserCircle2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { cn } from "@/lib/utils";

export function AgentMenu({
  name,
  email,
}: {
  name: string;
  email: string;
}) {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
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
    <details className="group relative">
      <summary
        className={cn(
          "flex cursor-pointer list-none items-center gap-2 rounded-md px-1.5 py-1 text-sm text-fg",
          "hover:bg-surface-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        )}
        aria-label="Menú de usuario"
      >
        <span className="flex h-8 w-8 items-center justify-center rounded-full bg-primary text-xs font-semibold text-primary-fg">
          {initials}
        </span>
      </summary>
      <div
        className="absolute right-0 z-20 mt-1 w-60 overflow-hidden rounded-md border border-border bg-surface shadow-md"
        role="menu"
      >
        <div className="border-b border-border px-3 py-3">
          <p className="flex items-center gap-2 text-sm font-medium text-fg">
            <UserCircle2 className="h-4 w-4 text-fg-muted" aria-hidden />
            <span className="truncate">{name || "Usuario"}</span>
          </p>
          <p className="mt-0.5 truncate text-xs text-fg-muted">{email}</p>
        </div>
        <button
          type="button"
          onClick={onLogout}
          disabled={loading}
          role="menuitem"
          className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-danger hover:bg-surface-2 disabled:opacity-50"
        >
          <LogOut className="h-4 w-4" aria-hidden />
          Cerrar sesión
        </button>
      </div>
    </details>
  );
}
