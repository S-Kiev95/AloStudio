"use client";

import { ChevronLeft, ChevronRight, RefreshCw } from "lucide-react";
import { useState } from "react";

import { PageHeader } from "@/components/shell/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ApiError } from "@/lib/api/errors";
import {
  currentMonth,
  shiftMonth,
  type UsageLimit,
  type UsageSummary,
  useSyncWhatsappCosts,
  useUsageLimits,
  useUsageSummary,
} from "@/lib/api/usage";

import { LimitEditor } from "./limit-editor";
import { useIntlTag, useT } from "@/lib/i18n/provider";
import type { MessageKey } from "@/lib/i18n/translate";

const CATEGORY_KEYS = new Set([
  "MARKETING",
  "UTILITY",
  "AUTHENTICATION",
  "AUTHENTICATION_INTERNATIONAL",
  "SERVICE",
  "MARKETING_LITE",
  "REFERRAL_CONVERSION",
]);
const PURPOSE_KEYS = new Set(["help_assistant", "call_summary", "agent", "instagram_autoreply", "help_center", "writing_assist"]);

function useMoney() {
  const tag = useIntlTag();
  return (amount: number, currency: string | null) =>
    currency
      ? new Intl.NumberFormat(tag, {
          style: "currency",
          currency,
          maximumFractionDigits: amount < 1 ? 4 : 2,
        }).format(amount)
      : amount.toLocaleString(tag, { maximumFractionDigits: 4 });
}

function Stat({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <Card className="p-4">
      <p className="text-xs font-medium uppercase tracking-wide text-fg-muted">{label}</p>
      <p className="mt-1 font-numeric text-2xl font-semibold tabular-nums text-fg">{value}</p>
      {hint ? <p className="mt-1 text-xs text-fg-muted">{hint}</p> : null}
    </Card>
  );
}

