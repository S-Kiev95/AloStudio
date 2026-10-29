import {
  addDaysLocal,
  endOfWeekExclusive,
  formatLocalDateKey,
  formatWeekRangeLabel,
  startOfWeekMonday,
} from "@/components/agenda/week-utils";
import type { Publication } from "@/lib/api/publications";

export {
  addDaysLocal,
  endOfWeekExclusive,
  formatLocalDateKey,
  formatWeekRangeLabel,
  startOfWeekMonday,
};

export const SHORT_WEEKDAYS = [
  "Lun",
  "Mar",
  "Mié",
  "Jue",
  "Vie",
  "Sáb",
  "Dom",
] as const;

export const LONG_WEEKDAYS = [
  "Lunes",
  "Martes",
  "Miércoles",
  "Jueves",
  "Viernes",
  "Sábado",
  "Domingo",
] as const;

export type CalendarPeriod = "day" | "week" | "month";

export function startOfLocalDay(date: Date): Date {
  return new Date(
    date.getFullYear(),
    date.getMonth(),
    date.getDate(),
    0,
    0,
    0,
    0,
  );
}

export function startOfLocalMonth(date: Date): Date {
  return new Date(date.getFullYear(), date.getMonth(), 1, 0, 0, 0, 0);
}

export function addMonthsLocal(date: Date, months: number): Date {
  return new Date(date.getFullYear(), date.getMonth() + months, 1, 0, 0, 0, 0);
}

/**
 * Effective timestamp used to position a publication on the calendar:
 * ``scheduled_for`` when present, falling back to ``created_at`` for unscheduled drafts.
 */
export function publicationTimestamp(pub: Publication): Date | null {
  const raw = pub.scheduled_for ?? pub.created_at;
  if (!raw) return null;
  const dt = new Date(raw);
  return Number.isNaN(dt.getTime()) ? null : dt;
}

export function publicationPreviewWords(
  pub: Publication,
  maxWords = 10,
): string {
  const raw =
    pub.content?.trim() ||
    pub.targets.find((t) => t.content_override?.trim())?.content_override?.trim() ||
    "";
  if (!raw) return "Sin texto";
  const words = raw.split(/\s+/);
  if (words.length <= maxWords) return words.join(" ");
  return `${words.slice(0, maxWords).join(" ")}…`;
}

export function formatHourLabel(hour: number): string {
  return `${hour}:00`;
}

export function formatClockHHMM(date: Date): string {
  const hh = String(date.getHours()).padStart(2, "0");
  const mm = String(date.getMinutes()).padStart(2, "0");
  return `${hh}:${mm}`;
}

export function formatCalendarRangeLabel(
  period: CalendarPeriod,
  cursor: Date,
): string {
  if (period === "week") {
    return formatWeekRangeLabel(cursor);
  }
  if (period === "day") {
    return cursor.toLocaleDateString("es-ES", {
      weekday: "short",
      day: "numeric",
      month: "short",
      year: "numeric",
    });
  }
  const monthLabel = cursor.toLocaleDateString("es-ES", {
    month: "long",
    year: "numeric",
  });
  return monthLabel.charAt(0).toUpperCase() + monthLabel.slice(1);
}

export function computePeriodBounds(
  period: CalendarPeriod,
  cursor: Date,
): { start: Date; end: Date } {
  if (period === "day") {
    const start = startOfLocalDay(cursor);
    return { start, end: addDaysLocal(start, 1) };
  }
  if (period === "week") {
    const start = startOfWeekMonday(cursor);
    return { start, end: endOfWeekExclusive(start) };
  }
  // 6-week grid starting Monday of the week containing the 1st of the month.
  const firstOfMonth = startOfLocalMonth(cursor);
  const start = startOfWeekMonday(firstOfMonth);
  return { start, end: addDaysLocal(start, 42) };
}

export type CalendarDayColumn = {
  date: Date;
  key: string;
  shortName: string;
  longName: string;
  dayNumber: number;
  dateShort: string;
  inCurrentMonth: boolean;
  byHour: Map<number, Publication[]>;
  items: Publication[];
};

function sortPublications(items: Publication[]): Publication[] {
  return [...items].sort((a, b) => {
    const ta = publicationTimestamp(a)?.getTime() ?? 0;
    const tb = publicationTimestamp(b)?.getTime() ?? 0;
    return ta - tb;
  });
}

function weekdayIndexMondayFirst(date: Date): number {
  const day = date.getDay(); // 0 = Sun
  return day === 0 ? 6 : day - 1;
}

export function buildDayColumns(
  startDate: Date,
  numDays: number,
  publications: Publication[],
  referenceMonth?: number,
): CalendarDayColumn[] {
  const cols: CalendarDayColumn[] = [];
  const byKey = new Map<string, CalendarDayColumn>();

  for (let i = 0; i < numDays; i++) {
    const d = addDaysLocal(startDate, i);
    const key = formatLocalDateKey(d);
    const wd = weekdayIndexMondayFirst(d);
    const col: CalendarDayColumn = {
      date: d,
      key,
      shortName: SHORT_WEEKDAYS[wd],
      longName: LONG_WEEKDAYS[wd],
      dayNumber: d.getDate(),
      dateShort: `${String(d.getDate()).padStart(2, "0")}/${String(d.getMonth() + 1).padStart(2, "0")}`,
      inCurrentMonth:
        referenceMonth === undefined || d.getMonth() === referenceMonth,
      byHour: new Map(),
      items: [],
    };
    cols.push(col);
    byKey.set(key, col);
  }

  for (const pub of sortPublications(publications)) {
    const dt = publicationTimestamp(pub);
    if (!dt) continue;
    const col = byKey.get(formatLocalDateKey(dt));
    if (!col) continue;
    col.items.push(pub);
    const hr = dt.getHours();
    const list = col.byHour.get(hr) ?? [];
    list.push(pub);
    col.byHour.set(hr, list);
  }

  return cols;
}

export type DayListGroup = {
  key: string;
  date: Date;
  heading: string;
  items: Publication[];
};

export function groupPublicationsByLocalDay(
  publications: Publication[],
): DayListGroup[] {
  const map = new Map<string, DayListGroup>();
  for (const pub of sortPublications(publications)) {
    const dt = publicationTimestamp(pub);
    if (!dt) continue;
    const key = formatLocalDateKey(dt);
    let grp = map.get(key);
    if (!grp) {
      const dayStart = startOfLocalDay(dt);
      const rawHeading = dayStart.toLocaleDateString("es-ES", {
        weekday: "long",
        day: "numeric",
        month: "long",
      });
      grp = {
        key,
        date: dayStart,
        heading: rawHeading.charAt(0).toUpperCase() + rawHeading.slice(1),
        items: [],
      };
      map.set(key, grp);
    }
    grp.items.push(pub);
  }
  return Array.from(map.values());
}
