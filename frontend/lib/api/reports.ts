import { useQuery } from "@tanstack/react-query";

import { apiFetch } from "./fetcher";

/** Dashboard summary cards (mirrors V2::ReportBuilder#summary). */
export type ReportSummary = {
  conversations_count: number;
  incoming_messages_count: number;
  outgoing_messages_count: number;
  avg_first_response_time: number; // seconds
  avg_resolution_time: number; // seconds
  resolutions_count: number;
  reply_time: number; // seconds
};

export type ReportSummaryWithPrev = ReportSummary & {
  previous: ReportSummary;
};

/** Live current-state counters. unassigned/pending only present for account scope. */
export type LiveMetrics = {
  open: number;
  unattended: number;
  unassigned?: number;
  pending?: number;
};

export type TimeseriesPoint = {
  value: number;
  timestamp: number; // unix seconds (bucket start)
  count?: number; // present for avg metrics
};

export type ReportRange = { since: number; until: number };

/** All metrics the backend allow-lists for the timeseries endpoint. */
export const TIMESERIES_METRICS = [
  { key: "conversations_count", label: "Conversaciones", kind: "count" },
  { key: "incoming_messages_count", label: "Mensajes entrantes", kind: "count" },
  { key: "outgoing_messages_count", label: "Mensajes salientes", kind: "count" },
  { key: "resolutions_count", label: "Resoluciones", kind: "count" },
  { key: "avg_first_response_time", label: "Primera respuesta", kind: "avg" },
  { key: "avg_resolution_time", label: "Tiempo de resolución", kind: "avg" },
  { key: "reply_time", label: "Tiempo de respuesta", kind: "avg" },
] as const;

export type MetricKey = (typeof TIMESERIES_METRICS)[number]["key"];

function base(accountId: string): string {
  return `/api/v2/accounts/${accountId}`;
}

/** Build a [now-Ndays, now] window in unix seconds. */
export function rangeForDays(days: number): ReportRange {
  const until = Math.floor(Date.now() / 1000);
  return { since: until - days * 86_400, until };
}

export function useReportSummary(accountId: string, range: ReportRange) {
  return useQuery({
    queryKey: ["report-summary", accountId, range.since, range.until],
    queryFn: () => {
      const sp = new URLSearchParams({
        type: "account",
        since: String(range.since),
        until: String(range.until),
      });
      return apiFetch<ReportSummaryWithPrev>(
        `${base(accountId)}/reports/summary?${sp}`,
      );
    },
  });
}

export function useLiveMetrics(accountId: string) {
  return useQuery({
    queryKey: ["live-metrics", accountId],
    queryFn: () =>
      apiFetch<LiveMetrics>(
        `${base(accountId)}/live_reports/conversation_metrics`,
      ),
    refetchInterval: 30_000,
  });
}

// ---------------------------------------------------------------------------
// Per-entity summary reports (drill-down tables)
// ---------------------------------------------------------------------------
/** The four breakdown axes exposed by ``/summary_reports/{scope}``. */
export const SUMMARY_SCOPES = [
  { key: "agent", label: "Agentes", entityLabel: "Agente" },
  { key: "team", label: "Equipos", entityLabel: "Equipo" },
  { key: "inbox", label: "Bandejas", entityLabel: "Bandeja" },
  { key: "label", label: "Etiquetas", entityLabel: "Etiqueta" },
] as const;

export type SummaryScope = (typeof SUMMARY_SCOPES)[number]["key"];

/**
 * One row of a per-entity summary report. The agent builder emits only
 * `id` (the user id) with no `name`, so the caller resolves it from the
 * agents list; team/inbox/label rows carry their own `name`.
 */
export type SummaryRow = {
  id: number;
  name?: string;
  conversations_count: number;
  resolved_conversations_count: number;
  avg_resolution_time: number; // seconds
  avg_first_response_time: number; // seconds
  avg_reply_time: number; // seconds
};

/**
 * Same-origin BFF URL for downloading a per-entity summary as CSV/XLSX.
 * Used as an ``<a href download>`` target so the httpOnly auth cookie
 * rides along automatically (the proxy re-attaches devise headers).
 */
export function summaryExportUrl(
  accountId: string,
  scope: SummaryScope,
  range: ReportRange,
  format: "csv" | "xlsx",
): string {
  const apiBase = process.env.NEXT_PUBLIC_API_BASE ?? "/api/backend";
  const sp = new URLSearchParams({
    since: String(range.since),
    until: String(range.until),
    format,
  });
  return `${apiBase}${base(accountId)}/summary_reports/${scope}/export?${sp}`;
}

export function useSummaryReport(
  accountId: string,
  scope: SummaryScope,
  range: ReportRange,
) {
  return useQuery({
    queryKey: ["summary-report", accountId, scope, range.since, range.until],
    queryFn: () => {
      const sp = new URLSearchParams({
        since: String(range.since),
        until: String(range.until),
      });
      return apiFetch<SummaryRow[]>(
        `${base(accountId)}/summary_reports/${scope}?${sp}`,
      );
    },
  });
}

export function useReportTimeseries(
  accountId: string,
  metric: MetricKey,
  range: ReportRange,
) {
  // Backend expects timezone_offset in *hours east of UTC*.
  const offsetHours = -new Date().getTimezoneOffset() / 60;
  return useQuery({
    queryKey: ["report-timeseries", accountId, metric, range.since, range.until],
    queryFn: () => {
      const sp = new URLSearchParams({
        metric,
        type: "account",
        since: String(range.since),
        until: String(range.until),
        timezone_offset: String(offsetHours),
      });
      return apiFetch<TimeseriesPoint[]>(`${base(accountId)}/reports?${sp}`);
    },
  });
}

/** One date's 24 hourly conversation counts. */
export type TrafficRow = { date: string; hours: number[] };
export type TrafficReport = { timezone_offset: number; data: TrafficRow[] };

/** ``GET /reports/conversation_traffic`` — the (date × hour) heatmap grid. */
export function useConversationTraffic(
  accountId: string,
  range: ReportRange,
) {
  const offsetHours = -new Date().getTimezoneOffset() / 60;
  return useQuery({
    queryKey: [
      "conversation-traffic",
      accountId,
      range.since,
      range.until,
    ],
    queryFn: () => {
      const sp = new URLSearchParams({
        since: String(range.since),
        until: String(range.until),
        timezone_offset: String(offsetHours),
      });
      return apiFetch<TrafficReport>(
        `${base(accountId)}/reports/conversation_traffic?${sp}`,
      );
    },
  });
}

/** Bot-report numbers (mirrors V2::Reports::BotMetricsBuilder). Rates are
 * integer percentages. */
export type BotMetrics = {
  conversation_count: number;
  message_count: number;
  resolution_rate: number;
  handoff_rate: number;
};

/** ``GET /reports/bot_metrics`` — the four bot-report figures over the range. */
export function useBotMetrics(accountId: string, range: ReportRange) {
  return useQuery({
    queryKey: ["bot-metrics", accountId, range.since, range.until],
    queryFn: () => {
      const sp = new URLSearchParams({
        since: String(range.since),
        until: String(range.until),
      });
      return apiFetch<BotMetrics>(
        `${base(accountId)}/reports/bot_metrics?${sp}`,
      );
    },
  });
}
