"use client";

import { Plus } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import {
  formatClockHHMM,
  formatHourLabel,
  shortWeekdayNames,
} from "@/components/publications/calendar-utils";
import type { Appointment } from "@/lib/api/appointments";
import { DEFAULT_LOCALE, type Locale } from "@/lib/i18n/config";
import { useLocale, useT } from "@/lib/i18n/provider";
import { cn } from "@/lib/utils";

import { APPOINTMENT_STATUS_META } from "./status-badge";
import { addDaysLocal, formatLocalDateKey, weekdayName } from "./week-utils";

/** The Agenda's day/week/month grids, laid out like the publications
 *  Calendario: hourly rows with a "now" line, or a six-week month. */

const HOURS = Array.from({ length: 24 }, (_, i) => i);
const MONTH_MAX_VISIBLE = 3;

export type AgendaDay = {
  date: Date;
  key: string;
  longName: string;
  dayNumber: number;
  dateShort: string;
  inCurrentMonth: boolean;
  byHour: Map<number, Appointment[]>;
  items: Appointment[];
};

export function buildAgendaDays(
  start: Date,
  numDays: number,
  appointments: Appointment[],
  referenceMonth?: number,
  locale: Locale = DEFAULT_LOCALE,
): AgendaDay[] {
  const days: AgendaDay[] = [];
  const byKey = new Map<string, AgendaDay>();
  for (let i = 0; i < numDays; i++) {
    const d = addDaysLocal(start, i);
    const day: AgendaDay = {
      date: d,
      key: formatLocalDateKey(d),
      longName: weekdayName(d, "long", locale),
      dayNumber: d.getDate(),
      dateShort: `${String(d.getDate()).padStart(2, "0")}/${String(d.getMonth() + 1).padStart(2, "0")}`,
      inCurrentMonth: referenceMonth === undefined || d.getMonth() === referenceMonth,
      byHour: new Map(),
      items: [],
    };
    days.push(day);
    byKey.set(day.key, day);
  }
  const sorted = [...appointments].sort(
    (a, b) => new Date(a.starts_at).getTime() - new Date(b.starts_at).getTime(),
  );
  for (const appt of sorted) {
    const at = new Date(appt.starts_at);
    if (Number.isNaN(at.getTime())) continue;
    const day = byKey.get(formatLocalDateKey(at));
    if (!day) continue;
    day.items.push(appt);
    const list = day.byHour.get(at.getHours()) ?? [];
    list.push(appt);
    day.byHour.set(at.getHours(), list);
  }
  return days;
}

function contactName(appt: Appointment): string | null {
  return (
    appt.contact?.name?.trim() ||
    appt.contact?.email?.trim() ||
    appt.contact?.phone_number?.trim() ||
    null
  );
}

function AppointmentCard({
  appointment,
  onClick,
  showTime = false,
}: {
  appointment: Appointment;
  onClick: (appt: Appointment) => void;
  showTime?: boolean;
}) {
  const t = useT();
  const meta = APPOINTMENT_STATUS_META[appointment.status] ?? APPOINTMENT_STATUS_META.scheduled;
  const Icon = meta.icon;
  const who = contactName(appointment);
  return (
    <button
      type="button"
      data-testid={`appointment-card-${appointment.id}`}
      title={t(meta.label)}
      onClick={(e) => {
        e.stopPropagation();
        onClick(appointment);
      }}
      className={cn(
        "flex w-full items-start gap-1.5 rounded-md border border-glass bg-surface-2 p-1.5 text-left text-[11px] transition-colors hover:bg-hover-glass focus-visible:outline focus-visible:outline-2 focus-visible:outline-neon",
        appointment.status === "cancelled" && "opacity-60",
      )}
    >
      <span className={cn("mt-px grid h-4 w-4 shrink-0 place-items-center rounded-full", meta.className)}>
        <Icon className="h-2.5 w-2.5" aria-hidden />
      </span>
      <span className="min-w-0 flex-1">
        <span className="flex items-center gap-1">
          {showTime ? (
            <span className="font-numeric font-semibold tabular-nums text-fg">
              {formatClockHHMM(new Date(appointment.starts_at))}
            </span>
          ) : null}
          <span
            className={cn(
              "truncate font-medium text-fg",
              appointment.status === "cancelled" && "line-through",
            )}
          >
            {appointment.title}
          </span>
        </span>
        {who ? <span className="block truncate text-fg-muted">{who}</span> : null}
      </span>
    </button>
  );
}

