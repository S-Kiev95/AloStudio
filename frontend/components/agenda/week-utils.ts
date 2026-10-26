import type { Appointment } from "@/lib/api/appointments";

const SHORT_WEEKDAYS = [
  "Lun",
  "Mar",
  "Mié",
  "Jue",
  "Vie",
  "Sáb",
  "Dom",
] as const;

const LONG_WEEKDAYS = [
  "Lunes",
  "Martes",
  "Miércoles",
  "Jueves",
  "Viernes",
  "Sábado",
  "Domingo",
] as const;

/** Local midnight on Monday of the week containing `date`. */
export function startOfWeekMonday(date: Date): Date {
  const day = date.getDay(); // 0 = Sun, 1 = Mon ... 6 = Sat
  const diff = day === 0 ? -6 : 1 - day;
  return new Date(
    date.getFullYear(),
    date.getMonth(),
    date.getDate() + diff,
    0,
    0,
    0,
    0,
  );
}

/** Add `days` in local calendar arithmetic (safe across DST boundaries). */
export function addDaysLocal(date: Date, days: number): Date {
  return new Date(
    date.getFullYear(),
    date.getMonth(),
    date.getDate() + days,
    0,
    0,
    0,
    0,
  );
}

/** Exclusive end of the week (Monday 00:00 of the next week). */
export function endOfWeekExclusive(weekStart: Date): Date {
  return addDaysLocal(weekStart, 7);
}

function pad2(n: number): string {
  return String(n).padStart(2, "0");
}

/** Local YYYY-MM-DD key in the browser's timezone. */
export function formatLocalDateKey(date: Date): string {
  return `${date.getFullYear()}-${pad2(date.getMonth() + 1)}-${pad2(date.getDate())}`;
}

export type DayBucket = {
  date: Date;
  key: string;
  shortName: string;
  longName: string;
  dayNumber: number;
  monthShort: string;
  items: Appointment[];
};

/** Build 7 day buckets (Monday to Sunday) and place appointments by local date. */
export function groupAppointmentsByDay(
  weekStart: Date,
  appointments: Appointment[],
): DayBucket[] {
  const monday = startOfWeekMonday(weekStart);
  const buckets: DayBucket[] = [];
  const byKey = new Map<string, DayBucket>();

  for (let i = 0; i < 7; i++) {
    const d = addDaysLocal(monday, i);
    const key = formatLocalDateKey(d);
    const bucket: DayBucket = {
      date: d,
      key,
      shortName: SHORT_WEEKDAYS[i],
      longName: LONG_WEEKDAYS[i],
      dayNumber: d.getDate(),
      monthShort: d.toLocaleDateString("es-ES", { month: "short" }),
      items: [],
    };
    buckets.push(bucket);
    byKey.set(key, bucket);
  }

  const sorted = [...appointments].sort(
    (a, b) => new Date(a.starts_at).getTime() - new Date(b.starts_at).getTime(),
  );

  for (const appt of sorted) {
    const dt = new Date(appt.starts_at);
    if (Number.isNaN(dt.getTime())) continue;
    const bucket = byKey.get(formatLocalDateKey(dt));
    if (bucket) {
      bucket.items.push(appt);
    }
  }

  return buckets;
}

export function formatWeekRangeLabel(weekStart: Date): string {
  const monday = startOfWeekMonday(weekStart);
  const sunday = addDaysLocal(monday, 6);
  const fmtDayMonth = new Intl.DateTimeFormat("es-ES", {
    day: "numeric",
    month: "short",
  });
  return `${fmtDayMonth.format(monday)} – ${fmtDayMonth.format(sunday)} ${sunday.getFullYear()}`;
}

export function formatTimeRange(
  startsAt: string,
  endsAt: string | null,
): string {
  const start = new Date(startsAt);
  if (Number.isNaN(start.getTime())) return "";
  const fmt = new Intl.DateTimeFormat("es-ES", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
  if (!endsAt) return fmt.format(start);
  const end = new Date(endsAt);
  if (Number.isNaN(end.getTime())) return fmt.format(start);
  return `${fmt.format(start)} – ${fmt.format(end)}`;
}

export function formatDateTimeLocal(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleString("es-ES", {
    weekday: "short",
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

/** Format a Date or ISO string into `YYYY-MM-DDTHH:mm` in local browser time. */
export function toDatetimeLocalInput(
  value?: string | Date | null,
): string {
  if (!value) return "";
  const d = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(d.getTime())) return "";
  return `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}T${pad2(d.getHours())}:${pad2(d.getMinutes())}`;
}

/** Convert `YYYY-MM-DDTHH:mm` in local browser time into an ISO 8601 string. */
export function fromDatetimeLocalInput(value: string): string | null {
  const trimmed = value.trim();
  if (!trimmed) return null;
  const d = new Date(trimmed);
  if (Number.isNaN(d.getTime())) return null;
  return d.toISOString();
}
