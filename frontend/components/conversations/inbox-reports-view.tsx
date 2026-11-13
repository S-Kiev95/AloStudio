"use client";

import { ArrowRight } from "lucide-react";
import Link from "next/link";
import { useMemo } from "react";

import { MetricChart } from "@/components/reports/metric-chart";
import { Avatar } from "@/components/ui/avatar";
import { buttonVariants } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { useAgents } from "@/lib/api/account";
import { useContacts } from "@/lib/api/contacts";
import {
  rangeForDays,
  type TimeseriesPoint,
  useLiveMetrics,
  useReportSummary,
  useReportTimeseries,
} from "@/lib/api/reports";
import { cn } from "@/lib/utils";
import { useIntlTag, useT } from "@/lib/i18n/provider";
import type { MessageKey } from "@/lib/i18n/translate";

const AVAILABILITY_CHIP: Record<string, { label: MessageKey; className: string }> = {
  online: {
    label: "conversations.reports.availability.online",
    className: "border border-success bg-surface-2 text-success",
  },
  busy: {
    label: "conversations.reports.availability.busy",
    className: "border border-warning bg-surface-2 text-warning",
  },
  offline: {
    label: "conversations.reports.availability.offline",
    className: "border border-glass bg-surface-2 text-fg-muted",
  },
};

function StatCard({
  label,
  value,
  loading,
}: {
  label: string;
  value: string;
  loading?: boolean;
}) {
  return (
    <Card className="p-4">
      <p className="text-xs text-fg-muted">{label}</p>
      <p className="mt-2 font-numeric text-2xl font-semibold leading-none tabular-nums text-fg">
        {loading ? "—" : value}
      </p>
    </Card>
  );
}

export function InboxReportsView({ accountId }: { accountId: string }) {
  const intlTag = useIntlTag();
  const t = useT();
  const range = useMemo(() => rangeForDays(7), []);
  const live = useLiveMetrics(accountId);
  const summary = useReportSummary(accountId, range);
  const incomingSeries = useReportTimeseries(
    accountId,
    "incoming_messages_count",
    range,
  );
  const outgoingSeries = useReportTimeseries(
    accountId,
    "outgoing_messages_count",
    range,
  );
  const contacts = useContacts(accountId, 1);
  const agents = useAgents(accountId);

  const messagesSeries = useMemo<TimeseriesPoint[]>(() => {
    const inc = incomingSeries.data ?? [];
    const out = outgoingSeries.data ?? [];
    if (inc.length === 0 && out.length === 0) return [];
    const byTs = new Map<number, number>();
    for (const p of inc) {
      byTs.set(p.timestamp, (byTs.get(p.timestamp) ?? 0) + p.value);
    }
    for (const p of out) {
      byTs.set(p.timestamp, (byTs.get(p.timestamp) ?? 0) + p.value);
    }
    return [...byTs.entries()]
      .sort(([a], [b]) => a - b)
      .map(([timestamp, value]) => ({ timestamp, value }));
  }, [incomingSeries.data, outgoingSeries.data]);

  const messagesToday =
    messagesSeries.length > 0
      ? messagesSeries[messagesSeries.length - 1].value
      : 0;

  const agentList = agents.data ?? [];
  const onlineAgents = agentList.filter(
    (a) => a.availability_status === "online",
  ).length;

  const seriesLoading = incomingSeries.isLoading || outgoingSeries.isLoading;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-base font-medium text-fg">
            {t("conversations.reports.title")}
          </h2>
          <p className="text-xs text-fg-muted">
            {t("conversations.reports.subtitle")}
          </p>
        </div>
        <Link
          href={`/accounts/${accountId}/reports`}
          className={buttonVariants({ variant: "secondary", size: "sm" })}
        >
          {t("conversations.reports.seeFull")}
          <ArrowRight className="h-4 w-4" aria-hidden />
        </Link>
      </div>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <StatCard
          label={t("conversations.reports.open")}
          value={(live.data?.open ?? 0).toLocaleString(intlTag)}
          loading={live.isLoading}
        />
        <StatCard
          label={t("conversations.reports.resolved")}
          value={(summary.data?.resolutions_count ?? 0).toLocaleString(intlTag)}
          loading={summary.isLoading}
        />
        <StatCard
          label={t("conversations.reports.pending")}
          value={(live.data?.pending ?? 0).toLocaleString(intlTag)}
          loading={live.isLoading}
        />
        <StatCard
          label={t("conversations.reports.messagesToday")}
          value={messagesToday.toLocaleString(intlTag)}
          loading={seriesLoading}
        />
        <StatCard
          label={t("conversations.reports.contacts")}
          value={(contacts.data?.meta.count ?? 0).toLocaleString(intlTag)}
          loading={contacts.isLoading}
        />
        <StatCard
          label={t("conversations.reports.agentsOnline")}
          value={`${onlineAgents}/${agentList.length}`}
          loading={agents.isLoading}
        />
      </div>

      <Card className="p-5">
        <div className="mb-4 flex items-center justify-between gap-2">
          <h3 className="text-sm font-medium text-fg">
            {t("conversations.reports.messages7d")}
          </h3>
          <span className="font-numeric text-sm font-medium tabular-nums text-fg-muted">
            {seriesLoading
              ? "—"
              : messagesSeries
                  .reduce((acc, p) => acc + p.value, 0)
                  .toLocaleString(intlTag)}
          </span>
        </div>
        {seriesLoading ? (
          <div className="h-48 animate-pulse rounded-md bg-surface-2" />
        ) : (
          <MetricChart
            data={messagesSeries}
            formatValue={(v) => v.toLocaleString(intlTag)}
          />
        )}
      </Card>

      <Card className="p-5">
        <h3 className="mb-3 text-sm font-medium text-fg">{t("conversations.reports.agents")}</h3>
        {agents.isLoading ? (
          <p className="text-sm text-fg-muted">{t("conversations.reports.loadingAgents")}</p>
        ) : agentList.length === 0 ? (
          <p className="text-sm text-fg-muted">{t("conversations.reports.noAgents")}</p>
        ) : (
          <ul className="divide-y divide-glass">
            {agentList.map((agent) => {
              const chip =
                AVAILABILITY_CHIP[agent.availability_status ?? "offline"] ??
                AVAILABILITY_CHIP.offline;
              return (
                <li
                  key={agent.id}
                  className="flex items-center gap-3 py-2.5 first:pt-0 last:pb-0"
                >
                  <Avatar name={agent.name} size="sm" />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium text-fg">
                      {agent.name}
                    </p>
                    {agent.email ? (
                      <p className="truncate text-xs text-fg-muted">
                        {agent.email}
                      </p>
                    ) : null}
                  </div>
                  <span
                    className={cn(
                      "shrink-0 rounded-pill px-2.5 py-0.5 text-xs font-medium",
                      chip.className,
                    )}
                  >
                    {t(chip.label)}
                  </span>
                </li>
              );
            })}
          </ul>
        )}
      </Card>
    </div>
  );
}