export function AgendaHourlyGrid({
  days,
  todayKey,
  now,
  showNowLine,
  onCreateAt,
  onSelect,
}: {
  days: AgendaDay[];
  todayKey: string;
  now: Date;
  showNowLine: boolean;
  onCreateAt: (date: Date, hour: number) => void;
  onSelect: (appt: Appointment) => void;
}) {
  const t = useT();
  const nowPct = ((now.getHours() * 60 + now.getMinutes()) / 1440) * 100;

  // Opens with the "now" line (or 8:00, for another week) near the top
  // third; once the person scrolls, it stays where they left it.
  const scrollerRef = useRef<HTMLDivElement>(null);
  const userMovedRef = useRef(false);
  const [openedAtPct] = useState(nowPct);
  const firstKey = days[0]?.key;
  useEffect(() => {
    userMovedRef.current = false;
  }, [firstKey]);
  useEffect(() => {
    const el = scrollerRef.current;
    if (!el || userMovedRef.current) return;
    const pct = showNowLine ? openedAtPct : (8 / 24) * 100;
    el.scrollTop = (pct / 100) * el.scrollHeight - el.clientHeight / 3;
  }, [days, showNowLine, openedAtPct]);
  const markMoved = () => {
    userMovedRef.current = true;
  };
  const gridTemplateColumns = `64px repeat(${days.length}, minmax(0, 1fr))`;

  return (
    <div data-testid="agenda-hourly-grid" className="overflow-x-auto rounded-md border border-glass bg-surface">
      <div className="min-w-[680px]">
        <div
          ref={scrollerRef}
          onWheel={markMoved}
          onTouchStart={markMoved}
          onPointerDown={markMoved}
          onKeyDown={markMoved}
          style={{ scrollbarGutter: "stable" }}
          className="relative max-h-[640px] overflow-y-auto"
        >
          <div
            className="sticky top-0 z-30 grid border-b border-glass bg-surface-2"
            style={{ gridTemplateColumns }}
          >
            <div className="p-2" />
            {days.map((day) => {
              const isToday = day.key === todayKey;
              return (
                <div
                  key={day.key}
                  className="flex flex-col items-center justify-center border-l border-glass px-2 py-2.5 text-center"
                >
                  <span className="text-xs font-medium text-fg-muted">{day.longName}</span>
                  <span
                    className={cn(
                      "mt-0.5 inline-flex items-center gap-1 font-numeric text-xs font-semibold tabular-nums",
                      isToday ? "text-lit" : "text-fg",
                    )}
                  >
                    {isToday ? <span className="h-1.5 w-1.5 rounded-full bg-neon" aria-hidden /> : null}
                    {day.dateShort}
                  </span>
                </div>
              );
            })}
          </div>

          <div className="relative">
            {showNowLine ? (
              <div
                data-testid="agenda-now-line"
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
                style={{ gridTemplateColumns }}
              >
                <div className="flex items-start justify-center px-2 py-3 font-numeric text-xs tabular-nums text-fg-muted">
                  {formatHourLabel(hour)}
                </div>
                {days.map((day) => {
                  const items = day.byHour.get(hour) ?? [];
                  const label = t("agenda.newAt", {
                    day: day.longName,
                    date: day.dayNumber,
                    time: formatHourLabel(hour),
                  });
                  return (
                    <div
                      key={`${day.key}-${hour}`}
                      data-testid={`agenda-slot-${day.key}-${hour}`}
                      aria-label={label}
                      onClick={() => onCreateAt(day.date, hour)}
                      className="min-h-14 cursor-pointer space-y-1.5 border-l border-glass p-1.5 transition-colors hover:bg-hover-glass"
                    >
                      {items.map((appt) => (
                        <AppointmentCard key={appt.id} appointment={appt} onClick={onSelect} />
                      ))}
                      {items.length > 0 ? (
                        <button
                          type="button"
                          aria-label={label}
                          onClick={(e) => {
                            e.stopPropagation();
                            onCreateAt(day.date, hour);
                          }}
                          className="flex w-full items-center justify-center gap-1 rounded-sm px-1.5 py-0.5 text-[11px] font-medium text-fg-muted hover:bg-hover-glass hover:text-lit"
                        >
                          <Plus className="h-3 w-3" aria-hidden />
                          {t("publications.calendar.add")}
                        </button>
                      ) : null}
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

export function AgendaMonthGrid({
  days,
  todayKey,
  onCreateOn,
  onSelect,
}: {
  days: AgendaDay[];
  todayKey: string;
  onCreateOn: (date: Date) => void;
  onSelect: (appt: Appointment) => void;
}) {
  const t = useT();
  const locale = useLocale();
  const [expanded, setExpanded] = useState<Set<string>>(() => new Set());

  return (
    <div data-testid="agenda-month-grid" className="overflow-x-auto rounded-md border border-glass bg-surface">
      <div className="min-w-[680px]">
        <div className="grid grid-cols-7 border-b border-glass bg-surface-2">
          {shortWeekdayNames(locale).map((wd) => (
            <div
              key={wd}
              className="border-l border-glass px-2 py-2 text-center text-[11px] font-medium uppercase tracking-[0.08em] text-fg-muted first:border-l-0"
            >
              {wd}
            </div>
          ))}
        </div>
        <div className="grid grid-cols-7">
          {days.map((day, idx) => {
            const isToday = day.key === todayKey;
            const visible = expanded.has(day.key) ? day.items : day.items.slice(0, MONTH_MAX_VISIBLE);
            const overflow = day.items.length - visible.length;
            return (
              <div
                key={day.key}
                data-testid={`agenda-month-day-${day.key}`}
                onClick={() => onCreateOn(day.date)}
                className={cn(
                  "min-h-28 cursor-pointer space-y-1.5 border-b border-l border-glass p-2 transition-colors hover:bg-hover-glass",
                  idx % 7 === 0 && "border-l-0",
                  !day.inCurrentMonth && "bg-field opacity-65",
                )}
              >
                <span
                  className={cn(
                    "font-numeric text-xs font-semibold tabular-nums",
                    isToday ? "rounded-pill bg-focused px-2 py-0.5 text-lit" : "text-fg",
                  )}
                >
                  {day.dayNumber}
                </span>
                <div className="space-y-1">
                  {visible.map((appt) => (
                    <AppointmentCard key={appt.id} appointment={appt} onClick={onSelect} showTime />
                  ))}
                  {overflow > 0 ? (
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        setExpanded((prev) => new Set(prev).add(day.key));
                      }}
                      className="w-full rounded-sm px-1.5 py-0.5 text-left font-numeric text-[11px] font-medium tabular-nums text-lit hover:bg-hover-glass"
                    >
                      {t("publications.calendar.more", { count: overflow })}
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
