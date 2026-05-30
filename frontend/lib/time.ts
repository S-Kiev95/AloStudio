/** Relative time from a unix-seconds timestamp (backend emits seconds). */
export function relativeTime(unixSeconds: number | null | undefined): string {
  if (!unixSeconds) return "";
  const diffMs = Date.now() - unixSeconds * 1000;
  const sec = Math.round(diffMs / 1000);
  if (sec < 60) return "ahora";
  const min = Math.round(sec / 60);
  if (min < 60) return `hace ${min}m`;
  const hr = Math.round(min / 60);
  if (hr < 24) return `hace ${hr}h`;
  const day = Math.round(hr / 24);
  if (day < 7) return `hace ${day}d`;
  return new Date(unixSeconds * 1000).toLocaleDateString();
}

/** Clock time (HH:MM) for message bubbles. */
export function clockTime(unixSeconds: number | null | undefined): string {
  if (!unixSeconds) return "";
  return new Date(unixSeconds * 1000).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  });
}

/**
 * Human duration from a number of seconds (report averages). Returns "—"
 * for 0/empty, since the backend emits 0 when no events matched.
 */
export function formatDuration(seconds: number | null | undefined): string {
  if (!seconds || seconds <= 0) return "—";
  const s = Math.round(seconds);
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  if (m < 60) {
    const rem = s % 60;
    return rem ? `${m}m ${rem}s` : `${m}m`;
  }
  const h = Math.floor(m / 60);
  const remM = m % 60;
  if (h < 24) return remM ? `${h}h ${remM}m` : `${h}h`;
  const d = Math.floor(h / 24);
  const remH = h % 24;
  return remH ? `${d}d ${remH}h` : `${d}d`;
}

/** Short date label (e.g. "12 may") for chart axes from unix seconds. */
export function shortDate(unixSeconds: number | null | undefined): string {
  if (!unixSeconds) return "";
  return new Date(unixSeconds * 1000).toLocaleDateString(undefined, {
    day: "numeric",
    month: "short",
  });
}
