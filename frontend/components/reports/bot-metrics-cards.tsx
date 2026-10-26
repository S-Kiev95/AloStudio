"use client";

import { Card } from "@/components/ui/card";
import type { BotMetrics } from "@/lib/api/reports";

const CARDS: {
  key: keyof BotMetrics;
  label: string;
  suffix?: string;
}[] = [
  { key: "conversation_count", label: "Conversaciones con bot" },
  { key: "message_count", label: "Mensajes del bot" },
  { key: "resolution_rate", label: "Tasa de resolución", suffix: "%" },
  { key: "handoff_rate", label: "Tasa de derivación", suffix: "%" },
];

export function BotMetricsCards({ data }: { data: BotMetrics }) {
  return (
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
      {CARDS.map((c) => (
        <Card key={c.key} className="p-4">
          <p className="text-[11px] font-medium uppercase tracking-[0.08em] text-fg-muted">
            {c.label}
          </p>
          <p className="mt-1 font-numeric text-2xl font-semibold tabular-nums text-fg">
            {data[c.key].toLocaleString()}
            {c.suffix ?? ""}
          </p>
        </Card>
      ))}
    </div>
  );
}
