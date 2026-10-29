"use client";

import { usePathname } from "next/navigation";

import { NavTabs } from "@/components/ui/tabs";

export function CrmTabs({ accountId }: { accountId: string }) {
  const pathname = usePathname() ?? "";
  const tabs = [
    { href: `/accounts/${accountId}/contacts`, label: "Contactos" },
    { href: `/accounts/${accountId}/products`, label: "Productos" },
    { href: `/accounts/${accountId}/agenda`, label: "Agenda" },
  ];

  return (
    <NavTabs
      ariaLabel="Secciones de CRM"
      className="mb-6"
      items={tabs.map((t) => ({
        href: t.href,
        label: t.label,
        active: pathname === t.href || pathname.startsWith(`${t.href}/`),
      }))}
    />
  );
}
