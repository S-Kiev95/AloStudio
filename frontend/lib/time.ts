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
