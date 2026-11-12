"use client";

import { ArrowDown, ArrowUp } from "lucide-react";

import { Card } from "@/components/ui/card";
import type { ReportSummary, ReportSummaryWithPrev } from "@/lib/api/reports";
import { formatDuration } from "@/lib/time";
import { cn } from "@/lib/utils";
import { useT } from "@/lib/i18n/provider";
import type { MessageKey } from "@/lib/i18n/translate";

type CardDef = {
  key: keyof ReportSummary;
  label: MessageKey;
  kind: "count" | "duration";
  lowerIsBetter?: boolean;
};

const CARDS: CardDef[] = [
  { key: "conversations_count", label: "reports.cards.conversations", kind: "count" },
  { key: "incoming_messages_count", label: "reports.cards.incoming", kind: "count" },
  { key: "outgoing_messages_count", label: "reports.cards.outgoing", kind: "count" },
  { key: "resolutions_count", label: "reports.cards.resolutions", kind: "count" },
  {
    key: "avg_first_response_time",
    label: "reports.cards.firstResponse",
    kind: "duration",
    lowerIsBetter: true,
  },
  {
    key: "avg_resolution_time",
    label: "reports.cards.resolution",
    kind: "duration",
    lowerIsBetter: true,
  },
  {
    key: "reply_time",
    label: "reports.cards.reply",
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
  const t = useT();
  const value =
    def.kind === "duration"
      ? formatDuration(current)
      : current.toLocaleString();

  const pct =
    previous > 0 ? ((current - previous) / previous) * 100 : null;

  return (
    <Card className="p-4">
      <p className="text-xs font-medium uppercase tracking-wide text-fg-muted">
        {t(def.label)}
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
  const t = useT();
  if (pct === null || !Number.isFinite(pct)) {
    return <p className="mt-1 text-xs text-fg-muted">{t("reports.cards.noPrevious")}</p>;
  }
  if (Math.round(pct) === 0) {
    return <p className="mt-1 text-xs text-fg-muted">{t("reports.cards.noChange")}</p>;
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
      <span className="font-normal text-fg-muted">{t("reports.cards.vsPrevious")}</span>
    </p>
  );
}
