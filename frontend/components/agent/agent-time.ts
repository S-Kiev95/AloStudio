import type { AgentPendingAction } from "@/lib/api/agent";

const WEEKDAYS_SHORT_LOWER = [
  "dom",
  "lun",
  "mar",
  "mié",
  "jue",
  "vie",
  "sáb",
] as const;

const MONTHS_SHORT_LOWER = [
  "ene",
  "feb",
  "mar",
  "abr",
  "may",
  "jun",
  "jul",
  "ago",
  "sep",
  "oct",
  "nov",
  "dic",
] as const;

/** Short relative label in browser local time for an ISO 8601 timestamp. */
export function formatRelativeIso(iso: string | null | undefined): string {
  if (!iso) return "";
  const dt = new Date(iso);
  const ms = dt.getTime();
  if (Number.isNaN(ms)) return "";

  const diffSec = Math.round((Date.now() - ms) / 1000);
  if (diffSec < 60) return "ahora";
  const min = Math.round(diffSec / 60);
  if (min < 60) return `hace ${min}m`;
  const hr = Math.round(min / 60);
  if (hr < 24) return `hace ${hr}h`;
  const day = Math.round(hr / 24);
  if (day < 7) return `hace ${day}d`;

  return `${dt.getDate()} ${MONTHS_SHORT_LOWER[dt.getMonth()]}`;
}

/** Local clock time (HH:MM) for an ISO 8601 timestamp. */
export function formatLocalClock(iso: string | null | undefined): string {
  if (!iso) return "";
  const dt = new Date(iso);
  if (Number.isNaN(dt.getTime())) return "";
  const hh = String(dt.getHours()).padStart(2, "0");
  const mm = String(dt.getMinutes()).padStart(2, "0");
  return `${hh}:${mm}`;
}

/**
 * Schedule / cancellation summary line for ``PendingActionCard`` in the
 * browser's local timezone (e.g. ``"Sale el lun 2 nov, 10:00"``).
 */
export function formatPendingSchedule(
  action: Pick<AgentPendingAction, "tool" | "publication">,
): string {
  if (action.tool === "cancel_publication") {
    return "Se va a borrar esta publicación";
  }
  const iso = action.publication.scheduled_for;
  if (!iso) {
    return "Sale en los próximos minutos";
  }
  const dt = new Date(iso);
  if (Number.isNaN(dt.getTime())) {
    return "Sale en los próximos minutos";
  }
  const wd = WEEKDAYS_SHORT_LOWER[dt.getDay()];
  const day = dt.getDate();
  const mon = MONTHS_SHORT_LOWER[dt.getMonth()];
  const hh = String(dt.getHours()).padStart(2, "0");
  const mm = String(dt.getMinutes()).padStart(2, "0");
  return `Sale el ${wd} ${day} ${mon}, ${hh}:${mm}`;
}
