"use client";

import { usePathname } from "next/navigation";

import { NavTabs } from "@/components/ui/tabs";
import { useT } from "@/lib/i18n/provider";

export function CrmTabs({ accountId }: { accountId: string }) {
  const t = useT();
  const pathname = usePathname() ?? "";
  const tabs = [
    { href: `/accounts/${accountId}/contacts`, label: t("crm.contacts") },
    { href: `/accounts/${accountId}/opportunities`, label: t("opportunities.pageTitle") },
    { href: `/accounts/${accountId}/tasks`, label: t("activities.pageTitle") },
    { href: `/accounts/${accountId}/products`, label: t("crm.products") },
    { href: `/accounts/${accountId}/agenda`, label: t("crm.agenda") },
  ];

  return (
    <NavTabs
      ariaLabel={t("crm.label")}
      className="mb-6"
      items={tabs.map((t) => ({
        href: t.href,
        label: t.label,
        active: pathname === t.href || pathname.startsWith(`${t.href}/`),
      }))}
    />
  );
}
