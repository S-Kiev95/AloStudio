"use client";

import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { useContext, useEffect, useMemo } from "react";

import { MetricChart } from "@/components/reports/metric-chart";
import { SummaryCards } from "@/components/reports/summary-cards";
import {
  BarsIcon,
  ClockIcon,
  HourglassIcon,
  InboxIcon,
  InstagramNavIcon,
  MegaphoneIcon,
  MessagesIcon,
  UnassignedIcon,
} from "@/components/shell/app-icons";
import { PageSignContext } from "@/components/shell/page-header";
import type { IconComponent } from "@/components/ui/brand-icons";
import { buttonVariants } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import {
  type LiveMetrics,
  rangeForDays,
  useLiveMetrics,
  useReportSummary,
  useReportTimeseries,
} from "@/lib/api/reports";

import { NetworkOrbit } from "./network-orbit";
import { useIntlTag, useT } from "@/lib/i18n/provider";
import type { MessageKey } from "@/lib/i18n/translate";

const LIVE: {
  key: keyof LiveMetrics;
  label: MessageKey;
  icon: IconComponent;
}[] = [
  { key: "open", label: "overview.live.open", icon: InboxIcon },
  { key: "unattended", label: "overview.live.unattended", icon: ClockIcon },
  { key: "unassigned", label: "overview.live.unassigned", icon: UnassignedIcon },
  { key: "pending", label: "overview.live.pending", icon: HourglassIcon },
];

const ACTIONS: {
  label: MessageKey;
  desc: MessageKey;
  icon: IconComponent;
  segment: string;
}[] = [
  {
    label: "overview.shortcut.conversations",
    desc: "overview.shortcut.conversationsDesc",
    icon: MessagesIcon,
    segment: "conversations",
  },
  {
    label: "nav.instagram",
    desc: "overview.shortcut.instagramDesc",
    icon: InstagramNavIcon,
    segment: "instagram",
  },
  {
    label: "overview.shortcut.campaigns",
    desc: "overview.shortcut.campaignsDesc",
    icon: MegaphoneIcon,
    segment: "campaigns",
  },
  {
    label: "overview.shortcut.reports",
    desc: "overview.shortcut.reportsDesc",
    icon: BarsIcon,
    segment: "reports",
  },
];

function SectionLabel({ children }: { children: string }) {
  return (
    <p className="text-[11px] font-medium uppercase tracking-[0.08em] text-fg-muted">
      {children}
    </p>
  );
}

function LiveCard({
  def,
  value,
  loading,
}: {
  def: (typeof LIVE)[number];
  value: number | undefined;
  loading: boolean;
}) {
  const intlTag = useIntlTag();
  const t = useT();
  const Icon = def.icon;
  return (
    <Card className="flex items-center gap-3.5 p-4">
      <span
        data-live-icon={def.key}
        className="neon-nav inline-flex shrink-0 items-center justify-center"
      >
        <Icon className="h-8 w-8" aria-hidden />
      </span>
      <div className="min-w-0">
        <p className="font-numeric text-2xl font-semibold leading-none tabular-nums text-fg">
          {loading ? "—" : (value ?? 0).toLocaleString(intlTag)}
        </p>
        <p className="mt-1.5 truncate text-xs text-fg-muted">{t(def.label)}</p>
      </div>
    </Card>
  );
}

function ActionRow({
  accountId,
  action,
}: {
  accountId: string;
  action: (typeof ACTIONS)[number];
}) {
  const t = useT();
  const Icon = action.icon;
  return (
    <Link
      href={`/accounts/${accountId}/${action.segment}`}
      className="group flex items-center gap-3 rounded-md border border-transparent px-2 py-2 transition-colors hover:border-glass hover:bg-hover-glass focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-neon"
    >
      <span className="neon-nav inline-flex shrink-0 items-center justify-center transition-colors group-hover:text-lit">
        <Icon className="h-5 w-5" aria-hidden />
      </span>
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium text-fg">{t(action.label)}</p>
        <p className="truncate text-xs text-fg-muted">{t(action.desc)}</p>
      </div>
      <ArrowRight
        className="h-4 w-4 shrink-0 text-fg-muted opacity-0 transition-all group-hover:translate-x-0.5 group-hover:opacity-100"
        aria-hidden
      />
    </Link>
  );
}