function Table({
  head,
  rows,
  compact = false,
}: {
  head: string[];
  rows: Array<Array<string | number>>;
  /** Fits a narrow column (no minimum width, no sideways scroll). */
  compact?: boolean;
}) {
  return (
    <div className={compact ? undefined : "overflow-x-auto"}>
      <table className={compact ? "w-full text-left text-sm" : "w-full min-w-[420px] text-left text-sm"}>
        <thead className="text-xs text-fg-muted">
          <tr>
            {head.map((h, i) => (
              <th key={h} className={i === 0 ? "py-1.5 pr-3 font-medium" : "py-1.5 pl-3 text-right font-medium"}>
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-glass">
          {rows.map((row, r) => (
            <tr key={r}>
              {row.map((cell, i) => (
                <td
                  key={i}
                  className={
                    i === 0
                      ? "py-2 pr-3 text-fg"
                      : "py-2 pl-3 text-right font-numeric tabular-nums text-fg"
                  }
                >
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function WhatsappCard({
  data,
  accountId,
  limit,
  showLimit,
}: {
  data: UsageSummary["whatsapp"];
  accountId: string;
  limit: UsageLimit | undefined;
  showLimit: boolean;
}) {
  const t = useT();
  const money = useMoney();
  const tag = useIntlTag();
  const cur = data.currency;
  const category = (c: string) =>
    CATEGORY_KEYS.has(c) ? t(`usage.categories.${c}` as MessageKey) : c;
  const empty = data.messages === 0;
  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("usage.whatsappTitle")}</CardTitle>
        <p className="text-sm text-fg-muted">{t("usage.whatsappHint")}</p>
        <p className="text-xs text-fg-muted">
          {data.last_synced_at
            ? t("usage.lastSync", {
                date: new Date(data.last_synced_at * 1000).toLocaleString(tag),
              })
            : t("usage.neverSynced")}
        </p>
      </CardHeader>
      <CardContent className="space-y-6">
        {showLimit ? (
          <LimitEditor
            accountId={accountId}
            kind="whatsapp"
            limit={limit}
            currency={cur ?? "USD"}
          />
        ) : null}
        {empty ? (
          <p className="text-sm text-fg-muted">{t("usage.noWhatsapp")}</p>
        ) : (
          <div className="grid gap-6 lg:grid-cols-3">
            <div className="space-y-2">
              <h3 className="text-sm font-semibold text-fg">{t("usage.byNumber")}</h3>
              <Table
                compact
                head={["", t("usage.messages"), t("usage.cost")]}
                rows={data.by_inbox.map((r) => [
                  r.name ?? `#${r.inbox_id}`,
                  r.volume.toLocaleString(tag),
                  money(r.cost, cur),
                ])}
              />
            </div>
            <div className="space-y-2">
              <h3 className="text-sm font-semibold text-fg">{t("usage.byCategory")}</h3>
              <Table
                compact
                head={["", t("usage.messages"), t("usage.cost")]}
                rows={data.by_category.map((r) => [
                  category(r.category),
                  r.volume.toLocaleString(tag),
                  money(r.cost, cur),
                ])}
              />
            </div>
            <div className="space-y-2">
              <h3 className="text-sm font-semibold text-fg">{t("usage.byCountry")}</h3>
              <Table
                compact
                head={["", t("usage.messages"), t("usage.cost")]}
                rows={data.by_country.map((r) => [
                  r.country,
                  r.volume.toLocaleString(tag),
                  money(r.cost, cur),
                ])}
              />
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export function CostsView({ accountId }: { accountId: string }) {
  const t = useT();
  const money = useMoney();
  const tag = useIntlTag();
  const [month, setMonth] = useState(() => currentMonth());
  const q = useUsageSummary(accountId, month);
  const limitsQ = useUsageLimits(accountId);
  const limitOf = (kind: "whatsapp" | "ai") => limitsQ.data?.find((l) => l.kind === kind);
  const sync = useSyncWhatsappCosts(accountId, month);
  const data = sync.data?.month === month ? { ...q.data, ...sync.data } : q.data;
  const label = new Date(`${month}-15T12:00:00Z`).toLocaleDateString(tag, {
    month: "long",
    year: "numeric",
  });
  const forbidden = q.error instanceof ApiError && [401, 403].includes(q.error.status);
  const isCurrent = month >= currentMonth();
  const wa = data?.whatsapp;
  const purpose = (p: string | null) =>
    p && PURPOSE_KEYS.has(p) ? t(`usage.purposes.${p}` as MessageKey) : (p ?? "");

  return (
    <div className="mx-auto max-w-7xl space-y-4">
      <PageHeader
        title={t("usage.title")}
        description={t("usage.subtitle")}
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <Button
              type="button"
              variant="ghost"
              size="icon"
              aria-label={t("usage.prevMonth")}
              onClick={() => setMonth((m) => shiftMonth(m, -1))}
            >
              <ChevronLeft className="h-4 w-4" aria-hidden />
            </Button>
            <span className="min-w-[9rem] text-center text-sm font-medium capitalize text-fg">
              {label}
            </span>
            <Button
              type="button"
              variant="ghost"
              size="icon"
              aria-label={t("usage.nextMonth")}
              disabled={isCurrent}
              onClick={() => setMonth((m) => shiftMonth(m, 1))}
            >
              <ChevronRight className="h-4 w-4" aria-hidden />
            </Button>
            <Button
              type="button"
              variant="secondary"
              size="sm"
              loading={sync.isPending}
              disabled={forbidden}
              onClick={() => sync.mutate()}
            >
              <RefreshCw className="h-3.5 w-3.5" aria-hidden />
              {t("usage.refresh")}
            </Button>
          </div>
        }
      />

      {forbidden ? (
        <p className="text-sm text-fg-muted">{t("usage.adminOnly")}</p>
      ) : q.isLoading ? (
        <p className="text-sm text-fg-muted">{t("common.loading")}</p>
      ) : q.isError || !data || !wa ? (
        <p role="alert" className="text-sm text-danger">
          {t("usage.loadFailed")}
        </p>
      ) : (
        <>
          {(sync.data?.sync_errors ?? []).map((e) => (
            <p key={e.inbox_id} role="alert" className="text-sm text-danger">
              {t("usage.syncError", { name: e.name, message: e.message ?? "" })}
            </p>
          ))}
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Stat
              label={t("usage.whatsappTitle")}
              value={wa.currency ? money(wa.total_cost, wa.currency) : wa.messages ? t("usage.several") : money(0, "USD")}
              hint={`${wa.billable_messages.toLocaleString(tag)} ${t("usage.billable").toLowerCase()} / ${wa.messages.toLocaleString(tag)}`}
            />
            <Stat
              label={t("usage.aiTitle")}
              value={money(data.ai.total_cost, data.ai.currency)}
              hint={`${data.ai.requests.toLocaleString(tag)} ${t("usage.requests").toLowerCase()}`}
            />
            <Stat
              label={t("usage.byCampaign")}
              value={money(
                data.campaigns.reduce((s, c) => s + c.estimated_cost, 0),
                wa.currency ?? "USD",
              )}
              hint={`${data.campaigns.length}`}
            />
            <Stat
              label={t("usage.total")}
              value={
                (wa.currency ?? "USD") === data.ai.currency
                  ? money(wa.total_cost + data.ai.total_cost, data.ai.currency)
                  : t("usage.several")
              }
            />
          </div>

          <WhatsappCard
            data={wa}
            accountId={accountId}
            limit={limitOf("whatsapp")}
            showLimit={isCurrent}
          />

          <Card>
            <CardHeader>
              <CardTitle>{t("usage.byCampaign")}</CardTitle>
              <p className="text-sm text-fg-muted">{t("usage.campaignHint")}</p>
            </CardHeader>
            <CardContent>
              {data.campaigns.length === 0 ? (
                <p className="text-sm text-fg-muted">{t("usage.noCampaigns")}</p>
              ) : (
                <Table
                  head={["", t("usage.messages"), t("usage.billable"), t("usage.cost")]}
                  rows={data.campaigns.map((c) => [
                    c.title ?? `#${c.campaign_id}`,
                    c.messages.toLocaleString(tag),
                    c.billable_messages.toLocaleString(tag),
                    `${money(c.estimated_cost, wa.currency ?? "USD")}${c.complete ? "" : ` (${t("usage.incomplete")})`}`,
                  ])}
                />
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>{t("usage.aiTitle")}</CardTitle>
              <p className="text-sm text-fg-muted">
                {t("usage.aiHint", { date: data.ai.prices_checked_on })}
              </p>
            </CardHeader>
            <CardContent className="space-y-4">
              {isCurrent ? (
                <LimitEditor
                  accountId={accountId}
                  kind="ai"
                  limit={limitOf("ai")}
                  currency="USD"
                />
              ) : null}
              {data.ai.items.length === 0 ? (
                <p className="text-sm text-fg-muted">{t("usage.noAi")}</p>
              ) : (
                <Table
                  head={[
                    t("usage.purpose"),
                    t("usage.model"),
                    t("usage.requests"),
                    t("usage.tokensIn"),
                    t("usage.tokensOut"),
                    t("usage.cost"),
                  ]}
                  rows={data.ai.items.map((i) => [
                    purpose(i.purpose),
                    i.model ?? "",
                    i.requests.toLocaleString(tag),
                    i.input_tokens.toLocaleString(tag),
                    i.output_tokens.toLocaleString(tag),
                    money(i.cost, data.ai.currency),
                  ])}
                />
              )}
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
