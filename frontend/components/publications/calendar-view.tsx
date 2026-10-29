"use client";

import {
  CalendarDays,
  ChevronLeft,
  ChevronRight,
  Film,
  List,
  Plus,
  X,
} from "lucide-react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { PageHeader } from "@/components/shell/page-header";
import { Button } from "@/components/ui/button";
import { SegmentedControl } from "@/components/ui/segmented-control";
import { useIsAccountAdmin } from "@/lib/api/profile";
import {
  canEditPublication,
  type Publication,
  type PublicationState,
  usePublicationChannels,
  usePublicationsRange,
} from "@/lib/api/publications";
import { cn } from "@/lib/utils";

import {
  addDaysLocal,
  addMonthsLocal,
  buildDayColumns,
  type CalendarDayColumn,
  type CalendarPeriod,
  computePeriodBounds,
  formatCalendarRangeLabel,
  formatClockHHMM,
  formatHourLabel,
  formatLocalDateKey,
  groupPublicationsByLocalDay,
  publicationPreviewWords,
  publicationTimestamp,
  SHORT_WEEKDAYS,
  startOfLocalDay,
  startOfWeekMonday,
} from "./calendar-utils";
import { ChannelsPanel } from "./channels-panel";
import { channelDisplayName, NetworkIcon, networkLabel } from "./network-icon";
import { PublicationDetailDialog } from "./publication-detail-dialog";
import { PublicationEditorDialog } from "./publication-editor-dialog";
import {
  PUBLICATION_STATE_FILTERS,
  PublicationStateBadge,
} from "./publication-state-badge";

type DisplayMode = "calendar" | "list";

const HOURS = Array.from({ length: 24 }, (_, i) => i);
const MONTH_MAX_VISIBLE = 3;

