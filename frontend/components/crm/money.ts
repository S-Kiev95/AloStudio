/** ``1200.5`` + ``"UYU"`` → ``"$ 1.200,50"`` in the panel's language. A
 *  currency code ``Intl`` doesn't know is written after the number. */
export function formatMoney(value: number, currency: string | null, intlTag: string): string {
  if (currency) {
    try {
      return new Intl.NumberFormat(intlTag, {
        style: "currency",
        currency,
        maximumFractionDigits: 2,
      }).format(value);
    } catch {
      // Not an ISO 4217 code: fall through.
    }
  }
  const n = new Intl.NumberFormat(intlTag, { maximumFractionDigits: 2 }).format(value);
  return currency ? `${n} ${currency}` : n;
}

/** Totals per currency, for a column header: ``"$ 3.000 · US$ 200"``. */
export function formatTotals(
  items: { value: number | null; currency: string | null }[],
  intlTag: string,
): string | null {
  const sums = new Map<string, number>();
  for (const it of items) {
    if (it.value == null) continue;
    const key = it.currency ?? "";
    sums.set(key, (sums.get(key) ?? 0) + it.value);
  }
  if (sums.size === 0) return null;
  return [...sums.entries()]
    .map(([cur, v]) => formatMoney(v, cur || null, intlTag))
    .join(" · ");
}
