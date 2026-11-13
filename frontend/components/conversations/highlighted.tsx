/** Wraps the backend's `[start, end)` spans in `<mark>`. The spans are
 *  offsets into this exact text, so no matching is redone here — the
 *  search folds accents and case, and redoing it in the browser would mark
 *  different letters than the ones it matched. */
export function Highlighted({
  text,
  spans,
}: {
  text: string;
  spans: [number, number][];
}) {
  const parts: React.ReactNode[] = [];
  let at = 0;
  for (const [start, end] of spans) {
    if (start < at || end > text.length) continue;
    if (start > at) parts.push(text.slice(at, start));
    parts.push(
      <mark key={start} className="rounded-sm bg-primary/25 px-0.5 text-fg">
        {text.slice(start, end)}
      </mark>,
    );
    at = end;
  }
  parts.push(text.slice(at));
  return <>{parts}</>;
}