export function CalendarView({
  accountId,
  now: nowProp,
}: {
  accountId: string;
  now?: Date;
}) {
  const isAdmin = useIsAccountAdmin(accountId);
  const searchParams = useSearchParams();
  const router = useRouter();
  const pathname = usePathname() ?? `/accounts/${accountId}/publications`;

  const [now, setNow] = useState<Date>(() => nowProp ?? new Date());
  useEffect(() => {
    if (nowProp) {
      setNow(nowProp);
      return;
    }
    const timer = window.setInterval(() => setNow(new Date()), 60_000);
    return () => window.clearInterval(timer);
  }, [nowProp]);

  // Capture ?connected=<network>&channel=<id> or ?connect_error=<mensaje> and strip query.
  const [connectSuccess, setConnectSuccess] = useState<{
    network: string;
    channelId: number | null;
  } | null>(() => {
    const net = searchParams.get("connected");
    if (!net) return null;
    const chRaw = searchParams.get("channel");
    const chNum = chRaw ? Number(chRaw) : Number.NaN;
    return {
      network: net,
      channelId: Number.isFinite(chNum) ? chNum : null,
    };
  });
  const [connectError, setConnectError] = useState<string | null>(() =>
    searchParams.get("connect_error"),
  );

  useEffect(() => {
    if (
      searchParams.has("connected") ||
      searchParams.has("channel") ||
      searchParams.has("connect_error")
    ) {
      router.replace(pathname, { scroll: false });
    }
  }, [searchParams, router, pathname]);

  const [period, setPeriod] = useState<CalendarPeriod>("week");
  const [displayMode, setDisplayMode] = useState<DisplayMode>("calendar");
  const [cursor, setCursor] = useState<Date>(() =>
    startOfWeekMonday(nowProp ?? new Date()),
  );
  const [stateFilter, setStateFilter] = useState<PublicationState | undefined>(
    undefined,
  );
  const [selectedChannelId, setSelectedChannelId] = useState<
    number | undefined
  >(undefined);
  const [expandedMonthDays, setExpandedMonthDays] = useState<Set<string>>(
    () => new Set(),
  );

  const [editorOpen, setEditorOpen] = useState(false);
  const [editingPub, setEditingPub] = useState<Publication | null>(null);
  const [presetDate, setPresetDate] = useState<Date | null>(null);
  const [detailPub, setDetailPub] = useState<Publication | null>(null);

  const bounds = useMemo(
    () => computePeriodBounds(period, cursor),
    [period, cursor],
  );

  const channelsQuery = usePublicationChannels(accountId);
  const channels = useMemo(
    () => channelsQuery.data ?? [],
    [channelsQuery.data],
  );

  const publicationsQuery = usePublicationsRange(accountId, {
    from: bounds.start.toISOString(),
    to: bounds.end.toISOString(),
    state: displayMode === "list" ? stateFilter : undefined,
    channel_id: selectedChannelId,
  });
  const publications = useMemo(
    () => publicationsQuery.data ?? [],
    [publicationsQuery.data],
  );

  const connectedBannerText = useMemo(() => {
    if (!connectSuccess) return null;
    const matched =
      connectSuccess.channelId !== null
        ? channels.find((c) => c.id === connectSuccess.channelId)
        : undefined;
    const netName = networkLabel(connectSuccess.network);
    if (matched) {
      return `Canal ${channelDisplayName(matched)} (${netName}) conectado correctamente.`;
    }
    return `Canal de ${netName} conectado correctamente.`;
  }, [connectSuccess, channels]);

  function shiftCursor(direction: -1 | 1) {
    setCursor((prev) => {
      if (period === "day") return addDaysLocal(prev, direction);
      if (period === "week") return addDaysLocal(prev, direction * 7);
      return addMonthsLocal(prev, direction);
    });
  }

  function goToday() {
    const base = nowProp ?? new Date();
    if (period === "week") {
      setCursor(startOfWeekMonday(base));
    } else {
      setCursor(startOfLocalDay(base));
    }
  }

  function openNewPublication(date?: Date) {
    if (!isAdmin) return;
    setEditingPub(null);
    setPresetDate(date ?? null);
    setEditorOpen(true);
  }

  function handleCardClick(pub: Publication) {
    if (isAdmin && canEditPublication(pub.state)) {
      setEditingPub(pub);
      setPresetDate(null);
      setEditorOpen(true);
    } else {
      setDetailPub(pub);
    }
  }

  const todayKey = formatLocalDateKey(now);

  return (
    <div className="space-y-4">
      <PageHeader title="Calendario" />

      {/* Connection callback banners */}
      {connectedBannerText ? (
        <div
          role="status"
          className="flex items-center justify-between gap-2 rounded-md border border-success/30 bg-success/5 px-3 py-2 text-sm text-success"
        >
          <span>{connectedBannerText}</span>
          <button
            type="button"
            aria-label="Cerrar aviso"
            onClick={() => setConnectSuccess(null)}
            className="inline-flex h-6 w-6 items-center justify-center rounded-sm hover:bg-success/10"
          >
            <X className="h-3.5 w-3.5" aria-hidden />
          </button>
        </div>
      ) : null}

      {connectError ? (
        <div
          role="alert"
          className="flex items-center justify-between gap-2 rounded-md border border-danger/30 bg-danger/5 px-3 py-2 text-sm text-danger"
        >
          <span>{connectError}</span>
          <button
            type="button"
            aria-label="Cerrar aviso"
            onClick={() => setConnectError(null)}
            className="inline-flex h-6 w-6 items-center justify-center rounded-sm hover:bg-danger/10"
          >
            <X className="h-3.5 w-3.5" aria-hidden />
          </button>
        </div>
      ) : null}

      <div className="flex flex-col gap-4 lg:flex-row lg:items-start">
        {/* Main calendar/list column */}
        <div className="min-w-0 flex-1 space-y-3">
          {/* Toolbar */}
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex flex-wrap items-center gap-2">
              <div className="inline-flex items-center rounded-control border border-glass bg-field p-0.5">
                <button
                  type="button"
                  aria-label="Período anterior"
                  onClick={() => shiftCursor(-1)}
                  className="inline-flex h-9 w-9 items-center justify-center rounded-md text-fg-muted hover:bg-hover-glass hover:text-fg focus-visible:outline focus-visible:outline-2 focus-visible:outline-neon"
                >
                  <ChevronLeft className="h-4 w-4" aria-hidden />
                </button>
                <span className="px-3 font-numeric text-sm font-medium tabular-nums text-fg">
                  {formatCalendarRangeLabel(period, cursor)}
                </span>
                <button
                  type="button"
                  aria-label="Período siguiente"
                  onClick={() => shiftCursor(1)}
                  className="inline-flex h-9 w-9 items-center justify-center rounded-md text-fg-muted hover:bg-hover-glass hover:text-fg focus-visible:outline focus-visible:outline-2 focus-visible:outline-neon"
                >
                  <ChevronRight className="h-4 w-4" aria-hidden />
                </button>
              </div>

              <Button
                type="button"
                size="sm"
                variant="simple"
                onClick={goToday}
              >
                Hoy
              </Button>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <SegmentedControl
                ariaLabel="Rango del calendario"
                size="sm"
                value={period}
                onValueChange={(next) => {
                  setPeriod(next);
                  if (next === "week") {
                    setCursor((c) => startOfWeekMonday(c));
                  }
                }}
                options={[
                  { value: "day" as CalendarPeriod, label: "Día" },
                  { value: "week" as CalendarPeriod, label: "Semana" },
                  { value: "month" as CalendarPeriod, label: "Mes" },
                ]}
              />

              <SegmentedControl
                ariaLabel="Modo de vista"
                size="sm"
                value={displayMode}
                onValueChange={setDisplayMode}
                options={[
                  {
                    value: "calendar" as DisplayMode,
                    label: (
                      <>
                        <CalendarDays className="h-3.5 w-3.5" aria-hidden />
                        Calendario
                      </>
                    ),
                  },
                  {
                    value: "list" as DisplayMode,
                    label: (
                      <>
                        <List className="h-3.5 w-3.5" aria-hidden />
                        Lista
                      </>
                    ),
                  },
                ]}
              />

              {isAdmin ? (
                <Button size="sm" onClick={() => openNewPublication()}>
                  <Plus className="h-4 w-4" aria-hidden />
                  Nueva publicación
                </Button>
              ) : null}
            </div>
          </div>

          {/* State filter in List mode */}
          {displayMode === "list" ? (
            <SegmentedControl
              ariaLabel="Filtrar por estado"
              size="sm"
              value={stateFilter}
              onValueChange={setStateFilter}
              options={PUBLICATION_STATE_FILTERS}
            />
          ) : null}

          {/* Body */}
          {publicationsQuery.isLoading ? (
            <div className="rounded-md border border-glass bg-surface p-10 text-center text-sm text-fg-muted">
              Cargando publicaciones…
            </div>
          ) : publicationsQuery.isError ? (
            <div
              role="alert"
              className="rounded-md border border-glass bg-surface p-10 text-center text-sm text-danger"
            >
              No se pudieron cargar las publicaciones.
            </div>
          ) : displayMode === "list" ? (
            <PublicationsListView
              publications={publications}
              onSelectPublication={handleCardClick}
            />
          ) : period === "month" ? (
            <MonthGrid
              startDate={bounds.start}
              referenceMonth={cursor.getMonth()}
              todayKey={todayKey}
              publications={publications}
              isAdmin={isAdmin}
              expandedDays={expandedMonthDays}
              onExpandDay={(key) =>
                setExpandedMonthDays((prev) => {
                  const next = new Set(prev);
                  next.add(key);
                  return next;
                })
              }
              onCreateOnDay={(d) => {
                const slot = new Date(
                  d.getFullYear(),
                  d.getMonth(),
                  d.getDate(),
                  10,
                  0,
                  0,
                  0,
                );
                openNewPublication(slot);
              }}
              onSelectPublication={handleCardClick}
            />
          ) : (
            <HourlyCalendarGrid
              columns={buildDayColumns(
                bounds.start,
                period === "day" ? 1 : 7,
                publications,
              )}
              todayKey={todayKey}
              now={now}
              showNowLine={
                now.getTime() >= bounds.start.getTime() &&
                now.getTime() < bounds.end.getTime()
              }
              isAdmin={isAdmin}
              onCreateAtSlot={(dayDate, hour) => {
                const slot = new Date(
                  dayDate.getFullYear(),
                  dayDate.getMonth(),
                  dayDate.getDate(),
                  hour,
                  0,
                  0,
                  0,
                );
                openNewPublication(slot);
              }}
              onSelectPublication={handleCardClick}
            />
          )}
        </div>

        {/* Right channels panel (collapses on desktop, stacks below on mobile) */}
        <ChannelsPanel
          accountId={accountId}
          channels={channels}
          isLoading={channelsQuery.isLoading}
          isAdmin={isAdmin}
          selectedChannelId={selectedChannelId}
          onSelectChannel={setSelectedChannelId}
        />
      </div>

      {/* Editor Dialog */}
      <PublicationEditorDialog
        accountId={accountId}
        open={editorOpen}
        onClose={() => {
          setEditorOpen(false);
          setEditingPub(null);
          setPresetDate(null);
        }}
        channels={channels}
        isAdmin={isAdmin}
        initial={editingPub}
        defaultScheduledFor={presetDate}
        onOpenDetail={(pub) => {
          setEditorOpen(false);
          setEditingPub(null);
          setDetailPub(pub);
        }}
      />

      {/* Detail Dialog */}
      <PublicationDetailDialog
        accountId={accountId}
        publication={detailPub}
        open={detailPub !== null}
        onClose={() => setDetailPub(null)}
        isAdmin={isAdmin}
        onEdit={(pub) => {
          setDetailPub(null);
          setEditingPub(pub);
          setPresetDate(null);
          setEditorOpen(true);
        }}
      />
    </div>
  );
}

