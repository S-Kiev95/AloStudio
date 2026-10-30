import {
  BarChart3,
  BookOpen,
  CalendarDays,
  ChartLine,
  Home,
  Images,
  Inbox,
  Instagram,
  type LucideIcon,
  Megaphone,
  Settings,
  Sparkles,
  Users,
} from "lucide-react";

export type NavItem = {
  key: string;
  label: string;
  icon: LucideIcon;
  segment: string; // "" = account home
  /** Additional segments under `/accounts/[accountId]/` that activate this item. */
  matchSegments?: string[];
};

export const NAV_ITEMS: NavItem[] = [
  { key: "home", label: "Inicio", icon: Home, segment: "" },
  {
    key: "calendar",
    label: "Calendario",
    icon: CalendarDays,
    segment: "publications",
  },
  {
    key: "agent",
    label: "Agente",
    icon: Sparkles,
    segment: "agent",
  },
  {
    key: "analytics",
    label: "Estadísticas",
    icon: ChartLine,
    segment: "publications/analytics",
  },
  {
    key: "media",
    label: "Medios",
    icon: Images,
    segment: "publications/media",
  },
  {
    key: "conversations",
    label: "Bandeja",
    icon: Inbox,
    segment: "conversations",
  },
  {
    key: "crm",
    label: "CRM",
    icon: Users,
    segment: "contacts",
    matchSegments: ["contacts", "products", "agenda"],
  },
  { key: "instagram", label: "Instagram", icon: Instagram, segment: "instagram" },
  {
    key: "help-center",
    label: "Help Center",
    icon: BookOpen,
    segment: "help-center",
  },
  {
    key: "campaigns",
    label: "Campañas",
    icon: Megaphone,
    segment: "campaigns",
  },
  { key: "reports", label: "Reportes", icon: BarChart3, segment: "reports" },
  { key: "settings", label: "Ajustes", icon: Settings, segment: "settings" },
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
