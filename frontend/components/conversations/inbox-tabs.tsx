"use client";

import { usePathname } from "next/navigation";

import { NavTabs } from "@/components/ui/tabs";
import { useT } from "@/lib/i18n/provider";

export function InboxTabs({ accountId }: { accountId: string }) {
  const t = useT();
  const pathname = usePathname() ?? "";
  const base = `/accounts/${accountId}/conversations`;
  const reportsHref = `${base}/reports`;
  const channelsHref = `${base}/channels`;

  const isReports =
    pathname === reportsHref || pathname.startsWith(`${reportsHref}/`);
  const isChannels =
    pathname === channelsHref || pathname.startsWith(`${channelsHref}/`);
  const isConversations =
    !isReports &&
    !isChannels &&
    (pathname === base || pathname.startsWith(`${base}/`));

  return (
    <NavTabs
      ariaLabel={t("conversations.tabs.label")}
      className="mb-4"
      items={[
        {
          href: base,
          label: t("conversations.tabs.conversations"),
          active: isConversations,
        },
        {
          href: reportsHref,
          label: t("conversations.tabs.reports"),
          active: isReports,
        },
        {
          href: channelsHref,
          label: t("conversations.tabs.channels"),
          active: isChannels,
        },
      ]}
    />
  );
}
