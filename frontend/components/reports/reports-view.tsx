"use client";

import { Download } from "lucide-react";
import { useMemo, useState } from "react";

import { PageHeader } from "@/components/shell/page-header";
import { buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { SegmentedControl } from "@/components/ui/segmented-control";
import { selectClassName } from "@/components/ui/select";
import {
  type MetricKey,
  SUMMARY_SCOPES,
  type SummaryScope,
  TIMESERIES_METRICS,
  rangeForDays,
  summaryExportUrl,
  useBotMetrics,
  useConversationTraffic,
  useLiveMetrics,
  useReportSummary,
  useReportTimeseries,
} from "@/lib/api/reports";
import { formatDuration } from "@/lib/time";

import { BotMetricsCards } from "./bot-metrics-cards";
import { MetricChart } from "./metric-chart";
import { SummaryCards } from "./summary-cards";
import { SummaryTable } from "./summary-table";
import { TrafficHeatmap } from "./traffic-heatmap";

const RANGES = [
  { value: 7, label: "7 días" },
  { value: 30, label: "30 días" },
  { value: 90, label: "90 días" },
] as const;

const LIVE_CARDS = [
  { key: "open", label: "Abiertas" },
  { key: "unattended", label: "Sin atender" },
  { key: "unassigned", label: "Sin asignar" },
  { key: "pending", label: "Pendientes" },
] as const;

const SCOPE_OPTIONS = SUMMARY_SCOPES.map((s) => ({
  value: s.key,
  label: s.label,
}));

export function ReportsView({ accountId }: { accountId: string }) {
  const [days, setDays] = useState<number>(30);
  const [metric, setMetric] = useState<MetricKey>("conversations_count");
  const [scope, setScope] = useState<SummaryScope>("agent");
  const range = useMemo(() => rangeForDays(days), [days]);

  const live = useLiveMetrics(accountId);
  const summary = useReportSummary(accountId, range);
  const series = useReportTimeseries(accountId, metric, range);
  const traffic = useConversationTraffic(accountId, range);
  const bot = useBotMetrics(accountId, range);

  const isAvg =
    TIMESERIES_METRICS.find((m) => m.key === metric)?.kind === "avg";
  const formatValue = (v: number) =>
    isAvg ? formatDuration(v) : v.toLocaleString();

  return (
    <div className="space-y-5">
      <PageHeader
        title="Reportes"
        actions={
          <SegmentedControl
            ariaLabel="Período"
            size="sm"
            value={days}
            onValueChange={setDays}
            options={RANGES}
          />
        }
      />

      {/* Live snapshot */}
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {LIVE_CARDS.map((c) => (
          <Card key={c.key} className="p-4">
            <p className="text-[11px] font-medium uppercase tracking-[0.08em] text-fg-muted">
              {c.label}
            </p>
            <p className="mt-1 font-numeric text-2xl font-semibold tabular-nums text-fg">
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
              className={selectClassName("sm")}
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

      {/* Conversation-traffic heatmap */}
      <Card>
        <CardHeader>
          <CardTitle>Tráfico de conversaciones</CardTitle>
        </CardHeader>
        <CardContent>
          {traffic.isLoading ? (
            <p className="py-8 text-center text-sm text-fg-muted">Cargando…</p>
          ) : traffic.isError ? (
            <p role="alert" className="py-8 text-center text-sm text-danger">
              No se pudo cargar el tráfico.
            </p>
          ) : (
            <TrafficHeatmap data={traffic.data?.data ?? []} />
          )}
        </CardContent>
      </Card>

      {/* Bot performance */}
      <Card>
        <CardHeader>
          <CardTitle>Rendimiento del bot</CardTitle>
        </CardHeader>
        <CardContent>
          {bot.isLoading ? (
            <p className="py-8 text-center text-sm text-fg-muted">Cargando…</p>
          ) : bot.isError ? (
            <p role="alert" className="py-8 text-center text-sm text-danger">
              No se pudieron cargar las métricas del bot.
            </p>
          ) : bot.data ? (
            <BotMetricsCards data={bot.data} />
          ) : null}
        </CardContent>
      </Card>

      {/* Per-entity breakdown */}
      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <CardTitle>Desglose</CardTitle>
            <div className="flex flex-wrap items-center gap-2">
              <SegmentedControl
                ariaLabel="Ámbito"
                size="sm"
                value={scope}
                onValueChange={setScope}
                options={SCOPE_OPTIONS}
              />
              <span
                className="mx-1 hidden h-6 w-px bg-glass sm:block"
                aria-hidden
              />
              <a
                href={summaryExportUrl(accountId, scope, range, "csv")}
                download
                className={buttonVariants({ variant: "simple", size: "sm" })}
              >
                <Download className="h-4 w-4" aria-hidden />
                CSV
              </a>
              <a
                href={summaryExportUrl(accountId, scope, range, "xlsx")}
                download
                className={buttonVariants({ variant: "simple", size: "sm" })}
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
