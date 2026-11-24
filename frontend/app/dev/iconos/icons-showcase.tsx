"use client";

import { useTheme } from "next-themes";
import { useState } from "react";

import {
  type AppIconComponent,
  type IconAnimate,
  AgentIcon,
  BarsIcon,
  BookIcon,
  CalendarIcon,
  ClockIcon,
  HomeIcon,
  HourglassIcon,
  InboxIcon,
  InstagramNavIcon,
  MediaIcon,
  MegaphoneIcon,
  MessagesIcon,
  PeopleIcon,
  SidebarCollapseIcon,
  SidebarExpandIcon,
  StatsIcon,
  UnassignedIcon,
  WhatsappNavIcon,
} from "@/components/shell/app-icons";
import { cn } from "@/lib/utils";

type IconShowcaseEntry = {
  id: string;
  name: string;
  label: string;
  mode: Exclude<IconAnimate, "none">;
  where: string;
  motion: string;
  icon: AppIconComponent;
};

const ICON_ENTRIES: IconShowcaseEntry[] = [
  {
    id: "hourglass",
    name: "HourglassIcon",
    label: "Reloj de arena",
    mode: "loop",
    where: "Inicio (Ahora mismo · bucle) · Menú (hover)",
    motion: "La arena baja de arriba a abajo y al vaciarse el reloj gira 180°.",
    icon: HourglassIcon,
  },
  {
    id: "clock",
    name: "ClockIcon",
    label: "Reloj",
    mode: "loop",
    where: "Inicio (Ahora mismo · bucle) · Menú (hover)",
    motion: "El minutero gira visiblemente mientras el horario avanza lento.",
    icon: ClockIcon,
  },
  {
    id: "inbox",
    name: "InboxIcon",
    label: "Bandeja",
    mode: "hover",
    where: "Menú lateral e Inicio",
    motion: "Cae una carta dentro de la bandeja con leve rebote al aterrizar.",
    icon: InboxIcon,
  },
  {
    id: "people",
    name: "PeopleIcon",
    label: "CRM",
    mode: "hover",
    where: "Menú lateral",
    motion: "La persona principal entra caminando desde el costado izquierdo.",
    icon: PeopleIcon,
  },
  {
    id: "unassigned",
    name: "UnassignedIcon",
    label: "Sin asignar",
    mode: "hover",
    where: "Inicio (Ahora mismo)",
    motion: "La persona se inclina levemente y la «x» se sacude.",
    icon: UnassignedIcon,
  },
  {
    id: "calendar",
    name: "CalendarIcon",
    label: "Calendario",
    mode: "hover",
    where: "Menú lateral",
    motion: "Pasa una hoja desde el lomo superior y se marca un día.",
    icon: CalendarIcon,
  },
  {
    id: "agent",
    name: "AgentIcon",
    label: "Agente",
    mode: "hover",
    where: "Menú lateral",
    motion: "La estrella pulsa y las chispas titilan y se encienden.",
    icon: AgentIcon,
  },
  {
    id: "stats",
    name: "StatsIcon",
    label: "Estadísticas",
    mode: "hover",
    where: "Menú lateral",
    motion: "La línea de tendencia y su relleno suben desde el origen.",
    icon: StatsIcon,
  },
  {
    id: "bars",
    name: "BarsIcon",
    label: "Reportes",
    mode: "hover",
    where: "Menú lateral e Inicio",
    motion: "Las tres barras suben en cascada desde la base.",
    icon: BarsIcon,
  },
  {
    id: "media",
    name: "MediaIcon",
    label: "Medios",
    mode: "hover",
    where: "Menú lateral",
    motion: "La montaña sube y el sol asoma dentro del marco.",
    icon: MediaIcon,
  },
  {
    id: "book",
    name: "BookIcon",
    label: "Centro de ayuda",
    mode: "hover",
    where: "Menú lateral",
    motion: "Las dos páginas se abren desde el lomo central.",
    icon: BookIcon,
  },
  {
    id: "megaphone",
    name: "MegaphoneIcon",
    label: "Campañas",
    mode: "hover",
    where: "Menú lateral e Inicio",
    motion: "El megáfono se inclina y emite ondas de sonido hacia afuera.",
    icon: MegaphoneIcon,
  },
  {
    id: "messages",
    name: "MessagesIcon",
    label: "Conversaciones",
    mode: "hover",
    where: "Inicio (Accesos rápidos)",
    motion: "Aparecen y rebotan los tres puntitos de «escribiendo».",
    icon: MessagesIcon,
  },
  {
    id: "home",
    name: "HomeIcon",
    label: "Inicio",
    mode: "hover",
    where: "Menú lateral",
    motion: "Se enciende la puerta y salen dos volutas suaves de humo.",
    icon: HomeIcon,
  },
  {
    id: "instagram",
    name: "InstagramNavIcon",
    label: "Instagram",
    mode: "hover",
    where: "Menú lateral e Inicio",
    motion: "Pulso leve sobre su centro conservando el trazo monocromo.",
    icon: InstagramNavIcon,
  },
  {
    id: "whatsapp",
    name: "WhatsappNavIcon",
    label: "WhatsApp",
    mode: "hover",
    where: "Menú lateral",
    motion: "Pulso leve sobre su centro conservando el trazo monocromo.",
    icon: WhatsappNavIcon,
  },
  {
    id: "sidebar-collapse",
    name: "SidebarCollapseIcon",
    label: "Plegar menú",
    mode: "hover",
    where: "Barra lateral",
    motion: "La flecha empuja a la izquierda y el panel lateral se angosta.",
    icon: SidebarCollapseIcon,
  },
  {
    id: "sidebar-expand",
    name: "SidebarExpandIcon",
    label: "Desplegar menú",
    mode: "hover",
    where: "Barra lateral",
    motion: "La flecha empuja a la derecha y el panel lateral se ensancha.",
    icon: SidebarExpandIcon,
  },
];

