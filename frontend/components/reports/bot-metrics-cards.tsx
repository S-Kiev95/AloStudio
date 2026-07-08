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
          <p className="text-xs font-medium uppercase tracking-wide text-fg-muted">
            {c.label}
          </p>
          <p className="mt-1 text-2xl font-semibold text-fg">
            {data[c.key].toLocaleString()}
            {c.suffix ?? ""}
          </p>
        </Card>
      ))}
    </div>
  );
}
