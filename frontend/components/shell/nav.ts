import {
  BarChart3,
  Home,
  Instagram,
  type LucideIcon,
  MessagesSquare,
  Package,
  Settings,
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
  { key: "instagram", label: "Instagram", icon: Instagram, segment: "instagram" },
  { key: "products", label: "Productos", icon: Package, segment: "products" },
  { key: "reports", label: "Reportes", icon: BarChart3, segment: "reports" },
  { key: "settings", label: "Ajustes", icon: Settings, segment: "settings" },
];

export function navHref(accountId: string, segment: string): string {
  return segment ? `/accounts/${accountId}/${segment}` : `/accounts/${accountId}`;
}
