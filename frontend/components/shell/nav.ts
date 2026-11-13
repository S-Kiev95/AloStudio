import { Settings } from "lucide-react";

import type { IconComponent } from "@/components/ui/brand-icons";
import type { MessageKey } from "@/lib/i18n/translate";

import {
  AgentIcon,
  BarsIcon,
  BookIcon,
  CalendarIcon,
  HomeIcon,
  InboxIcon,
  InstagramNavIcon,
  MediaIcon,
  MegaphoneIcon,
  PeopleIcon,
  StatsIcon,
} from "./app-icons";

export type NavItem = {
  key: string;
  /** Message key of the label, e.g. `"nav.home"`; render with `t()`. */
  label: MessageKey;
  icon: IconComponent;
  segment: string; // "" = account home
  /** Additional segments under `/accounts/[accountId]/` that activate this item. */
  matchSegments?: string[];
};

export const NAV_ITEMS: NavItem[] = [
  { key: "home", label: "nav.home", icon: HomeIcon, segment: "" },
  {
    key: "calendar",
    label: "nav.calendar",
    icon: CalendarIcon,
    segment: "publications",
  },
  {
    key: "agent",
    label: "nav.agent",
    icon: AgentIcon,
    segment: "agent",
  },
  {
    key: "analytics",
    label: "nav.analytics",
    icon: StatsIcon,
    segment: "publications/analytics",
  },
  {
    key: "media",
    label: "nav.media",
    icon: MediaIcon,
    segment: "publications/media",
  },
  {
    key: "conversations",
    label: "nav.conversations",
    icon: InboxIcon,
    segment: "conversations",
  },
  {
    key: "crm",
    label: "nav.crm",
    icon: PeopleIcon,
    segment: "contacts",
    matchSegments: ["contacts", "companies", "opportunities", "tasks", "products", "agenda"],
  },
  { key: "instagram", label: "nav.instagram", icon: InstagramNavIcon, segment: "instagram" },
  {
    key: "help-center",
    label: "nav.helpCenter",
    icon: BookIcon,
    segment: "help-center",
  },
  {
    key: "campaigns",
    label: "nav.campaigns",
    icon: MegaphoneIcon,
    segment: "campaigns",
  },
  { key: "reports", label: "nav.reports", icon: BarsIcon, segment: "reports" },
  { key: "settings", label: "nav.settings", icon: Settings, segment: "settings" },
];

/** Flat main section list up top with Ajustes pinned to the bottom (DESIGN.md). */
export type NavGroup = { label: string | null; keys: string[] };

export const NAV_GROUPS: NavGroup[] = [
  {
    label: null,
    keys: [
      "home",
      "calendar",
      "agent",
      "analytics",
      "media",
      "conversations",
      "crm",
      "instagram",
      "help-center",
      "campaigns",
      "reports",
    ],
  },
  { label: null, keys: ["settings"] },
];

export function navHref(accountId: string, segment: string): string {
  return segment ? `/accounts/${accountId}/${segment}` : `/accounts/${accountId}`;
}

/**
 * Resolve which ``NavItem.key`` is active for ``pathname`` using longest-prefix
 * matching so ``publications/media`` and ``publications/analytics`` do not
 * highlight ``Calendario`` (``publications``), while subroutes and CRM tabs do.
 */
export function activeNavItemKey(
  pathname: string,
  accountId: string,
): string | null {
  const homeHref = navHref(accountId, "");
  if (pathname === homeHref) return "home";

  let bestKey: string | null = null;
  let bestLen = -1;

  for (const item of NAV_ITEMS) {
    const segments = item.matchSegments ?? (item.segment ? [item.segment] : []);
    for (const seg of segments) {
      if (!seg) continue;
      const href = navHref(accountId, seg);
      if (pathname === href || pathname.startsWith(`${href}/`)) {
        if (href.length > bestLen) {
          bestLen = href.length;
          bestKey = item.key;
        }
      }
    }
  }

  return bestKey;
}
