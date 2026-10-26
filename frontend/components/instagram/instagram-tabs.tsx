"use client";

import { usePathname } from "next/navigation";

import { NavTabs } from "@/components/ui/tabs";

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
    <NavTabs
      ariaLabel="Secciones de Instagram"
      className="mb-6"
      items={tabs.map((t) => ({
        href: t.href,
        label: t.label,
        active: t.exact ? pathname === t.href : pathname.startsWith(t.href),
      }))}
    />
  );
}
