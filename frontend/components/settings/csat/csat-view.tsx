"use client";

import { MessageSquareQuote } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  type CsatMetrics,
  type CsatResponse,
  useCsatMetrics,
  useCsatResponses,
} from "@/lib/api/csat";
import { relativeTime } from "@/lib/time";
import { cn } from "@/lib/utils";

import { RatingStars } from "./rating-stars";

const RANGES = [
  { days: 7, label: "7 días" },
  { days: 30, label: "30 días" },
  { days: 90, label: "90 días" },
] as const;

const RATING_FILTERS = [
  { value: undefined, label: "Todos" },
  { value: 5, label: "5" },
  { value: 4, label: "4" },
  { value: 3, label: "3" },
  { value: 2, label: "2" },
  { value: 1, label: "1" },
] as const;

export function CsatView({ accountId }: { accountId: string }) {
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
    <div className="mx-auto max-w-3xl space-y-4 p-4 md:p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-xl font-semibold text-fg">CSAT</h2>
        <div className="flex gap-2">
          {RANGES.map((r) => (
            <button
              key={r.days}
              type="button"
              onClick={() => setDays(r.days)}
              aria-pressed={days === r.days}
              className={cn(
                "rounded-md px-3 py-1.5 text-sm font-medium",
                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                days === r.days
                  ? "bg-surface-2 font-semibold text-fg"
                  : "border border-border bg-surface text-fg hover:bg-surface-2",
              )}
            >
              {r.label}
            </button>
          ))}
        </div>
      </div>

      {/* Metric cards */}
      {metrics.isLoading ? (
        <p className="text-sm text-fg-muted">Cargando métricas…</p>
      ) : metrics.isError ? (
        <p role="alert" className="text-sm text-danger">
          No se pudieron cargar las métricas de CSAT.
        </p>
      ) : metrics.data ? (
        <>
          <MetricsCards data={metrics.data} />
          <RatingBreakdown data={metrics.data} />
        </>
      ) : null}

      {/* Rating filter */}
      <div className="flex flex-wrap gap-2">
        {RATING_FILTERS.map((r) => (
          <button
            key={r.label}
            type="button"
            onClick={() => setRating(r.value)}
            aria-pressed={rating === r.value}
            className={cn(
              "rounded-md px-3 py-1.5 text-sm font-medium",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
              rating === r.value
                ? "bg-surface-2 font-semibold text-fg"
                : "border border-border bg-surface text-fg hover:bg-surface-2",
            )}
          >
            {r.label}
          </button>
        ))}
      </div>

      {/* Response list */}
      <Card>
        <CardHeader>
          <CardTitle>Respuestas</CardTitle>
        </CardHeader>
        <CardContent>
          {responses.isLoading ? (
            <p className="py-8 text-center text-sm text-fg-muted">Cargando…</p>
          ) : responses.isError ? (
            <p role="alert" className="py-8 text-center text-sm text-danger">
              No se pudieron cargar las respuestas.
            </p>
          ) : (responses.data?.length ?? 0) === 0 ? (
            <p className="py-8 text-center text-sm text-fg-muted">
              Sin respuestas en este período.
            </p>
          ) : (
            <ul className="divide-y divide-border">
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
        <p className="text-xs font-medium uppercase tracking-wide text-fg-muted">
          Encuestas enviadas
        </p>
        <p className="mt-1 text-2xl font-semibold text-fg">{totalSent}</p>
      </Card>
      <Card className="p-4">
        <p className="text-xs font-medium uppercase tracking-wide text-fg-muted">
          Respuestas
        </p>
        <p className="mt-1 text-2xl font-semibold text-fg">{data.total_count}</p>
      </Card>
      <Card className="p-4">
        <p className="text-xs font-medium uppercase tracking-wide text-fg-muted">
          Tasa de respuesta
        </p>
        <p className="mt-1 text-2xl font-semibold text-fg">{responseRate}%</p>
      </Card>
      <Card className="p-4">
        <p className="text-xs font-medium uppercase tracking-wide text-fg-muted">
          Promedio
        </p>
        <p className="mt-1 text-2xl font-semibold text-fg">
          {avg !== null ? `${avg.toFixed(1)} / 5` : "—"}
        </p>
      </Card>
    </div>
  );
}

function RatingBreakdown({ data }: { data: CsatMetrics }) {
  const total = data.total_count || 0;
  const buckets = [5, 4, 3, 2, 1].map((rating) => {
    const count = Number(data.ratings_count[String(rating)] ?? 0);
    const pct = total > 0 ? Math.round((count / total) * 100) : 0;
    return { rating, count, pct };
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle>Distribución</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        {buckets.map((b) => (
          <div key={b.rating} className="flex items-center gap-3">
            <span className="w-12 shrink-0 text-sm text-fg-muted">
              {b.rating} ★
            </span>
            <div className="h-2 flex-1 overflow-hidden rounded-full bg-surface-2">
              <div
                className="h-full bg-primary"
                style={{ width: `${b.pct}%` }}
              />
            </div>
            <span className="w-16 shrink-0 text-right text-xs text-fg-muted">
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
  const contactName = response.contact?.name?.trim() || "Anónimo";
  return (
    <li className="flex items-start gap-3 py-3">
      <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-warning/10 text-warning">
        <MessageSquareQuote className="h-4 w-4" aria-hidden />
      </span>
      <div className="min-w-0 flex-1 space-y-1">
        <div className="flex flex-wrap items-center gap-2">
          <RatingStars rating={response.rating} />
          <span className="text-sm font-medium text-fg">{contactName}</span>
          {response.conversation_id ? (
            <Link
              href={`/accounts/${accountId}/conversations/${response.conversation_id}`}
              className="text-xs text-info hover:underline"
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
          <p className="text-sm text-fg-muted">(sin comentario)</p>
        )}
        <p className="text-xs text-fg-muted">
          {response.assigned_agent ? `Agente: ${response.assigned_agent.name} · ` : ""}
          {relativeTime(response.created_at)}
        </p>
      </div>
    </li>
  );
}
