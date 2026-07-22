"use client";

import Link from "next/link";
import {
  AlarmClock,
  ArrowRight,
  BarChart3,
  Hourglass,
  Inbox,
  Instagram,
  type LucideIcon,
  Megaphone,
  MessagesSquare,
  UserX,
} from "lucide-react";
import { useMemo } from "react";

import { MetricChart } from "@/components/reports/metric-chart";
import { SummaryCards } from "@/components/reports/summary-cards";
import { Card } from "@/components/ui/card";
import {
  type LiveMetrics,
  rangeForDays,
  useLiveMetrics,
  useReportSummary,
  useReportTimeseries,
} from "@/lib/api/reports";
import { cn } from "@/lib/utils";

/** Time-aware Spanish greeting so Inicio opens with a human note. */
function greeting(): string {
  const h = new Date().getHours();
  if (h < 6 || h >= 20) return "Buenas noches";
  if (h < 13) return "Buenos días";
  return "Buenas tardes";
}

type Tone = "info" | "warning" | "danger" | "muted";

/** The disciplined tint pattern (see instagram/state-badge) — a wash of the
 *  status colour behind its own icon, the one place Inicio spends colour. */
const TONE: Record<Tone, string> = {
  info: "bg-info/10 text-info",
  warning: "bg-warning/10 text-warning",
  danger: "bg-danger/10 text-danger",
  muted: "bg-surface-2 text-fg-muted",
};

const LIVE: {
  key: keyof LiveMetrics;
  label: string;
  icon: LucideIcon;
  tone: Tone;
}[] = [
  { key: "open", label: "Abiertas", icon: Inbox, tone: "info" },
  { key: "unattended", label: "Sin atender", icon: AlarmClock, tone: "warning" },
  { key: "unassigned", label: "Sin asignar", icon: UserX, tone: "danger" },
  { key: "pending", label: "Pendientes", icon: Hourglass, tone: "muted" },
];

const ACTIONS: {
  label: string;
  desc: string;
  icon: LucideIcon;
  segment: string;
}[] = [
  {
    label: "Conversaciones",
    desc: "Bandeja de entrada",
    icon: MessagesSquare,
    segment: "conversations",
  },
  {
    label: "Instagram",
    desc: "DMs, posts y comentarios",
    icon: Instagram,
    segment: "instagram",
  },
  {
    label: "Campañas",
    desc: "Envíos y plantillas",
    icon: Megaphone,
    segment: "campaigns",
  },
  {
    label: "Reportes",
    desc: "Métricas y exportes",
    icon: BarChart3,
    segment: "reports",
  },
];

function SectionLabel({ children }: { children: string }) {
  return (
    <p className="text-xs font-semibold uppercase tracking-wider text-fg-muted">
      {children}
    </p>
  );
}

function LiveCard({
  def,
  value,
  loading,
}: {
  def: (typeof LIVE)[number];
  value: number | undefined;
  loading: boolean;
}) {
  const Icon = def.icon;
  return (
    <Card className="flex items-center gap-3 p-4">
      <span
        className={cn(
          "grid h-11 w-11 shrink-0 place-items-center rounded-lg",
          TONE[def.tone],
        )}
      >
        <Icon className="h-5 w-5" aria-hidden />
      </span>
      <div className="min-w-0">
        <p className="font-numeric text-2xl font-semibold leading-none tabular-nums text-fg">
          {loading ? "—" : (value ?? 0).toLocaleString()}
        </p>
        <p className="mt-1.5 truncate text-xs text-fg-muted">{def.label}</p>
      </div>
    </Card>
  );
}

function ActionRow({
  accountId,
  action,
}: {
  accountId: string;
  action: (typeof ACTIONS)[number];
}) {
  const Icon = action.icon;
  return (
    <Link
      href={`/accounts/${accountId}/${action.segment}`}
      className="group flex items-center gap-3 rounded-lg border border-transparent px-2 py-2 transition-colors hover:border-border hover:bg-surface-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-surface"
    >
      <span className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-surface-2 text-fg-muted transition-colors group-hover:bg-surface-3 group-hover:text-fg">
        <Icon className="h-4 w-4" aria-hidden />
      </span>
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium text-fg">{action.label}</p>
        <p className="truncate text-xs text-fg-muted">{action.desc}</p>
      </div>
      <ArrowRight
        className="h-4 w-4 shrink-0 text-fg-muted opacity-0 transition-all group-hover:translate-x-0.5 group-hover:opacity-100"
        aria-hidden
      />
    </Link>
  );
}

/**
 * Account overview (Inicio) — the landing surface: live state, the 7-day KPI
 * set (reused from Reportes), a conversations chart, and quick links. All
 * client-side because the metrics are live queries.
 */
export function AccountOverview({ accountId }: { accountId: string }) {
  // Memoized so the window doesn't drift every render and thrash the queries.
  const range = useMemo(() => rangeForDays(7), []);
  const live = useLiveMetrics(accountId);
  const summary = useReportSummary(accountId, range);
  const series = useReportTimeseries(accountId, "conversations_count", range);

  return (
    <div className="mx-auto max-w-6xl space-y-8">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-fg sm:text-3xl">
            {greeting()}
          </h1>
          <p className="mt-1 text-sm text-fg-muted">
            Un vistazo a tu cuenta — estado actual y últimos 7 días.
          </p>
        </div>
        <Link
          href={`/accounts/${accountId}/reports`}
          className="inline-flex items-center gap-1.5 rounded-lg border border-border bg-surface px-3 py-2 text-sm font-medium text-fg shadow-sm transition-colors hover:bg-surface-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-bg"
        >
          Ver reportes
          <ArrowRight className="h-4 w-4" aria-hidden />
        </Link>
      </div>

      <section className="space-y-3">
        <SectionLabel>Ahora mismo</SectionLabel>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {LIVE.map((def) => (
            <LiveCard
              key={def.key}
              def={def}
              value={live.data?.[def.key]}
              loading={live.isLoading}
            />
          ))}
        </div>
      </section>

      <section className="space-y-3">
        <SectionLabel>Últimos 7 días</SectionLabel>
        {summary.isLoading ? (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <Card key={i} className="h-[92px] animate-pulse p-4" />
            ))}
          </div>
        ) : summary.data ? (
          <SummaryCards data={summary.data} />
        ) : (
          <Card className="p-4 text-sm text-fg-muted">
            No pudimos cargar las métricas del período.
          </Card>
        )}
      </section>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="p-5 lg:col-span-2">
          <div className="mb-4 flex items-start justify-between">
            <div>
              <p className="text-sm font-semibold text-fg">Conversaciones</p>
              <p className="text-xs text-fg-muted">Últimos 7 días</p>
            </div>
            <p className="font-numeric text-2xl font-semibold tabular-nums text-fg">
              {summary.data?.conversations_count?.toLocaleString() ?? "—"}
            </p>
          </div>
          {series.isLoading ? (
            <div className="h-48 animate-pulse rounded-lg bg-surface-2" />
          ) : (
            <MetricChart
              data={series.data ?? []}
              formatValue={(v) => v.toLocaleString()}
            />
          )}
        </Card>

        <Card className="p-5">
          <p className="mb-3 text-sm font-semibold text-fg">Accesos rápidos</p>
          <div className="flex flex-col gap-1">
            {ACTIONS.map((action) => (
              <ActionRow
                key={action.segment}
                accountId={accountId}
                action={action}
              />
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
}
