"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { cn } from "@/lib/utils";

export type SettingsItem = {
  segment: string;
  label: string;
  milestone: string;
  done: boolean;
  group?: "general" | "publishing";
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
    label: "API y MCP",
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
  {
    segment: "signatures",
    label: "Firmas",
    milestone: "F.7",
    done: true,
    group: "publishing",
  },
  {
    segment: "sets",
    label: "Sets",
    milestone: "F.7",
    done: true,
    group: "publishing",
  },
  {
    segment: "autoposts",
    label: "Auto post",
    milestone: "F.7",
    done: true,
    group: "publishing",
  },
  {
    segment: "plugs",
    label: "Plugs",
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
  const href = `${baseHref}/${item.segment}`;
  const active = pathname === href || pathname.startsWith(`${href}/`);
  if (!item.done) {
    return (
      <li className="shrink-0">
        <span
          className="flex cursor-not-allowed items-center justify-between gap-2 whitespace-nowrap rounded-md px-3 py-2 text-sm text-fg-muted opacity-60"
          title={`Llega en ${item.milestone}`}
        >
          {item.label}
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
        {item.label}
      </Link>
    </li>
  );
}

export function SettingsSidebar({ accountId }: { accountId: string }) {
  const pathname = usePathname() ?? "";
  const baseHref = `/accounts/${accountId}/settings`;

  const generalItems = SETTINGS_ITEMS.filter((i) => i.group !== "publishing");
  const publishingItems = SETTINGS_ITEMS.filter(
    (i) => i.group === "publishing",
  );

  return (
    <nav
      aria-label="Ajustes"
      className="w-full shrink-0 border-b border-glass pb-2 md:w-56 md:border-b-0 md:border-r md:pb-0 md:pr-3"
    >
      <div className="hidden md:block">
        <p className="px-3 pb-1 text-[11px] font-semibold uppercase tracking-wider text-fg-muted">
          Publicación
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
          Cuenta y bandeja
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
