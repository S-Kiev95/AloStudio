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

function dayPeriod(hour: number): string {
  if (hour < 6) return "de la madrugada";
  if (hour < 12) return "de la mañana";
  if (hour < 20) return "de la tarde";
  return "de la noche";
}

function relativeFromNow(minutes: number): string {
  if (minutes < 1) return "en menos de un minuto";
  if (minutes < 60) return minutes === 1 ? "en 1 minuto" : `en ${minutes} minutos`;
  const hours = Math.round(minutes / 60);
  if (hours < 48) return hours === 1 ? "en 1 hora" : `en ${hours} horas`;
  return `en ${Math.round(hours / 24)} días`;
}

/**
 * Spell out a `YYYY-MM-DDTHH:mm` value, e.g. "Se publica hoy, lunes 2/11, a
 * las 02:00 de la madrugada (en 1 hora)", so a 24h time can't be misread.
 */
export function describeScheduledFor(
  value: string,
  now: Date = new Date(),
): { text: string; past: boolean } | null {
  if (!value.trim()) return null;
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return null;
  const weekday = new Intl.DateTimeFormat("es-ES", { weekday: "long" }).format(d);
  const dayDiff = Math.round(
    (new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime() -
      new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime()) /
      86_400_000,
  );
  const dayWord = dayDiff === 0 ? "hoy, " : dayDiff === 1 ? "mañana, " : "el ";
  const hour = d.getHours();
  const when = `${dayWord}${weekday} ${d.getDate()}/${d.getMonth() + 1}, ${hour === 1 ? "a la" : "a las"} ${pad2(hour)}:${pad2(d.getMinutes())} ${dayPeriod(hour)}`;
  const minutes = Math.floor((d.getTime() - now.getTime()) / 60_000);
  if (minutes < 0) return { text: `Esa hora ya pasó: ${when}.`, past: true };
  return { text: `Se publica ${when} (${relativeFromNow(minutes)}).`, past: false };
}
