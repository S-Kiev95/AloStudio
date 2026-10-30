/**
 * ``value`` when it is a path inside this app, otherwise ``null``. A
 * ``next`` taken from the URL must never send someone to another site
 * (``//evil.example`` and ``/\evil.example`` are other sites to a browser).
 */
export function safeNextPath(value: string | null | undefined): string | null {
  if (!value || !value.startsWith("/")) return null;
  if (value.startsWith("//") || value.startsWith("/\\")) return null;
  return value;
}
