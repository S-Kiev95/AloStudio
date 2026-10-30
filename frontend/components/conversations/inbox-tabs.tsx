"use client";

import { usePathname } from "next/navigation";

import { NavTabs } from "@/components/ui/tabs";

export function InboxTabs({ accountId }: { accountId: string }) {
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
      ariaLabel="Secciones de la bandeja"
      className="mb-4"
      items={[
        {
          href: base,
          label: "Conversaciones",
          active: isConversations,
        },
        {
          href: reportsHref,
          label: "Reportes",
          active: isReports,
        },
        {
          href: channelsHref,
          label: "Canales",
          active: isChannels,
        },
      ]}
    />
  );
}
