import {
  BarChart3,
  BookOpen,
  Home,
  Instagram,
  type LucideIcon,
  Megaphone,
  MessagesSquare,
  Package,
  Settings,
  Users,
} from "lucide-react";

export type NavItem = {
  key: string;
  label: string;
  icon: LucideIcon;
  segment: string; // "" = account home
};

export const NAV_ITEMS: NavItem[] = [
  { key: "home", label: "Inicio", icon: Home, segment: "" },
  {
    key: "conversations",
    label: "Conversaciones",
    icon: MessagesSquare,
    segment: "conversations",
  },
  { key: "contacts", label: "Contactos", icon: Users, segment: "contacts" },
  { key: "instagram", label: "Instagram", icon: Instagram, segment: "instagram" },
  { key: "products", label: "Productos", icon: Package, segment: "products" },
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

/** The nav grouped into labelled sections — a quieter, more scannable sidebar
 *  than one flat list of nine. `label: null` renders headerless (Inicio sits
 *  on its own up top; Ajustes on its own at the bottom). */
export type NavGroup = { label: string | null; keys: string[] };

export const NAV_GROUPS: NavGroup[] = [
  { label: null, keys: ["home"] },
  { label: "Bandeja", keys: ["conversations", "contacts", "instagram"] },
  {
    label: "Crecimiento",
    keys: ["products", "help-center", "campaigns", "reports"],
  },
  { label: null, keys: ["settings"] },
];

export function navHref(accountId: string, segment: string): string {
  return segment ? `/accounts/${accountId}/${segment}` : `/accounts/${accountId}`;
}
