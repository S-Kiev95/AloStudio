"use client";

import { useMemo } from "react";

import { useAgents } from "@/lib/api/account";
import {
  type ReportRange,
  SUMMARY_SCOPES,
  type SummaryRow,
  type SummaryScope,
  useSummaryReport,
} from "@/lib/api/reports";
import { formatDuration } from "@/lib/time";
import { cn } from "@/lib/utils";
import { useT } from "@/lib/i18n/provider";

const COLUMNS = [
  { key: "conversations_count", label: "reports.cards.conversations", kind: "count" },
  { key: "resolved_conversations_count", label: "reports.table.resolved", kind: "count" },
  { key: "avg_resolution_time", label: "reports.cards.resolution", kind: "duration" },
  {
    key: "avg_first_response_time",
    label: "reports.table.firstResponse",
    kind: "duration",
  },
  { key: "avg_reply_time", label: "reports.cards.reply", kind: "duration" },
] as const;

/** Spend columns, appended only for ads whose figures have been synced. */
const MONEY_COLUMNS = [
  { key: "spend", label: "reports.table.spend" },
  { key: "cost_per_conversation", label: "reports.table.costPerConversation" },
  { key: "cost_per_resolution", label: "reports.table.costPerResolved" },
] as const;

function money(value: number | null | undefined, currency?: string | null) {
  // A null cost is a real state — spend exists but nothing was resolved yet,
  // so there is no per-result figure to divide into.
  if (value == null) return "—";
  const n = value.toLocaleString("es-AR", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
  return currency ? `${n} ${currency}` : n;
}

export function SummaryTable({
  accountId,
  scope,
  range,
}: {
  accountId: string;
  scope: SummaryScope;
  range: ReportRange;
}) {
  const t = useT();
  const query = useSummaryReport(accountId, scope, range);
  // Agent rows arrive without a name (just the user id) — resolve from
  // the agents list. Other scopes carry their own name so this stays idle.
  const agents = useAgents(accountId);
  const agentNames = useMemo(() => {
    const m = new Map<number, string>();
    for (const a of agents.data ?? []) m.set(a.id, a.name);
    return m;
  }, [agents.data]);

  const entityLabel =
    SUMMARY_SCOPES.find((s) => s.key === scope)?.entityLabel ?? t("reports.table.entity");

  const rows = useMemo(() => {
    const nameOf = (r: SummaryRow) =>
      r.name ?? agentNames.get(r.id) ?? `#${r.id}`;
    return [...(query.data ?? [])].sort(
      (a, b) =>
        b.conversations_count - a.conversations_count ||
        nameOf(a).localeCompare(nameOf(b)),
    );
  }, [query.data, agentNames]);

  if (query.isLoading) {
    return (
      <p className="py-10 text-center text-sm text-fg-muted">{t("common.loading")}</p>
    );
  }
  if (query.isError) {
    return (
      <p role="alert" className="py-10 text-center text-sm text-danger">
        {t("reports.table.loadFailed")}
      </p>
    );
  }
  if (rows.length === 0) {
    return (
      <p className="py-10 text-center text-sm text-fg-muted">
        {t("reports.table.noData")}
      </p>
    );
  }

  const nameOf = (r: SummaryRow) =>
    r.name ?? agentNames.get(r.id) ?? `#${r.id}`;

  // Absent spend means the Marketing API was never connected, which is not
  // the same as having spent nothing — so the columns disappear entirely
  // rather than showing a column of zeros that reads as "this ad was free".
  const hasSpend = rows.some((r) => r.spend != null);

  return (
    <div className="overflow-x-auto rounded-md border border-glass">
      <table className="w-full text-sm">
        <thead className="bg-surface-2">
          <tr className="border-b border-glass text-left">
            <th className="px-3 py-2.5 text-[11px] font-medium uppercase tracking-[0.08em] text-fg-muted">
              {entityLabel}
            </th>
            {COLUMNS.map((c) => (
              <th
                key={c.key}
                className="px-3 py-2.5 text-right text-[11px] font-medium uppercase tracking-[0.08em] text-fg-muted"
              >
                {t(c.label)}
              </th>
            ))}
            {hasSpend
              ? MONEY_COLUMNS.map((c) => (
                  <th
                    key={c.key}
                    className="px-3 py-2.5 text-right text-[11px] font-medium uppercase tracking-[0.08em] text-table-focused"
                  >
                    {t(c.label)}
                  </th>
                ))
              : null}
          </tr>
        </thead>
        <tbody className="divide-y divide-glass">
          {rows.map((row) => (
            <tr key={row.id} className="transition-colors hover:bg-hover-glass">
              <td className="max-w-[12rem] truncate px-3 py-2.5 font-medium text-fg">
                {nameOf(row)}
              </td>
              {COLUMNS.map((c) => {
                const v = row[c.key];
                const display =
                  c.kind === "duration"
                    ? formatDuration(v)
                    : v.toLocaleString();
                return (
                  <td
                    key={c.key}
                    className={cn(
                      "px-3 py-2.5 text-right font-numeric tabular-nums",
                      v === 0 ? "text-fg-muted" : "text-fg",
                    )}
                  >
                    {display}
                  </td>
                );
              })}
              {hasSpend
                ? MONEY_COLUMNS.map((c) => (
                    <td
                      key={c.key}
                      className="px-3 py-2.5 text-right font-numeric tabular-nums text-fg"
                    >
                      {money(row[c.key], row.currency)}
                    </td>
                  ))
                : null}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
