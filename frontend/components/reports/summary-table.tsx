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

const COLUMNS = [
  { key: "conversations_count", label: "Conversaciones", kind: "count" },
  { key: "resolved_conversations_count", label: "Resueltas", kind: "count" },
  { key: "avg_resolution_time", label: "Resolución (prom.)", kind: "duration" },
  {
    key: "avg_first_response_time",
    label: "1ª respuesta (prom.)",
    kind: "duration",
  },
  { key: "avg_reply_time", label: "Respuesta (prom.)", kind: "duration" },
] as const;

export function SummaryTable({
  accountId,
  scope,
  range,
}: {
  accountId: string;
  scope: SummaryScope;
  range: ReportRange;
}) {
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
    SUMMARY_SCOPES.find((s) => s.key === scope)?.entityLabel ?? "Entidad";

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
      <p className="py-10 text-center text-sm text-fg-muted">Cargando…</p>
    );
  }
  if (query.isError) {
    return (
      <p role="alert" className="py-10 text-center text-sm text-danger">
        No se pudo cargar el desglose.
      </p>
    );
  }
  if (rows.length === 0) {
    return (
      <p className="py-10 text-center text-sm text-fg-muted">
        No hay datos para este período.
      </p>
    );
  }

  const nameOf = (r: SummaryRow) =>
    r.name ?? agentNames.get(r.id) ?? `#${r.id}`;

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border text-left">
            <th className="px-3 py-2 text-xs font-medium uppercase tracking-wide text-fg-muted">
              {entityLabel}
            </th>
            {COLUMNS.map((c) => (
              <th
                key={c.key}
                className="px-3 py-2 text-right text-xs font-medium uppercase tracking-wide text-fg-muted"
              >
                {c.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {rows.map((row) => (
            <tr key={row.id} className="hover:bg-surface-2">
              <td className="max-w-[12rem] truncate px-3 py-2 font-medium text-fg">
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
                      "px-3 py-2 text-right font-numeric tabular-nums",
                      v === 0 ? "text-fg-muted" : "text-fg",
                    )}
                  >
                    {display}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
