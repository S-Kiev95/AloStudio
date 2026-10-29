"use client";

import {
  ArrowDown,
  ArrowUp,
  Clock,
  ExternalLink,
  Facebook,
  Instagram,
} from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";

import {
  addDaysLocal,
  formatDateTimeLocal,
  formatLocalDateKey,
} from "@/components/agenda/week-utils";
import { MetricChart } from "@/components/reports/metric-chart";
import { PageHeader } from "@/components/shell/page-header";
import { buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { SegmentedControl } from "@/components/ui/segmented-control";
import { selectClassName } from "@/components/ui/select";
import {
  type AnalyticsChannel,
  type MetricName,
  parsePublicationError,
  usePublicationAnalytics,
  usePublicationChannels,
} from "@/lib/api/publications";
import { cn } from "@/lib/utils";

import { ChannelAvatar, channelDisplayName, NetworkIcon } from "./network-icon";
import { formatMetricValue } from "./publication-detail-dialog";
import { PublicationErrorAlert } from "./publication-error-alert";

type PeriodOption = 7 | 30 | 90 | "custom";
type SeriesMetric = "reach" | "views";

const PERIOD_OPTIONS: { value: PeriodOption; label: string }[] = [
  { value: 7, label: "7 días" },
  { value: 30, label: "30 días" },
  { value: 90, label: "90 días" },
  { value: "custom", label: "Personalizado" },
];

const TOTAL_CARDS: {
  key: "posts" | MetricName;
  label: string;
}[] = [
  { key: "posts", label: "Publicaciones" },
  { key: "views", label: "Vistas" },
  { key: "reach", label: "Alcance" },
  { key: "interactions", label: "Interacciones" },
  { key: "likes", label: "Me gusta" },
  { key: "comments", label: "Comentarios" },
  { key: "shares", label: "Compartidos" },
  { key: "saves", label: "Guardados" },
];

const METRIC_LABELS: { key: MetricName; label: string }[] = [
  { key: "views", label: "Vistas" },
  { key: "reach", label: "Alcance" },
  { key: "interactions", label: "Interacciones" },
  { key: "likes", label: "Me gusta" },
  { key: "comments", label: "Comentarios" },
  { key: "shares", label: "Compartidos" },
  { key: "saves", label: "Guardados" },
];

/** Local midnight of a ``YYYY-MM-DD`` date, or ``null``. */
function localDay(ymd: string): Date | null {
  const [y, m, d] = ymd.split("-").map(Number);
  if (!y || !m || !d) return null;
  const date = new Date(y, m - 1, d);
  return Number.isNaN(date.getTime()) ? null : date;
}

function validateCustomRange(from: string, to: string): string | null {
  if (!from || !to) return "Seleccioná las fechas Desde y Hasta.";
  const start = localDay(from);
  const end = localDay(to);
  if (!start || !end) {
    return "Las fechas ingresadas no son válidas.";
  }
  if (end.getTime() < start.getTime()) {
    return "La fecha Hasta debe ser igual o posterior a Desde.";
  }
  // Both ends count: the period runs through the whole "Hasta" day.
  const days =
    Math.round((end.getTime() - start.getTime()) / 86_400_000) + 1;
  if (days > 366) {
    return "El período no puede superar un año (366 días).";
  }
  return null;
}

export function PublicationsAnalyticsView({
  accountId,
}: {
  accountId: string;
}) {
  const today = useMemo(() => new Date(), []);
  const [period, setPeriod] = useState<PeriodOption>(30);
  const [customFrom, setCustomFrom] = useState<string>(() =>
    formatLocalDateKey(addDaysLocal(today, -29)),
  );
  const [customTo, setCustomTo] = useState<string>(() =>
    formatLocalDateKey(today),
  );
  const [channelIdStr, setChannelIdStr] = useState<string>("");

  const channelsQuery = usePublicationChannels(accountId);
  const channels = channelsQuery.data ?? [];
  const hasChannels = channels.length > 0;

  // The backend takes instants, ``from`` inclusive and ``to`` exclusive:
  // send the local midnights around the chosen days, so the period covers
  // them whole in the browser's time zone (today included).
  const computedRange = useMemo(() => {
    if (period === "custom") {
      const start = localDay(customFrom);
      const end = localDay(customTo);
      return start && end
        ? { from: start.toISOString(), to: addDaysLocal(end, 1).toISOString() }
        : { from: "", to: "" };
    }
    return {
      from: addDaysLocal(today, -(period - 1)).toISOString(),
      to: addDaysLocal(today, 1).toISOString(),
    };
  }, [period, customFrom, customTo, today]);

  const customError =
    period === "custom" ? validateCustomRange(customFrom, customTo) : null;

  const selectedChannelId = channelIdStr ? Number(channelIdStr) : undefined;

  const analyticsQuery = usePublicationAnalytics(accountId, {
    from: computedRange.from,
    to: computedRange.to,
    channel_id: selectedChannelId,
    enabled: !channelsQuery.isLoading && hasChannels && customError === null,
  });

  if (channelsQuery.isLoading) {
    return (
      <div className="space-y-4">
        <PageHeader title="Estadísticas" />
        <div className="rounded-md border border-glass bg-surface p-12 text-center text-sm text-fg-muted">
          Cargando estadísticas…
        </div>
      </div>
    );
  }

  // Empty state when no channels are connected (matches analytics reference).
  if (!hasChannels) {
    return (
      <div className="space-y-4">
        <PageHeader title="Estadísticas" />
        <div
          data-testid="analytics-empty-state"
          className="flex min-h-[420px] flex-col items-center justify-center rounded-md border border-glass bg-surface px-6 py-16 text-center"
        >
          <h2 className="text-xl font-medium text-fg sm:text-2xl">
            Todavía no hay estadísticas para mostrar
          </h2>
          <p className="mt-2 text-sm text-fg-muted">
            Agregá canales de redes sociales para empezar a medir tus
            publicaciones.
          </p>

          <div className="mt-5 flex flex-wrap items-center justify-center gap-2 text-xs">
            <span className="font-medium uppercase tracking-[0.08em] text-fg-muted">
              Soportadas:
            </span>
            <span className="inline-flex items-center gap-1.5 rounded-pill border border-glass bg-field px-3 py-1 text-fg">
              <Instagram className="h-3.5 w-3.5 text-[#E1306C]" aria-hidden />
              Instagram
            </span>
            <span className="inline-flex items-center gap-1.5 rounded-pill border border-glass bg-field px-3 py-1 text-fg">
              <Facebook className="h-3.5 w-3.5 text-[#1877F2]" aria-hidden />
              Facebook
            </span>
          </div>

          <div className="mt-6">
            <Link
              href={`/accounts/${accountId}/publications`}
              className={buttonVariants()}
            >
              Ir al calendario para agregar canales
            </Link>
          </div>
        </div>
      </div>
    );
  }

  const data = analyticsQuery.data;

  return (
    <div className="space-y-5">
      <PageHeader
        title="Estadísticas"
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <select
              aria-label="Filtrar por canal"
              value={channelIdStr}
              onChange={(e) => setChannelIdStr(e.target.value)}
              className={selectClassName("sm")}
            >
              <option value="">Todos los canales</option>
              {channels.map((ch) => (
                <option key={ch.id} value={String(ch.id)}>
                  {channelDisplayName(ch)}
                </option>
              ))}
            </select>

            <SegmentedControl
              ariaLabel="Período"
              size="sm"
              value={period}
              onValueChange={setPeriod}
              options={PERIOD_OPTIONS}
            />
          </div>
        }
      />

      {period === "custom" ? (
        <div className="flex flex-wrap items-end gap-3 rounded-md border border-glass bg-surface p-3">
          <div className="space-y-1">
            <Label htmlFor="analytics-from">Desde</Label>
            <Input
              id="analytics-from"
              type="date"
              value={customFrom}
              onChange={(e) => setCustomFrom(e.target.value)}
              className="w-auto tabular-nums"
            />
          </div>
          <div className="space-y-1">
            <Label htmlFor="analytics-to">Hasta</Label>
            <Input
              id="analytics-to"
              type="date"
              value={customTo}
              onChange={(e) => setCustomTo(e.target.value)}
              className="w-auto tabular-nums"
            />
          </div>
          {customError ? (
            <p role="alert" className="pb-2 text-xs text-danger">
              {customError}
            </p>
          ) : null}
        </div>
      ) : null}

      {/* Update cadence notice */}
      <p className="flex items-center gap-1.5 text-xs text-fg-muted">
        <Clock className="h-3.5 w-3.5 shrink-0" aria-hidden />
        Las cifras de los posts se actualizan cada hora y las de los canales una
        vez por día (03:47 UTC).
      </p>

      {analyticsQuery.isError ? (
        <PublicationErrorAlert
          error={parsePublicationError(
            analyticsQuery.error,
            "No se pudieron cargar las estadísticas.",
          )}
        />
      ) : analyticsQuery.isLoading ? (
        <div className="rounded-md border border-glass bg-surface p-10 text-center text-sm text-fg-muted">
          Cargando estadísticas…
        </div>
      ) : data ? (
        <>
          {/* Totals cards */}
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            {TOTAL_CARDS.map((card) => {
              const rawVal =
                card.key === "posts"
                  ? data.totals.posts
                  : data.totals[card.key];
              return (
                <Card
                  key={card.key}
                  data-testid={`total-card-${card.key}`}
                  className="p-4"
                >
                  <p className="text-[11px] font-medium uppercase tracking-[0.08em] text-fg-muted">
                    {card.label}
                  </p>
                  <p className="mt-1 font-numeric text-2xl font-semibold tabular-nums text-fg">
                    {formatMetricValue(rawVal)}
                  </p>
                </Card>
              );
            })}
          </div>

          {/* Per-channel breakdown & daily series chart */}
          <section className="space-y-3">
            <h2 className="text-base font-medium text-fg">Por canal</h2>
            {data.channels.length === 0 ? (
              <Card className="p-6 text-center text-sm text-fg-muted">
                Sin datos de canales para el período seleccionado.
              </Card>
            ) : (
              <div className="space-y-4">
                {data.channels.map((chEntry) => (
                  <ChannelAnalyticsCard
                    key={chEntry.channel.id}
                    entry={chEntry}
                  />
                ))}
              </div>
            )}
          </section>

          {/* Top posts */}
          <Card>
            <CardHeader>
              <CardTitle>Mejores publicaciones</CardTitle>
            </CardHeader>
            <CardContent>
              {data.top_posts.length === 0 ? (
                <p className="py-6 text-center text-sm text-fg-muted">
                  Todavía no hay publicaciones destacadas en este período.
                </p>
              ) : (
                <ul className="divide-y divide-glass">
                  {data.top_posts.map((post) => (
                    <li
                      key={`${post.publication_id}-${post.target_id}`}
                      className="space-y-2 py-3 first:pt-0 last:pb-0"
                    >
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <div className="flex items-center gap-2 text-xs text-fg-muted">
                          {post.channel ? (
                            <>
                              <NetworkIcon network={post.channel.network} />
                              <span className="font-medium text-fg">
                                {channelDisplayName(post.channel)}
                              </span>
                            </>
                          ) : null}
                          {post.published_at ? (
                            <span className="font-numeric tabular-nums">
                              {formatDateTimeLocal(post.published_at)}
                            </span>
                          ) : null}
                        </div>

                        {post.permalink ? (
                          <a
                            href={post.permalink}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center gap-1 text-xs font-medium text-info hover:underline"
                          >
                            Ver publicación
                            <ExternalLink className="h-3 w-3" aria-hidden />
                          </a>
                        ) : null}
                      </div>

                      <p className="line-clamp-2 whitespace-pre-wrap break-words text-sm text-fg">
                        {post.content?.trim() || "(Sin texto)"}
                      </p>

                      <div className="flex flex-wrap gap-3 text-xs text-fg-muted">
                        {METRIC_LABELS.map((m) => (
                          <span key={m.key} className="font-numeric tabular-nums">
                            {m.label}:{" "}
                            <strong className="font-semibold text-fg">
                              {formatMetricValue(post.metrics?.[m.key])}
                            </strong>
                          </span>
                        ))}
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </CardContent>
          </Card>
        </>
      ) : null}
    </div>
  );
}

function ChannelAnalyticsCard({ entry }: { entry: AnalyticsChannel }) {
  const [seriesMetric, setSeriesMetric] = useState<SeriesMetric>("reach");
  const name = channelDisplayName(entry.channel);

  return (
    <Card className="space-y-4 p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <ChannelAvatar channel={entry.channel} />
          <div>
            <h3 className="text-sm font-medium text-fg">{name}</h3>
            {entry.channel.username &&
            name !== `@${entry.channel.username}` ? (
              <p className="text-xs text-fg-muted">@{entry.channel.username}</p>
            ) : null}
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-4">
          <div className="text-right">
            <p className="text-[11px] uppercase tracking-[0.08em] text-fg-muted">
              Seguidores
            </p>
            <div className="flex items-center justify-end gap-1.5">
              <span className="font-numeric text-lg font-semibold tabular-nums text-fg">
                {formatMetricValue(entry.followers)}
              </span>
              <FollowersDelta delta={entry.followers_change} />
            </div>
          </div>

          <div className="text-right">
            <p className="text-[11px] uppercase tracking-[0.08em] text-fg-muted">
              Publicaciones
            </p>
            <p className="font-numeric text-lg font-semibold tabular-nums text-fg">
              {entry.posts.toLocaleString()}
            </p>
          </div>
        </div>
      </div>

      {/* Per-channel metric totals */}
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-7">
        {METRIC_LABELS.map((m) => (
          <div
            key={m.key}
            className="rounded-sm border border-glass bg-surface-2 px-3 py-2"
          >
            <p className="text-[10px] uppercase tracking-wide text-fg-muted">
              {m.label}
            </p>
            <p className="font-numeric text-sm font-semibold tabular-nums text-fg">
              {formatMetricValue(entry.metrics?.[m.key])}
            </p>
          </div>
        ))}
      </div>

      <div className="space-y-3 border-t border-glass pt-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className="text-xs font-medium text-fg-muted">Evolución diaria</p>
          <SegmentedControl
            ariaLabel={`Serie diaria de ${name}`}
            size="sm"
            value={seriesMetric}
            onValueChange={setSeriesMetric}
            options={[
              { value: "reach" as SeriesMetric, label: "Alcance" },
              { value: "views" as SeriesMetric, label: "Vistas" },
            ]}
          />
        </div>

        <MetricChart
          data={entry.series.map((pt) => ({
            // Local midnight: the chart labels the timestamp in local time.
            timestamp: (localDay(pt.date)?.getTime() ?? 0) / 1000,
            value: pt[seriesMetric] ?? 0,
          }))}
          formatValue={(v) => v.toLocaleString()}
        />
      </div>
    </Card>
  );
}

function FollowersDelta({ delta }: { delta: number | null }) {
  if (delta === null || !Number.isFinite(delta)) {
    return null;
  }
  if (delta === 0) {
    return (
      <span className="font-numeric text-xs tabular-nums text-fg-muted">0</span>
    );
  }
  const up = delta > 0;
  const Icon = up ? ArrowUp : ArrowDown;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-0.5 font-numeric text-xs font-medium tabular-nums",
        up ? "text-success" : "text-danger",
      )}
    >
      <Icon className="h-3 w-3" aria-hidden />
      {up ? `+${delta.toLocaleString()}` : delta.toLocaleString()}
    </span>
  );
}
