"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  type CampaignAnalytics,
  useCampaignAnalytics,
} from "@/lib/api/campaigns";

const DELIVERY_LABELS: {
  key: keyof CampaignAnalytics["delivery"];
  label: string;
}[] = [
  { key: "sent", label: "Enviados" },
  { key: "delivered", label: "Entregados" },
  { key: "read", label: "Leídos" },
  { key: "failed", label: "Fallidos" },
];

export function CampaignAnalyticsPanel({
  accountId,
  displayId,
}: {
  accountId: string;
  displayId: number;
}) {
  const { data, isLoading, isError } = useCampaignAnalytics(
    accountId,
    displayId,
  );

  return (
    <Card>
      <CardHeader>
        <CardTitle>Entrega</CardTitle>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <p className="text-sm text-fg-muted">Cargando métricas…</p>
        ) : isError || !data ? (
          <p role="alert" className="text-sm text-danger">
            No se pudieron cargar las métricas.
          </p>
        ) : (
          <div className="space-y-4">
            <div className="grid grid-cols-3 gap-3">
              <Metric label="Audiencia" value={data.audience_count} />
              <Metric label="Conversaciones" value={data.conversations_count} />
              <Metric label="Mensajes" value={data.messages_count} />
            </div>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              {DELIVERY_LABELS.map((d) => (
                <Metric
                  key={d.key}
                  label={d.label}
                  value={data.delivery[d.key]}
                />
              ))}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-lg border border-border bg-surface p-3">
      <p className="text-xs font-medium uppercase tracking-wide text-fg-muted">
        {label}
      </p>
      <p className="mt-1 text-2xl font-semibold text-fg">
        {value.toLocaleString()}
      </p>
    </div>
  );
}
