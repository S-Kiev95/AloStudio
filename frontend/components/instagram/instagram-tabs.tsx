"use client";

import { usePathname } from "next/navigation";

import { NavTabs } from "@/components/ui/tabs";
import { useT } from "@/lib/i18n/provider";

export function InstagramTabs({ accountId }: { accountId: string }) {
  const t = useT();
  const pathname = usePathname();
  const tabs = [
    { href: `/accounts/${accountId}/instagram`, label: t("instagram.tabs.connection"), exact: true },
    {
      href: `/accounts/${accountId}/instagram/posts`,
      label: t("instagram.tabs.posts"),
      exact: false,
    },
    {
      href: `/accounts/${accountId}/instagram/autoreply`,
      label: t("instagram.tabs.autoreplies"),
      exact: false,
    },
  ];
  return (
    <NavTabs
      ariaLabel={t("instagram.tabs.label")}
      className="mb-6"
      items={tabs.map((t) => ({
        href: t.href,
        label: t.label,
        active: t.exact ? pathname === t.href : pathname.startsWith(t.href),
      }))}
    />
  );
}