function ShowcaseCard({
  entry,
  forceLoop,
}: {
  entry: IconShowcaseEntry;
  forceLoop: boolean;
}) {
  const Icon = entry.icon;
  const effectiveMode: IconAnimate =
    forceLoop && entry.mode === "hover" ? "loop" : entry.mode;

  return (
    <div
      tabIndex={0}
      data-showcase-icon={entry.id}
      className="group glass-card glass-card-interactive flex flex-col justify-between gap-4 rounded-md p-4 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-neon"
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="truncate text-sm font-medium text-fg">{entry.label}</p>
          <p className="truncate font-mono text-xs text-fg-muted">{entry.name}</p>
        </div>
        <span
          className={cn(
            "shrink-0 rounded-sm border px-2 py-0.5 text-[11px] font-medium uppercase tracking-[0.06em]",
            entry.mode === "loop"
              ? "border-neon bg-focused text-lit"
              : "border-glass bg-surface-2 text-fg-muted",
          )}
        >
          {entry.mode === "loop" ? "Bucle" : "Hover"}
        </span>
      </div>

      <div className="flex items-end justify-around rounded-control border border-glass bg-field px-4 py-5 text-fg-muted transition-colors group-hover:text-lit group-focus-visible:text-lit">
        <div className="flex flex-col items-center gap-2">
          <div className="flex h-12 items-center justify-center">
            <Icon className="h-6 w-6" animate={effectiveMode} aria-hidden />
          </div>
          <span className="font-numeric text-[11px] text-fg-muted">24 px</span>
        </div>
        <div className="h-10 w-px bg-glass" aria-hidden />
        <div className="flex flex-col items-center gap-2">
          <div className="flex h-12 items-center justify-center">
            <Icon className="h-12 w-12" animate={effectiveMode} aria-hidden />
          </div>
          <span className="font-numeric text-[11px] text-fg-muted">48 px</span>
        </div>
      </div>

      <div className="space-y-1">
        <p className="text-xs leading-relaxed text-fg">{entry.motion}</p>
        <p className="text-[11px] text-fg-muted">{entry.where}</p>
      </div>
    </div>
  );
}

