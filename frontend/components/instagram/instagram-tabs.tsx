"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { cn } from "@/lib/utils";

export function InstagramTabs({ accountId }: { accountId: string }) {
  const pathname = usePathname();
  const tabs = [
    { href: `/accounts/${accountId}/instagram`, label: "Conexión", exact: true },
    {
      href: `/accounts/${accountId}/instagram/posts`,
      label: "Publicaciones",
      exact: false,
    },
    {
      href: `/accounts/${accountId}/instagram/autoreply`,
      label: "Respuestas automáticas",
      exact: false,
    },
  ];
  return (
    <div className="mb-6 flex gap-1 border-b border-border">
      {tabs.map((t) => {
        const active = t.exact
          ? pathname === t.href
          : pathname.startsWith(t.href);
        return (
          <Link
            key={t.href}
            href={t.href}
            aria-current={active ? "page" : undefined}
            className={cn(
              "-mb-px border-b-2 px-3 py-2 text-sm font-medium",
              active
                ? "border-primary text-fg"
                : "border-transparent text-fg-muted hover:text-fg",
            )}
          >
            {t.label}
          </Link>
        );
      })}
    </div>
  );
}
