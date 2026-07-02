"use client";

import { Download } from "lucide-react";
import { useMemo, useState } from "react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  type MetricKey,
  SUMMARY_SCOPES,
  type SummaryScope,
  TIMESERIES_METRICS,
  rangeForDays,
  summaryExportUrl,
  useLiveMetrics,
  useReportSummary,
  useReportTimeseries,
} from "@/lib/api/reports";
import { formatDuration } from "@/lib/time";
import { cn } from "@/lib/utils";

import { MetricChart } from "./metric-chart";
import { SummaryCards } from "./summary-cards";
import { SummaryTable } from "./summary-table";

const RANGES = [
  { days: 7, label: "7 días" },
  { days: 30, label: "30 días" },
  { days: 90, label: "90 días" },
] as const;

const LIVE_CARDS = [
  { key: "open", label: "Abiertas" },
  { key: "unattended", label: "Sin atender" },
  { key: "unassigned", label: "Sin asignar" },
  { key: "pending", label: "Pendientes" },
] as const;

export function ReportsView({ accountId }: { accountId: string }) {
  const [days, setDays] = useState<number>(30);
  const [metric, setMetric] = useState<MetricKey>("conversations_count");
  const [scope, setScope] = useState<SummaryScope>("agent");
  const range = useMemo(() => rangeForDays(days), [days]);

  const live = useLiveMetrics(accountId);
  const summary = useReportSummary(accountId, range);
  const series = useReportTimeseries(accountId, metric, range);

  const isAvg =
    TIMESERIES_METRICS.find((m) => m.key === metric)?.kind === "avg";
  const formatValue = (v: number) =>
    isAvg ? formatDuration(v) : v.toLocaleString();

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-xl font-semibold text-fg">Reportes</h2>
        <div className="flex gap-2">
          {RANGES.map((r) => (
            <button
              key={r.days}
              type="button"
              onClick={() => setDays(r.days)}
              aria-pressed={days === r.days}
              className={cn(
                "rounded-md px-3 py-1.5 text-sm font-medium",
                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                days === r.days
                  ? "bg-surface-2 font-semibold text-fg"
                  : "border border-border bg-surface text-fg hover:bg-surface-2",
              )}
            >
              {r.label}
            </button>
          ))}
        </div>
      </div>

      {/* Live snapshot */}
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {LIVE_CARDS.map((c) => (
          <Card key={c.key} className="p-4">
            <p className="text-xs font-medium uppercase tracking-wide text-fg-muted">
              {c.label}
            </p>
            <p className="mt-1 text-2xl font-semibold text-fg">
              {live.isLoading ? "…" : (live.data?.[c.key] ?? 0).toLocaleString()}
            </p>
          </Card>
        ))}
      </div>

      {/* Summary cards */}
      {summary.isLoading ? (
        <p className="text-sm text-fg-muted">Cargando métricas…</p>
      ) : summary.isError ? (
        <p role="alert" className="text-sm text-danger">
          No se pudieron cargar las métricas.
        </p>
      ) : summary.data ? (
        <SummaryCards data={summary.data} />
      ) : null}

      {/* Timeseries chart */}
      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <CardTitle>Evolución</CardTitle>
            <select
              aria-label="Métrica"
              value={metric}
              onChange={(e) => setMetric(e.target.value as MetricKey)}
              className="h-9 rounded-md border border-border bg-surface px-2 text-sm text-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              {TIMESERIES_METRICS.map((m) => (
                <option key={m.key} value={m.key}>
                  {m.label}
                </option>
              ))}
            </select>
          </div>
        </CardHeader>
        <CardContent>
          {series.isLoading ? (
            <p className="py-12 text-center text-sm text-fg-muted">Cargando…</p>
          ) : series.isError ? (
            <p role="alert" className="py-12 text-center text-sm text-danger">
              No se pudo cargar la serie.
            </p>
          ) : (
            <MetricChart data={series.data ?? []} formatValue={formatValue} />
          )}
        </CardContent>
      </Card>

      {/* Per-entity breakdown */}
      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <CardTitle>Desglose</CardTitle>
            <div className="flex flex-wrap items-center gap-2">
              {SUMMARY_SCOPES.map((s) => (
                <button
                  key={s.key}
                  type="button"
                  onClick={() => setScope(s.key)}
                  aria-pressed={scope === s.key}
                  className={cn(
                    "rounded-md px-3 py-1.5 text-sm font-medium",
                    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                    scope === s.key
                      ? "bg-surface-2 font-semibold text-fg"
                      : "border border-border bg-surface text-fg hover:bg-surface-2",
                  )}
                >
                  {s.label}
                </button>
              ))}
              <span
                className="mx-1 hidden h-6 w-px bg-border sm:block"
                aria-hidden
              />
              <a
                href={summaryExportUrl(accountId, scope, range, "csv")}
                download
                className="inline-flex items-center gap-1.5 rounded-md border border-border bg-surface px-3 py-1.5 text-sm font-medium text-fg hover:bg-surface-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                <Download className="h-4 w-4" aria-hidden />
                CSV
              </a>
              <a
                href={summaryExportUrl(accountId, scope, range, "xlsx")}
                download
                className="inline-flex items-center gap-1.5 rounded-md border border-border bg-surface px-3 py-1.5 text-sm font-medium text-fg hover:bg-surface-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                <Download className="h-4 w-4" aria-hidden />
                Excel
              </a>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <SummaryTable accountId={accountId} scope={scope} range={range} />
        </CardContent>
      </Card>
    </div>
  );
}