/**
 * Account overview (Inicio) — the landing surface: live state, the 7-day KPI
 * set (reused from Reportes), a conversations chart, and quick links. All
 * client-side because the metrics are live queries.
 */
export function AccountOverview({ accountId }: { accountId: string }) {
  const intlTag = useIntlTag();
  const t = useT();
  const shell = useContext(PageSignContext);
  useEffect(() => {
    if (!shell) return;
    shell.setSignTitle(t("nav.home"));
    return () => shell.setSignTitle(null);
  }, [shell, t]);

  // Memoized so the window doesn't drift every render and thrash the queries.
  const range = useMemo(() => rangeForDays(7), []);
  const live = useLiveMetrics(accountId);
  const summary = useReportSummary(accountId, range);
  const series = useReportTimeseries(accountId, "conversations_count", range);

  return (
    <div className="mx-auto max-w-6xl space-y-8">
      <section className="grid items-center gap-6 md:grid-cols-[minmax(0,1fr)_auto] lg:gap-8">
        <div className="min-w-0">
          <h2 className="neon-sign text-[34px] leading-[1.2] sm:text-[42px]">
            {t("overview.welcome")}
          </h2>
          <p className="mt-2.5 max-w-xl text-sm leading-relaxed text-fg-muted">
            {t("overview.intro")}
          </p>
          <div className="mt-6 flex flex-wrap items-center gap-3">
            <Link
              href={`/accounts/${accountId}/conversations`}
              className={buttonVariants({ variant: "primary" })}
            >
              {t("overview.openInbox")}
            </Link>
            <Link
              href={`/accounts/${accountId}/publications`}
              className={buttonVariants({ variant: "secondary" })}
            >
              {t("overview.goCalendar")}
            </Link>
          </div>
        </div>

        <NetworkOrbit className="mx-auto md:mx-0" />
      </section>

      <section className="space-y-3">
        <SectionLabel>{t("overview.rightNow")}</SectionLabel>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {LIVE.map((def) => (
            <LiveCard
              key={def.key}
              def={def}
              value={live.data?.[def.key]}
              loading={live.isLoading}
            />
          ))}
        </div>
      </section>

      <section className="space-y-3">
        <SectionLabel>{t("overview.last7")}</SectionLabel>
        {summary.isLoading ? (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <Card key={i} className="h-[92px] animate-pulse p-4" />
            ))}
          </div>
        ) : summary.data ? (
          <SummaryCards data={summary.data} />
        ) : (
          <Card className="p-4 text-sm text-fg-muted">
            {t("overview.metricsFailed")}
          </Card>
        )}
      </section>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="p-5 lg:col-span-2">
          <div className="mb-4 flex items-start justify-between">
            <div>
              <p className="text-sm font-medium text-fg">{t("overview.conversations")}</p>
              <p className="text-xs text-fg-muted">{t("overview.last7")}</p>
            </div>
            <p className="font-numeric text-2xl font-semibold tabular-nums text-fg">
              {summary.data?.conversations_count?.toLocaleString(intlTag) ?? "—"}
            </p>
          </div>
          {series.isLoading ? (
            <div className="h-48 animate-pulse rounded-md bg-surface-2" />
          ) : (
            <MetricChart
              data={series.data ?? []}
              formatValue={(v) => v.toLocaleString(intlTag)}
            />
          )}
        </Card>

        <Card className="p-5">
          <p className="mb-3 text-sm font-medium text-fg">{t("overview.shortcuts")}</p>
          <div className="flex flex-col gap-1">
            {ACTIONS.map((action) => (
              <ActionRow
                key={action.segment}
                accountId={accountId}
                action={action}
              />
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
}
