"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  type CampaignAnalytics,
  useCampaignAnalytics,
} from "@/lib/api/campaigns";
import { useIntlTag, useT } from "@/lib/i18n/provider";
import type { MessageKey } from "@/lib/i18n/translate";

const DELIVERY_LABELS: {
  key: keyof CampaignAnalytics["delivery"];
  label: MessageKey;
}[] = [
  { key: "sent", label: "campaigns.analytics.sent" },
  { key: "delivered", label: "campaigns.analytics.delivered" },
  { key: "read", label: "campaigns.analytics.read" },
  { key: "failed", label: "campaigns.analytics.failed" },
];

export function CampaignAnalyticsPanel({
  accountId,
  displayId,
}: {
  accountId: string;
  displayId: number;
}) {
  const t = useT();
  const { data, isLoading, isError } = useCampaignAnalytics(
    accountId,
    displayId,
  );

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("campaigns.analytics.delivery")}</CardTitle>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <p className="text-sm text-fg-muted">{t("reports.loadingMetrics")}</p>
        ) : isError || !data ? (
          <p role="alert" className="text-sm text-danger">
            {t("reports.metricsFailed")}
          </p>
        ) : (
          <div className="space-y-4">
            <div className="grid grid-cols-3 gap-3">
              <Metric label={t("campaigns.analytics.audience")} value={data.audience_count} />
              <Metric label={t("overview.conversations")} value={data.conversations_count} />
              <Metric label={t("campaigns.analytics.messages")} value={data.messages_count} />
            </div>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              {DELIVERY_LABELS.map((d) => (
                <Metric
                  key={d.key}
                  label={t(d.label)}
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
  const intlTag = useIntlTag();
  return (
    <div className="rounded-lg border border-border bg-surface p-3">
      <p className="text-xs font-medium uppercase tracking-wide text-fg-muted">
        {label}
      </p>
      <p className="mt-1 text-2xl font-semibold text-fg">
        {value.toLocaleString(intlTag)}
      </p>
    </div>
  );
}
