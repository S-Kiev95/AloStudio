"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { useT } from "@/lib/i18n/provider";
import type { MessageKey } from "@/lib/i18n/translate";
import { cn } from "@/lib/utils";

export type SettingsItem = {
  segment: string;
  /** Message key; render with `t()`. */
  label: MessageKey;
  milestone: string;
  done: boolean;
  group?: "general" | "publishing";
};

export const SETTINGS_ITEMS: SettingsItem[] = [
  { segment: "agents", label: "settings.items.agents", milestone: "fe.14c", done: true },
  { segment: "profile", label: "settings.items.profile", milestone: "fe.14c", done: true },
  {
    segment: "security",
    label: "settings.items.security",
    milestone: "fe.14c",
    done: true,
  },
  {
    segment: "notifications",
    label: "settings.items.notifications",
    milestone: "fe.14d",
    done: true,
  },
  { segment: "labels", label: "settings.items.labels", milestone: "F.9a", done: true },
  { segment: "teams", label: "settings.items.teams", milestone: "F.9b", done: true },
  {
    segment: "inboxes",
    label: "settings.items.inboxes",
    milestone: "v2",
    done: true,
  },
  {
    segment: "assignment_policies",
    label: "settings.items.assignment_policies",
    milestone: "v2",
    done: true,
  },
  {
    segment: "canned_responses",
    label: "settings.items.canned_responses",
    milestone: "F.9c",
    done: true,
  },
  { segment: "macros", label: "settings.items.macros", milestone: "F.9c", done: true },
  {
    segment: "working_hours",
    label: "settings.items.working_hours",
    milestone: "F.9d",
    done: true,
  },
  {
    segment: "custom_attributes",
    label: "settings.items.custom_attributes",
    milestone: "F.9d",
    done: true,
  },
  {
    segment: "automation",
    label: "settings.items.automation",
    milestone: "F.9e",
    done: true,
  },
  { segment: "webhooks", label: "settings.items.webhooks", milestone: "F.9f", done: true },
  { segment: "agent_bots", label: "settings.items.agent_bots", milestone: "F.9f", done: true },
  {
    segment: "integrations",
    label: "settings.items.integrations",
    milestone: "F.9f",
    done: true,
  },
  { segment: "csat", label: "settings.items.csat", milestone: "F.9g", done: true },
  {
    segment: "mcp_tokens",
    label: "settings.items.mcp_tokens",
    milestone: "F.9h",
    done: true,
  },
  {
    segment: "oauth_apps",
    label: "settings.items.oauth_apps",
    milestone: "F.7",
    done: true,
  },
  {
    segment: "email_templates",
    label: "settings.items.email_templates",
    milestone: "F.9i",
    done: true,
  },
  {
    segment: "installation",
    label: "settings.items.installation",
    milestone: "F.9i",
    done: true,
  },
  {
    segment: "signatures",
    label: "settings.items.signatures",
    milestone: "F.7",
    done: true,
    group: "publishing",
  },
  {
    segment: "sets",
    label: "settings.items.sets",
    milestone: "F.7",
    done: true,
    group: "publishing",
  },
  {
    segment: "autoposts",
    label: "settings.items.autoposts",
    milestone: "F.7",
    done: true,
    group: "publishing",
  },
  {
    segment: "plugs",
    label: "settings.items.plugs",
    milestone: "F.7",
    done: true,
    group: "publishing",
  },
];

function SidebarRow({
  baseHref,
  pathname,
  item,
}: {
  baseHref: string;
  pathname: string;
  item: SettingsItem;
}) {
  const t = useT();
  const href = `${baseHref}/${item.segment}`;
  const active = pathname === href || pathname.startsWith(`${href}/`);
  if (!item.done) {
    return (
      <li className="shrink-0">
        <span
          className="flex cursor-not-allowed items-center justify-between gap-2 whitespace-nowrap rounded-md px-3 py-2 text-sm text-fg-muted opacity-60"
          title={t("settings.comingIn", { milestone: item.milestone })}
        >
          {t(item.label)}
          <span className="rounded-sm bg-surface-2 px-1 py-0.5 text-[9px] uppercase">
            {item.milestone}
          </span>
        </span>
      </li>
    );
  }
  return (
    <li className="shrink-0">
      <Link
        href={href}
        aria-current={active ? "page" : undefined}
        className={cn(
          "block whitespace-nowrap rounded-md px-3 py-2 text-sm font-medium transition-colors",
          "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-neon",
          active
            ? "bg-focused text-lit"
            : "text-fg-muted hover:bg-hover-glass hover:text-fg",
        )}
      >
        {t(item.label)}
      </Link>
    </li>
  );
}

export function SettingsSidebar({ accountId }: { accountId: string }) {
  const pathname = usePathname() ?? "";
  const baseHref = `/accounts/${accountId}/settings`;
  const t = useT();

  const generalItems = SETTINGS_ITEMS.filter((i) => i.group !== "publishing");
  const publishingItems = SETTINGS_ITEMS.filter(
    (i) => i.group === "publishing",
  );

  return (
    <nav
      aria-label={t("settings.title")}
      className="w-full shrink-0 border-b border-glass pb-2 md:w-56 md:border-b-0 md:border-r md:pb-0 md:pr-3"
    >
      <div className="hidden md:block">
        <p className="px-3 pb-1 text-[11px] font-semibold uppercase tracking-wider text-fg-muted">
          {t("settings.groups.publishing")}
        </p>
        <ul className="flex flex-col gap-0.5">
          {publishingItems.map((item) => (
            <SidebarRow
              key={item.segment}
              baseHref={baseHref}
              pathname={pathname}
              item={item}
            />
          ))}
        </ul>

        <p className="px-3 pb-1 pt-4 text-[11px] font-semibold uppercase tracking-wider text-fg-muted">
          {t("settings.groups.account")}
        </p>
        <ul className="flex flex-col gap-0.5">
          {generalItems.map((item) => (
            <SidebarRow
              key={item.segment}
              baseHref={baseHref}
              pathname={pathname}
              item={item}
            />
          ))}
        </ul>
      </div>

      {/* Horizontal pill strip on small screens */}
      <ul className="flex gap-1 overflow-x-auto md:hidden">
        {[...publishingItems, ...generalItems].map((item) => (
          <SidebarRow
            key={item.segment}
            baseHref={baseHref}
            pathname={pathname}
            item={item}
          />
        ))}
      </ul>
    </nav>
  );
}
