"use client";

import { Search } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useMemo, useState } from "react";

import { Input } from "@/components/ui/input";
import { selectClassName } from "@/components/ui/select";
import { useT } from "@/lib/i18n/provider";
import type { MessageKey } from "@/lib/i18n/translate";
import { cn } from "@/lib/utils";

export type SettingsGroupKey =
  | "publishing"
  | "account"
  | "inbox"
  | "automation"
  | "crm"
  | "system";

export type SettingsItem = {
  segment: string;
  /** Message key; render with `t()`. */
  label: MessageKey;
  milestone: string;
  done: boolean;
  group: SettingsGroupKey;
};

export const SETTINGS_GROUP_ORDER: readonly {
  key: SettingsGroupKey;
  label: MessageKey;
}[] = [
  { key: "account", label: "settings.groups.account" },
  { key: "inbox", label: "settings.groups.inbox" },
  { key: "automation", label: "settings.groups.automation" },
  { key: "crm", label: "settings.groups.crm" },
  { key: "publishing", label: "settings.groups.publishing" },
  { key: "system", label: "settings.groups.system" },
];

export const SETTINGS_ITEMS: SettingsItem[] = [
  // Cuenta y equipo
  { segment: "profile", label: "settings.items.profile", milestone: "fe.14c", done: true, group: "account" },
  { segment: "security", label: "settings.items.security", milestone: "fe.14c", done: true, group: "account" },
  { segment: "notifications", label: "settings.items.notifications", milestone: "fe.14d", done: true, group: "account" },
  { segment: "agents", label: "settings.items.agents", milestone: "fe.14c", done: true, group: "account" },
  { segment: "teams", label: "settings.items.teams", milestone: "F.9b", done: true, group: "account" },
  // Canales y bandeja
  { segment: "inboxes", label: "settings.items.inboxes", milestone: "v2", done: true, group: "inbox" },
  { segment: "assignment_policies", label: "settings.items.assignment_policies", milestone: "v2", done: true, group: "inbox" },
  { segment: "working_hours", label: "settings.items.working_hours", milestone: "F.9d", done: true, group: "inbox" },
  { segment: "labels", label: "settings.items.labels", milestone: "F.9a", done: true, group: "inbox" },
  { segment: "canned_responses", label: "settings.items.canned_responses", milestone: "F.9c", done: true, group: "inbox" },
  { segment: "closing_notes", label: "settings.items.closing_notes", milestone: "F17", done: true, group: "inbox" },
  { segment: "csat", label: "settings.items.csat", milestone: "F.9g", done: true, group: "inbox" },
  // Automatización e IA
  { segment: "automation", label: "settings.items.automation", milestone: "F.9e", done: true, group: "automation" },
  { segment: "macros", label: "settings.items.macros", milestone: "F.9c", done: true, group: "automation" },
  { segment: "agent_bots", label: "settings.items.agent_bots", milestone: "F.9f", done: true, group: "automation" },
  { segment: "decisions", label: "settings.items.decisions", milestone: "F10", done: true, group: "automation" },
  // CRM y ventas
  { segment: "lifecycle", label: "settings.items.lifecycle", milestone: "F17", done: true, group: "crm" },
  { segment: "custom_attributes", label: "settings.items.custom_attributes", milestone: "F.9d", done: true, group: "crm" },
  { segment: "conversions", label: "settings.items.conversions", milestone: "F17", done: true, group: "crm" },
  // Publicación
  { segment: "signatures", label: "settings.items.signatures", milestone: "F.7", done: true, group: "publishing" },
  { segment: "sets", label: "settings.items.sets", milestone: "F.7", done: true, group: "publishing" },
  { segment: "autoposts", label: "settings.items.autoposts", milestone: "F.7", done: true, group: "publishing" },
  { segment: "plugs", label: "settings.items.plugs", milestone: "F.7", done: true, group: "publishing" },
  // Integraciones y sistema
  { segment: "integrations", label: "settings.items.integrations", milestone: "F.9f", done: true, group: "system" },
  { segment: "webhooks", label: "settings.items.webhooks", milestone: "F.9f", done: true, group: "system" },
  { segment: "mcp_tokens", label: "settings.items.mcp_tokens", milestone: "F.9h", done: true, group: "system" },
  { segment: "oauth_apps", label: "settings.items.oauth_apps", milestone: "F.7", done: true, group: "system" },
  { segment: "email_templates", label: "settings.items.email_templates", milestone: "F.9i", done: true, group: "system" },
  { segment: "installation", label: "settings.items.installation", milestone: "F.9i", done: true, group: "system" },
];

