"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { cn } from "@/lib/utils";

export type SettingsItem = {
  segment: string;
  label: string;
  milestone: string;
  done: boolean;
};

export const SETTINGS_ITEMS: SettingsItem[] = [
  { segment: "agents", label: "Agentes", milestone: "fe.14c", done: true },
  { segment: "profile", label: "Mi perfil", milestone: "fe.14c", done: true },
  {
    segment: "security",
    label: "Seguridad",
    milestone: "fe.14c",
    done: true,
  },
  {
    segment: "notifications",
    label: "Notificaciones",
    milestone: "fe.14d",
    done: true,
  },
  { segment: "labels", label: "Etiquetas", milestone: "F.9a", done: true },
  { segment: "teams", label: "Equipos", milestone: "F.9b", done: true },
  {
    segment: "inboxes",
    label: "Bandejas de entrada",
    milestone: "v2",
    done: true,
  },
  {
    segment: "assignment_policies",
    label: "Políticas de asignación",
    milestone: "v2",
    done: true,
  },
  {
    segment: "canned_responses",
    label: "Respuestas predefinidas",
    milestone: "F.9c",
    done: true,
  },
  { segment: "macros", label: "Macros", milestone: "F.9c", done: true },
  {
    segment: "working_hours",
    label: "Horarios laborales",
    milestone: "F.9d",
    done: true,
  },
  {
    segment: "custom_attributes",
    label: "Atributos personalizados",
    milestone: "F.9d",
    done: true,
  },
  {
    segment: "automation",
    label: "Automatización",
    milestone: "F.9e",
    done: true,
  },
  { segment: "webhooks", label: "Webhooks", milestone: "F.9f", done: true },
  { segment: "agent_bots", label: "Bots", milestone: "F.9f", done: true },
  {
    segment: "integrations",
    label: "Integraciones",
    milestone: "F.9f",
    done: true,
  },
  { segment: "csat", label: "CSAT", milestone: "F.9g", done: true },
  {
    segment: "mcp_tokens",
    label: "Tokens MCP",
    milestone: "F.9h",
    done: true,
  },
  {
    segment: "email_templates",
    label: "Plantillas de correo",
    milestone: "F.9i",
    done: true,
  },
  {
    segment: "installation",
    label: "Instalación",
    milestone: "F.9i",
    done: true,
  },
];

export function SettingsSidebar({ accountId }: { accountId: string }) {
  const pathname = usePathname();
  const baseHref = `/accounts/${accountId}/settings`;

  return (
    <nav
      aria-label="Ajustes"
      className="w-full shrink-0 border-b border-border bg-surface md:w-56 md:border-b-0 md:border-r"
    >
      <ul className="flex gap-1 overflow-x-auto p-2 md:flex-col md:gap-0.5 md:overflow-visible md:p-3">
        {SETTINGS_ITEMS.map((item) => {
          const href = `${baseHref}/${item.segment}`;
          const active = pathname.startsWith(href);
          if (!item.done) {
            return (
              <li key={item.segment} className="shrink-0">
                <span
                  className="flex cursor-not-allowed items-center justify-between gap-2 whitespace-nowrap rounded-md px-3 py-2 text-sm text-fg-muted opacity-60"
                  title={`Llega en ${item.milestone}`}
                >
                  {item.label}
                  <span className="rounded bg-surface-2 px-1 py-0.5 text-[9px] uppercase">
                    {item.milestone}
                  </span>
                </span>
              </li>
            );
          }
          return (
            <li key={item.segment} className="shrink-0">
              <Link
                href={href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "block whitespace-nowrap rounded-md px-3 py-2 text-sm font-medium",
                  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                  active
                    ? "bg-primary/10 text-primary"
                    : "text-fg hover:bg-surface-2",
                )}
              >
                {item.label}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
