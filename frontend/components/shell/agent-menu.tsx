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
          "relative flex h-10 cursor-pointer list-none items-center gap-2 rounded-control px-1.5 text-sm text-fg transition-colors",
          "after:absolute after:-inset-y-0.5 after:inset-x-0 after:content-['']",
          "hover:bg-hover-glass focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-neon",
        )}
        aria-label="Menú de usuario"
      >
        <span className="flex h-8 w-8 items-center justify-center rounded-full bg-focused text-xs font-medium text-lit ring-1 ring-inset ring-glass">
          {initials}
        </span>
      </summary>
      <div
        className="absolute right-0 z-30 mt-1.5 w-60 overflow-hidden rounded-md border border-glass bg-surface-2 shadow-menu"
        role="menu"
      >
        <div className="border-b border-glass px-3 py-3">
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
          className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-danger transition-colors hover:bg-hover-glass disabled:opacity-50"
        >
          <LogOut className="h-4 w-4" aria-hidden />
          Cerrar sesión
        </button>
      </div>
    </details>
  );
}