function PublicationCard({
  publication,
  onClick,
  compact = false,
  showTime = false,
}: {
  publication: Publication;
  onClick: (pub: Publication) => void;
  compact?: boolean;
  showTime?: boolean;
}) {
  const firstMedia = publication.media[0];
  const uniqueNetworks = Array.from(
    new Set(publication.targets.map((t) => t.channel.network)),
  );
  const dt = publicationTimestamp(publication);

  return (
    <button
      type="button"
      data-testid={`publication-card-${publication.id}`}
      onClick={(e) => {
        e.stopPropagation();
        onClick(publication);
      }}
      className={cn(
        "flex w-full items-start gap-2 rounded-md border border-glass bg-surface-2 text-left transition-colors hover:bg-hover-glass focus-visible:outline focus-visible:outline-2 focus-visible:outline-neon",
        compact ? "p-1.5 text-[11px]" : "p-2 text-xs",
      )}
    >
      {firstMedia ? (
        <div
          className={cn(
            "relative shrink-0 overflow-hidden rounded-sm border border-glass bg-field",
            compact ? "h-8 w-8" : "h-10 w-10",
          )}
        >
          {firstMedia.type === "video" ? (
            <>
              <video
                src={firstMedia.url}
                preload="metadata"
                muted
                className="h-full w-full object-cover"
              />
              <span className="absolute bottom-0.5 right-0.5 rounded-sm bg-backdrop/80 p-0.5 text-fg">
                <Film className="h-2.5 w-2.5" aria-hidden />
              </span>
            </>
          ) : (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={firstMedia.url}
              alt=""
              loading="lazy"
              className="h-full w-full object-cover"
            />
          )}
        </div>
      ) : null}

      <div className="min-w-0 flex-1 space-y-1">
        <div className="flex flex-wrap items-center justify-between gap-1">
          <div className="flex items-center gap-1">
            {showTime && dt ? (
              <span className="font-numeric font-semibold tabular-nums text-fg">
                {formatClockHHMM(dt)}
              </span>
            ) : null}
            {uniqueNetworks.map((net) => (
              <NetworkIcon key={net} network={net} />
            ))}
          </div>
          <PublicationStateBadge state={publication.state} />
        </div>
        <p className="line-clamp-2 break-words text-fg">
          {publicationPreviewWords(publication)}
        </p>
      </div>
    </button>
  );
}

