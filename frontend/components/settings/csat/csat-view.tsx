"use client";

import { MessageSquareQuote } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { SegmentedControl } from "@/components/ui/segmented-control";
import {
  type CsatMetrics,
  type CsatResponse,
  useCsatMetrics,
  useCsatResponses,
} from "@/lib/api/csat";
import { relativeTime } from "@/lib/time";

import { RatingStars } from "./rating-stars";
import { useLocale, useT } from "@/lib/i18n/provider";
import type { MessageKey } from "@/lib/i18n/translate";

const RANGES = [
  { value: 7, label: "reports.range.d7" },
  { value: 30, label: "reports.range.d30" },
  { value: 90, label: "reports.range.d90" },
] as const;

const RATING_FILTERS = [
  { value: undefined, label: "helpCenter.filters.all" },
  { value: 5, label: "5" },
  { value: 4, label: "4" },
  { value: 3, label: "3" },
  { value: 2, label: "2" },
  { value: 1, label: "1" },
] as const;

export function CsatView({ accountId }: { accountId: string }) {
  const t = useT();
  const [days, setDays] = useState<number>(30);
  const [rating, setRating] = useState<number | undefined>(undefined);

  const range = useMemo(() => {
    const until = Math.floor(Date.now() / 1000);
    return { since: until - days * 86_400, until };
  }, [days]);

  const metrics = useCsatMetrics(accountId, range);
  const responses = useCsatResponses(accountId, {
    rating,
    since: range.since,
    until: range.until,
  });

  return (
    <div className="max-w-3xl space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-xl font-medium text-fg">CSAT</h2>
        <SegmentedControl
          size="sm"
          ariaLabel={t("reports.period")}
          value={days}
          onValueChange={setDays}
          options={RANGES.map((o) => ({ ...o, label: t(o.label) }))}
        />
      </div>

      {/* Metric cards */}
      {metrics.isLoading ? (
        <p className="text-sm text-fg-muted">{t("reports.loadingMetrics")}</p>
      ) : metrics.isError ? (
        <p role="alert" className="text-sm text-danger">
          {t("settingsCsat.metricsFailed")}
        </p>
      ) : metrics.data ? (
        <>
          <MetricsCards data={metrics.data} />
          <RatingBreakdown data={metrics.data} />
        </>
      ) : null}

      {/* Rating filter */}
      <SegmentedControl
        size="sm"
        ariaLabel={t("settingsCsat.rating")}
        value={rating}
        onValueChange={setRating}
        options={RATING_FILTERS.map((o) => ({
          ...o,
          label: o.value === undefined ? t(o.label as MessageKey) : o.label,
        }))}
      />

      {/* Response list */}
      <Card>
        <CardHeader>
          <CardTitle>{t("settingsCsat.responses")}</CardTitle>
        </CardHeader>
        <CardContent>
          {responses.isLoading ? (
            <p className="py-8 text-center text-sm text-fg-muted">{t("common.loading")}</p>
          ) : responses.isError ? (
            <p role="alert" className="py-8 text-center text-sm text-danger">
              {t("settingsCsat.responsesFailed")}
            </p>
          ) : (responses.data?.length ?? 0) === 0 ? (
            <p className="py-8 text-center text-sm text-fg-muted">
              {t("settingsCsat.noResponses")}
            </p>
          ) : (
            <ul className="divide-y divide-glass">
              {responses.data?.map((r) => (
                <ResponseRow key={r.id} accountId={accountId} response={r} />
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function MetricsCards({ data }: { data: CsatMetrics }) {
  const t = useT();
  const totalSent = data.total_sent_messages_count || 0;
  const responseRate =
    totalSent > 0 ? Math.round((data.total_count / totalSent) * 100) : 0;

  // Average rating from the breakdown buckets.
  let avg: number | null = null;
  if (data.total_count > 0) {
    let sum = 0;
    for (const [k, v] of Object.entries(data.ratings_count)) {
      sum += Number(k) * (Number(v) || 0);
    }
    avg = sum / data.total_count;
  }

  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
      <Card className="p-4">
        <p className="text-[11px] font-medium uppercase tracking-[0.08em] text-fg-muted">
          {t("settingsCsat.surveysSent")}
        </p>
        <p className="mt-1 font-numeric text-2xl font-semibold tabular-nums text-fg">
          {totalSent}
        </p>
      </Card>
      <Card className="p-4">
        <p className="text-[11px] font-medium uppercase tracking-[0.08em] text-fg-muted">
          {t("settingsCsat.responses")}
        </p>
        <p className="mt-1 font-numeric text-2xl font-semibold tabular-nums text-fg">
          {data.total_count}
        </p>
      </Card>
      <Card className="p-4">
        <p className="text-[11px] font-medium uppercase tracking-[0.08em] text-fg-muted">
          {t("settingsCsat.responseRate")}
        </p>
        <p className="mt-1 font-numeric text-2xl font-semibold tabular-nums text-fg">
          {responseRate}%
        </p>
      </Card>
      <Card className="p-4">
        <p className="text-[11px] font-medium uppercase tracking-[0.08em] text-fg-muted">
          {t("settingsCsat.average")}
        </p>
        <p className="mt-1 font-numeric text-2xl font-semibold tabular-nums text-fg">
          {avg !== null ? `${avg.toFixed(1)} / 5` : "—"}
        </p>
      </Card>
    </div>
  );
}

function RatingBreakdown({ data }: { data: CsatMetrics }) {
  const t = useT();
  const total = data.total_count || 0;
  const buckets = [5, 4, 3, 2, 1].map((rating) => {
    const count = Number(data.ratings_count[String(rating)] ?? 0);
    const pct = total > 0 ? Math.round((count / total) * 100) : 0;
    return { rating, count, pct };
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("settingsCsat.distribution")}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        {buckets.map((b) => (
          <div key={b.rating} className="flex items-center gap-3">
            <span className="w-12 shrink-0 font-numeric text-sm tabular-nums text-fg-muted">
              {b.rating} ★
            </span>
            <div className="h-2 flex-1 overflow-hidden rounded-full bg-surface-2">
              <div
                className="h-full bg-neon"
                style={{ width: `${b.pct}%` }}
              />
            </div>
            <span className="w-16 shrink-0 text-right font-numeric text-xs tabular-nums text-fg-muted">
              {b.count} · {b.pct}%
            </span>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

function ResponseRow({
  accountId,
  response,
}: {
  accountId: string;
  response: CsatResponse;
}) {
  const t = useT();
  const locale = useLocale();
  const contactName = response.contact?.name?.trim() || t("settingsCsat.anonymous");
  return (
    <li className="flex items-start gap-3 py-3">
      <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-focused text-lit">
        <MessageSquareQuote className="h-4 w-4" aria-hidden />
      </span>
      <div className="min-w-0 flex-1 space-y-1">
        <div className="flex flex-wrap items-center gap-2">
          <RatingStars rating={response.rating} />
          <span className="text-sm font-medium text-fg">{contactName}</span>
          {response.conversation_id ? (
            <Link
              href={`/accounts/${accountId}/conversations/${response.conversation_id}`}
              className="font-numeric text-xs tabular-nums text-lit hover:underline"
            >
              #{response.conversation_id}
            </Link>
          ) : null}
        </div>
        {response.feedback_message ? (
          <p className="whitespace-pre-wrap break-words text-sm text-fg">
            {response.feedback_message}
          </p>
        ) : (
          <p className="text-sm text-fg-muted">{t("settingsCsat.noComment")}</p>
        )}
        <p className="text-xs text-fg-muted">
          {response.assigned_agent
            ? `${t("settingsCsat.agent", { name: response.assigned_agent.name })} · `
            : ""}
          {relativeTime(response.created_at, locale)}
        </p>
      </div>
    </li>
  );
}