export function IconsShowcase() {
  const { resolvedTheme, setTheme } = useTheme();
  const [forceLoop, setForceLoop] = useState(false);

  const loopEntries = ICON_ENTRIES.filter((entry) => entry.mode === "loop");
  const hoverEntries = ICON_ENTRIES.filter((entry) => entry.mode === "hover");
  const isDark = resolvedTheme !== "light";

  return (
    <main className="mx-auto min-h-dvh max-w-6xl space-y-8 p-6 sm:p-8">
      <header className="glass-panel flex flex-col gap-4 rounded-panel p-6 sm:flex-row sm:items-center sm:justify-between">
        <div className="space-y-1">
          <p className="text-[11px] font-medium uppercase tracking-[0.08em] text-fg-muted">
            Muestra de desarrollo · Solo dev
          </p>
          <h1 className="neon-sign text-[28px] leading-tight sm:text-[34px]">
            Íconos animados
          </h1>
          <p className="max-w-2xl text-sm text-fg-muted">
            Pasá el mouse o movete con Tab por cada tarjeta para probar las
            animaciones en modo hover. Los relojes corren en bucle continuo como
            en Inicio.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <div
            role="group"
            aria-label="Tema de la muestra"
            className="inline-flex rounded-control border border-glass bg-field p-1"
          >
            <button
              type="button"
              onClick={() => setTheme("dark")}
              aria-pressed={isDark}
              className={cn(
                "rounded-md px-3 py-1.5 text-xs font-medium transition-colors",
                isDark ? "bg-focused text-lit" : "text-fg-muted hover:text-fg",
              )}
            >
              Oscuro
            </button>
            <button
              type="button"
              onClick={() => setTheme("light")}
              aria-pressed={!isDark}
              className={cn(
                "rounded-md px-3 py-1.5 text-xs font-medium transition-colors",
                !isDark ? "bg-focused text-lit" : "text-fg-muted hover:text-fg",
              )}
            >
              Claro
            </button>
          </div>

          <button
            type="button"
            onClick={() => setForceLoop((prev) => !prev)}
            aria-pressed={forceLoop}
            className={cn(
              "rounded-control border px-3 py-2 text-xs font-medium transition-colors",
              forceLoop
                ? "border-neon bg-focused text-lit"
                : "border-glass bg-surface-2 text-fg hover:bg-hover-glass",
            )}
          >
            {forceLoop ? "Volver a hover" : "Reproducir todos en bucle"}
          </button>
        </div>
      </header>

      <section className="space-y-3">
        <div className="flex items-baseline justify-between gap-2">
          <h2 className="text-base font-medium text-fg">
            En bucle constante ({loopEntries.length})
          </h2>
          <p className="text-xs text-fg-muted">
            En Inicio («Ahora mismo») corren en bucle; en el menú lateral solo en hover.
          </p>
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          {loopEntries.map((entry) => (
            <ShowcaseCard
              key={entry.id}
              entry={entry}
              forceLoop={forceLoop}
            />
          ))}
        </div>
      </section>

      <section className="space-y-3">
        <div className="flex items-baseline justify-between gap-2">
          <h2 className="text-base font-medium text-fg">
            Al pasar el mouse o enfocar ({hoverEntries.length})
          </h2>
          <p className="text-xs text-fg-muted">
            Se disparan una vez (~0,6–0,9 s) desde la fila del menú o la tarjeta.
          </p>
        </div>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {hoverEntries.map((entry) => (
            <ShowcaseCard
              key={entry.id}
              entry={entry}
              forceLoop={forceLoop}
            />
          ))}
        </div>
      </section>

      <section className="glass-panel space-y-3 rounded-panel p-5">
        <div className="flex items-baseline justify-between gap-2">
          <h2 className="text-base font-medium text-fg">
            Vista previa en filas del menú (neón)
          </h2>
          <p className="text-xs text-fg-muted">
            El ítem activo («Inicio») queda quieto; los inactivos animan al pasar el mouse.
          </p>
        </div>
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
          <div className="group lit-tube neon-nav-lit flex h-11 items-center gap-3 rounded-control bg-focused px-[14px] font-display text-[16px] dark:bg-transparent">
            <HomeIcon className="h-5 w-5 shrink-0" animate="none" aria-hidden />
            Inicio (activo)
          </div>
          <button
            type="button"
            className="group neon-nav flex h-11 items-center gap-3 rounded-control px-[14px] text-left font-display text-[16px] hover:bg-hover-glass"
          >
            <InboxIcon className="h-5 w-5 shrink-0" animate="hover" aria-hidden />
            Bandeja
          </button>
          <button
            type="button"
            className="group neon-nav flex h-11 items-center gap-3 rounded-control px-[14px] text-left font-display text-[16px] hover:bg-hover-glass"
          >
            <PeopleIcon className="h-5 w-5 shrink-0" animate="hover" aria-hidden />
            CRM
          </button>
          <button
            type="button"
            className="group neon-nav flex h-11 items-center gap-3 rounded-control px-[14px] text-left font-display text-[16px] hover:bg-hover-glass"
          >
            <AgentIcon className="h-5 w-5 shrink-0" animate="hover" aria-hidden />
            Agente
          </button>
        </div>
      </section>
    </main>
  );
}
