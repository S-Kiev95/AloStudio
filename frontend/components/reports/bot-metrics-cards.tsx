"use client";

import { Card } from "@/components/ui/card";
import type { BotMetrics } from "@/lib/api/reports";
import type { MessageKey } from "@/lib/i18n/translate";
import { useIntlTag, useT } from "@/lib/i18n/provider";

const CARDS: {
  key: keyof BotMetrics;
  label: MessageKey;
  suffix?: string;
}[] = [
  { key: "conversation_count", label: "reports.bot.conversations" },
  { key: "message_count", label: "reports.bot.messages" },
  { key: "resolution_rate", label: "reports.bot.resolutionRate", suffix: "%" },
  { key: "handoff_rate", label: "reports.bot.handoffRate", suffix: "%" },
];

export function BotMetricsCards({ data }: { data: BotMetrics }) {
  const intlTag = useIntlTag();
  const t = useT();
  return (
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
      {CARDS.map((c) => (
        <Card key={c.key} className="p-4">
          <p className="text-[11px] font-medium uppercase tracking-[0.08em] text-fg-muted">
            {t(c.label)}
          </p>
          <p className="mt-1 font-numeric text-2xl font-semibold tabular-nums text-fg">
            {data[c.key].toLocaleString(intlTag)}
            {c.suffix ?? ""}
          </p>
        </Card>
      ))}
    </div>
  );
}