function HourlyCalendarGrid({
  columns,
  todayKey,
  now,
  showNowLine,
  isAdmin,
  onCreateAtSlot,
  onSelectPublication,
}: {
  columns: CalendarDayColumn[];
  todayKey: string;
  now: Date;
  showNowLine: boolean;
  isAdmin: boolean;
  onCreateAtSlot: (dayDate: Date, hour: number) => void;
  onSelectPublication: (pub: Publication) => void;
}) {
  const nowMinutes = now.getHours() * 60 + now.getMinutes();
  const nowPct = (nowMinutes / 1440) * 100;

  return (
    <div
      data-testid="calendar-hourly-grid"
      className="overflow-x-auto rounded-md border border-glass bg-surface"
    >
      <div className="min-w-[680px]">
        {/* Day headers */}
        <div
          className="grid border-b border-glass bg-surface-2"
          style={{
            gridTemplateColumns: `64px repeat(${columns.length}, minmax(0, 1fr))`,
          }}
        >
          <div className="p-2" />
          {columns.map((col) => {
            const isToday = col.key === todayKey;
            return (
              <div
                key={col.key}
                className="flex flex-col items-center justify-center border-l border-glass px-2 py-2.5 text-center"
              >
                <span className="text-xs font-medium text-fg-muted">
                  {col.longName}
                </span>
                <span
                  className={cn(
                    "mt-0.5 inline-flex items-center gap-1 font-numeric text-xs font-semibold tabular-nums",
                    isToday ? "text-lit" : "text-fg",
                  )}
                >
                  {isToday ? (
                    <span
                      className="h-1.5 w-1.5 rounded-full bg-neon"
                      aria-hidden
                    />
                  ) : null}
                  {col.dateShort}
                </span>
              </div>
            );
          })}
        </div>

        {/* 24 hourly rows + "ahora" line */}
        <div className="relative max-h-[640px] overflow-y-auto">
          <div className="relative">
            {showNowLine ? (
              <div
                data-testid="calendar-now-line"
                style={{ top: `${nowPct}%` }}
                className="pointer-events-none absolute inset-x-0 z-20 flex items-center"
              >
                <span className="ml-1.5 rounded-sm bg-neon px-1.5 py-0.5 font-numeric text-[10px] font-semibold leading-none tabular-nums text-white">
                  {formatClockHHMM(now)}
                </span>
                <div className="h-[2px] flex-1 bg-neon" />
              </div>
            ) : null}

            {HOURS.map((hour) => (
              <div
                key={hour}
                className="grid border-b border-glass last:border-b-0"
                style={{
                  gridTemplateColumns: `64px repeat(${columns.length}, minmax(0, 1fr))`,
                }}
              >
                <div className="flex items-start justify-center px-2 py-3 font-numeric text-xs tabular-nums text-fg-muted">
                  {formatHourLabel(hour)}
                </div>

                {columns.map((col) => {
                  const slotItems = col.byHour.get(hour) ?? [];
                  return (
                    <div
                      key={`${col.key}-${hour}`}
                      data-testid={`slot-${col.key}-${hour}`}
                      data-day-key={col.key}
                      data-hour={hour}
                      aria-label={`${col.longName} ${col.dayNumber}, ${formatHourLabel(hour)}`}
                      onClick={() => {
                        if (isAdmin) onCreateAtSlot(col.date, hour);
                      }}
                      className={cn(
                        "min-h-14 space-y-1.5 border-l border-glass p-1.5 transition-colors",
                        isAdmin && "cursor-pointer hover:bg-hover-glass/60",
                      )}
                    >
                      {slotItems.map((pub) => (
                        <PublicationCard
                          key={pub.id}
                          publication={pub}
                          compact
                          onClick={onSelectPublication}
                        />
                      ))}
                    </div>
                  );
                })}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function MonthGrid({
  startDate,
  referenceMonth,
  todayKey,
  publications,
  isAdmin,
  expandedDays,
  onExpandDay,
  onCreateOnDay,
  onSelectPublication,
}: {
  startDate: Date;
  referenceMonth: number;
  todayKey: string;
  publications: Publication[];
  isAdmin: boolean;
  expandedDays: Set<string>;
  onExpandDay: (key: string) => void;
  onCreateOnDay: (date: Date) => void;
  onSelectPublication: (pub: Publication) => void;
}) {
  const cells = buildDayColumns(startDate, 42, publications, referenceMonth);

  return (
    <div
      data-testid="calendar-month-grid"
      className="overflow-x-auto rounded-md border border-glass bg-surface"
    >
      <div className="min-w-[680px]">
        <div className="grid grid-cols-7 border-b border-glass bg-surface-2">
          {SHORT_WEEKDAYS.map((wd) => (
            <div
              key={wd}
              className="border-l border-glass px-2 py-2 text-center text-[11px] font-medium uppercase tracking-[0.08em] text-fg-muted first:border-l-0"
            >
              {wd}
            </div>
          ))}
        </div>

        <div className="grid grid-cols-7">
          {cells.map((cell, idx) => {
            const isToday = cell.key === todayKey;
            const expanded = expandedDays.has(cell.key);
            const visibleItems = expanded
              ? cell.items
              : cell.items.slice(0, MONTH_MAX_VISIBLE);
            const overflowCount = cell.items.length - visibleItems.length;

            return (
              <div
                key={cell.key}
                data-testid={`month-day-${cell.key}`}
                data-day-key={cell.key}
                onClick={() => {
                  if (isAdmin) onCreateOnDay(cell.date);
                }}
                className={cn(
                  "min-h-28 space-y-1.5 border-b border-l border-glass p-2 transition-colors",
                  idx % 7 === 0 && "border-l-0",
                  !cell.inCurrentMonth && "bg-field/40 opacity-65",
                  isAdmin && "cursor-pointer hover:bg-hover-glass/50",
                )}
              >
                <div className="flex items-center justify-between">
                  <span
                    className={cn(
                      "font-numeric text-xs font-semibold tabular-nums",
                      isToday
                        ? "rounded-pill bg-focused px-2 py-0.5 text-lit"
                        : "text-fg",
                    )}
                  >
                    {cell.dayNumber}
                  </span>
                </div>

                <div className="space-y-1">
                  {visibleItems.map((pub) => (
                    <PublicationCard
                      key={pub.id}
                      publication={pub}
                      compact
                      showTime
                      onClick={onSelectPublication}
                    />
                  ))}
                  {overflowCount > 0 ? (
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        onExpandDay(cell.key);
                      }}
                      className="w-full rounded-sm px-1.5 py-0.5 text-left font-numeric text-[11px] font-medium tabular-nums text-lit hover:bg-hover-glass"
                    >
                      +{overflowCount} más
                    </button>
                  ) : null}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

function PublicationsListView({
  publications,
  onSelectPublication,
}: {
  publications: Publication[];
  onSelectPublication: (pub: Publication) => void;
}) {
  const groups = groupPublicationsByLocalDay(publications);

  if (groups.length === 0) {
    return (
      <div className="rounded-md border border-glass bg-surface p-10 text-center text-sm text-fg-muted">
        No hay publicaciones en este período.
      </div>
    );
  }

  return (
    <div className="space-y-4" data-testid="calendar-list-view">
      {groups.map((grp) => (
        <section
          key={grp.key}
          className="overflow-hidden rounded-md border border-glass bg-surface"
        >
          <header className="border-b border-glass bg-surface-2 px-4 py-2 text-xs font-medium text-fg">
            {grp.heading}
          </header>
          <div className="space-y-2 p-3">
            {grp.items.map((pub) => (
              <PublicationCard
                key={pub.id}
                publication={pub}
                showTime
                onClick={onSelectPublication}
              />
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}
