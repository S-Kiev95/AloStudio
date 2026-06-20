"use client";

import { ArrowDown, ArrowUp } from "lucide-react";

import { Card } from "@/components/ui/card";
import type { ReportSummary, ReportSummaryWithPrev } from "@/lib/api/reports";
import { formatDuration } from "@/lib/time";
import { cn } from "@/lib/utils";

type CardDef = {
  key: keyof ReportSummary;
  label: string;
  kind: "count" | "duration";
  lowerIsBetter?: boolean;
};

const CARDS: CardDef[] = [
  { key: "conversations_count", label: "Conversaciones", kind: "count" },
  { key: "incoming_messages_count", label: "Mensajes entrantes", kind: "count" },
  { key: "outgoing_messages_count", label: "Mensajes salientes", kind: "count" },
  { key: "resolutions_count", label: "Resoluciones", kind: "count" },
  {
    key: "avg_first_response_time",
    label: "Primera respuesta (prom.)",
    kind: "duration",
    lowerIsBetter: true,
  },
  {
    key: "avg_resolution_time",
    label: "Resolución (prom.)",
    kind: "duration",
    lowerIsBetter: true,
  },
  {
    key: "reply_time",
    label: "Respuesta (prom.)",
    kind: "duration",
    lowerIsBetter: true,
  },
];

export function SummaryCards({ data }: { data: ReportSummaryWithPrev }) {
  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
      {CARDS.map((c) => (
        <SummaryCard
          key={c.key}
          def={c}
          current={data[c.key]}
          previous={data.previous[c.key]}
        />
      ))}
    </div>
  );
}

function SummaryCard({
  def,
  current,
  previous,
}: {
  def: CardDef;
  current: number;
  previous: number;
}) {
  const value =
    def.kind === "duration"
      ? formatDuration(current)
      : current.toLocaleString();

  const pct =
    previous > 0 ? ((current - previous) / previous) * 100 : null;

  return (
    <Card className="p-4">
      <p className="text-xs font-medium uppercase tracking-wide text-fg-muted">
        {def.label}
      </p>
      <p className="mt-1 font-numeric text-2xl font-semibold tabular-nums text-fg">{value}</p>
      <Delta pct={pct} lowerIsBetter={def.lowerIsBetter} />
    </Card>
  );
}

function Delta({
  pct,
  lowerIsBetter,
}: {
  pct: number | null;
  lowerIsBetter?: boolean;
}) {
  if (pct === null || !Number.isFinite(pct)) {
    return <p className="mt-1 text-xs text-fg-muted">sin período previo</p>;
  }
  if (Math.round(pct) === 0) {
    return <p className="mt-1 text-xs text-fg-muted">sin cambios</p>;
  }
  const up = pct > 0;
  const good = lowerIsBetter ? !up : up;
  const Icon = up ? ArrowUp : ArrowDown;
  return (
    <p
      className={cn(
        "mt-1 flex items-center gap-0.5 text-xs font-medium",
        good ? "text-success" : "text-danger",
      )}
    >
      <Icon className="h-3 w-3" aria-hidden />
      <span className="font-numeric tabular-nums">
        {Math.abs(Math.round(pct))}%
      </span>
      <span className="font-normal text-fg-muted">vs. período previo</span>
    </p>
  );
}