function normalizeSearch(value: string): string {
  return value
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .trim();
}

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
          "block whitespace-nowrap rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
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
  const router = useRouter();
  const baseHref = `/accounts/${accountId}/settings`;
  const t = useT();
  const [query, setQuery] = useState("");

  const needle = normalizeSearch(query);

  const grouped = useMemo(
    () =>
      SETTINGS_GROUP_ORDER.map((group) => {
        const items = SETTINGS_ITEMS.filter((item) => {
          if (item.group !== group.key) return false;
          if (!needle) return true;
          return (
            normalizeSearch(t(item.label)).includes(needle) ||
            normalizeSearch(t(group.label)).includes(needle)
          );
        });
        return { ...group, items };
      }).filter((g) => g.items.length > 0),
    [needle, t],
  );

  const activeSegment =
    SETTINGS_ITEMS.find((item) => {
      const href = `${baseHref}/${item.segment}`;
      return pathname === href || pathname.startsWith(`${href}/`);
    })?.segment ?? "";

  return (
    <nav
      aria-label={t("settings.title")}
      className="w-full shrink-0 border-b border-glass pb-3 md:w-60 md:border-b-0 md:border-r md:pb-0 md:pr-4"
    >
      {/* Desktop: quick filter + 6 thematic groups */}
      <div className="hidden md:block">
        <div className="relative mb-3">
          <Search
            className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-fg-muted"
            aria-hidden
          />
          <Input
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            aria-label={t("settings.searchPlaceholder")}
            placeholder={t("settings.searchPlaceholder")}
            className="h-9 pl-8 pr-2.5 text-xs"
          />
        </div>

        {grouped.length === 0 ? (
          <p className="px-3 py-2 text-xs text-fg-muted">
            {t("settings.noMatches")}
          </p>
        ) : (
          <div className="space-y-4">
            {grouped.map((group) => (
              <div key={group.key}>
                <p className="px-3 pb-1 text-[11px] font-semibold uppercase tracking-[0.08em] text-fg-muted">
                  {t(group.label)}
                </p>
                <ul className="flex flex-col gap-0.5">
                  {group.items.map((item) => (
                    <SidebarRow
                      key={item.segment}
                      baseHref={baseHref}
                      pathname={pathname}
                      item={item}
                    />
                  ))}
                </ul>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Mobile: grouped native selector (replaces 3324px blind horizontal strip) */}
      <div className="md:hidden">
        <select
          aria-label={t("settings.sectionSelect")}
          value={activeSegment}
          onChange={(e) => {
            const seg = e.target.value;
            if (seg) router.push(`${baseHref}/${seg}`);
          }}
          className={cn(selectClassName("md"), "w-full font-medium")}
        >
          {SETTINGS_GROUP_ORDER.map((group) => {
            const items = SETTINGS_ITEMS.filter(
              (item) => item.group === group.key && item.done,
            );
            if (items.length === 0) return null;
            return (
              <optgroup key={group.key} label={t(group.label)}>
                {items.map((item) => (
                  <option
                    key={item.segment}
                    value={item.segment}
                    className="bg-surface-2 text-fg"
                  >
                    {t(item.label)}
                  </option>
                ))}
              </optgroup>
            );
          })}
        </select>
      </div>
    </nav>
  );
}
