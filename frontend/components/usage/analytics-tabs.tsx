"use client";

import { usePathname } from "next/navigation";

import { NavTabs } from "@/components/ui/tabs";
import { useT } from "@/lib/i18n/provider";

/** Estadísticas: the posts' figures and what the account spends (F6). */
export function AnalyticsTabs({ accountId }: { accountId: string }) {
  const t = useT();
  const pathname = usePathname() ?? "";
  const base = `/accounts/${accountId}/publications/analytics`;
  return (
    <NavTabs
      ariaLabel={t("nav.analytics")}
      className="mx-auto mb-4 max-w-7xl"
      items={[
        { href: base, label: t("usage.tabPublications"), active: pathname === base },
        {
          href: `${base}/costs`,
          label: t("usage.tabCosts"),
          active: pathname.startsWith(`${base}/costs`),
        },
      ]}
    />
  );
}
