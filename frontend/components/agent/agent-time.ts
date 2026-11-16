import type { AgentPendingAction } from "@/lib/api/agent";
import { DEFAULT_LOCALE, INTL_TAGS, type Locale } from "@/lib/i18n/config";
import { createTranslate } from "@/lib/i18n/translate";

// i18n-ignore-start: Spanish short names; other languages use Intl below.

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
// i18n-ignore-end

/** Short relative label in browser local time for an ISO 8601 timestamp. */
export function formatRelativeIso(
  iso: string | null | undefined,
  locale: Locale = DEFAULT_LOCALE,
): string {
  if (!iso) return "";
  const dt = new Date(iso);
  const ms = dt.getTime();
  if (Number.isNaN(ms)) return "";
  const t = createTranslate(locale);

  const diffSec = Math.round((Date.now() - ms) / 1000);
  if (diffSec < 60) return t("time.now");
  const min = Math.round(diffSec / 60);
  if (min < 60) return t("time.minutesAgo", { n: min });
  const hr = Math.round(min / 60);
  if (hr < 24) return t("time.hoursAgo", { n: hr });
  const day = Math.round(hr / 24);
  if (day < 7) return t("time.daysAgo", { n: day });

  if (locale !== "es") {
    return dt.toLocaleDateString(INTL_TAGS[locale], { day: "numeric", month: "short" });
  }
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
  locale: Locale = DEFAULT_LOCALE,
): string {
  const t = createTranslate(locale);
  if (action.tool === "cancel_publication") {
    return t("agent.pending.willDelete");
  }
  const iso = action.publication.scheduled_for;
  if (!iso) {
    return t("agent.pending.soon");
  }
  const dt = new Date(iso);
  if (Number.isNaN(dt.getTime())) {
    return t("agent.pending.soon");
  }
  const hh = String(dt.getHours()).padStart(2, "0");
  const mm = String(dt.getMinutes()).padStart(2, "0");
  const when =
    locale === "es"
      ? `${WEEKDAYS_SHORT_LOWER[dt.getDay()]} ${dt.getDate()} ${MONTHS_SHORT_LOWER[dt.getMonth()]}, ${hh}:${mm}`
      : new Intl.DateTimeFormat(INTL_TAGS[locale], {
          weekday: "short",
          day: "numeric",
          month: "short",
          hour: "2-digit",
          minute: "2-digit",
          hour12: false,
        }).format(dt);
  return t("agent.pending.at", { when });
}
