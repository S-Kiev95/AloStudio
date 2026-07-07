"use client";

import type { TrafficRow } from "@/lib/api/reports";

const HOURS = Array.from({ length: 24 }, (_, h) => h);

function shortDate(iso: string): string {
  // "2026-07-01" → "01/07"
  const [, m, d] = iso.split("-");
  return `${d}/${m}`;
}

/**
 * Conversations-created heatmap: rows are hours 0–23, columns are the dates
 * in range. Cell intensity scales with the count relative to the busiest cell.
 */
export function TrafficHeatmap({ data }: { data: TrafficRow[] }) {
  if (data.length === 0) {
    return (
      <p className="py-8 text-center text-sm text-fg-muted">
        No hay conversaciones en el rango elegido.
      </p>
    );
  }

  const max = Math.max(1, ...data.flatMap((row) => row.hours));

  return (
    <div className="overflow-x-auto">
      <table className="border-separate border-spacing-1 text-xs">
        <thead>
          <tr>
            <th className="sticky left-0 bg-surface p-1" aria-hidden />
            {data.map((row) => (
              <th
                key={row.date}
                scope="col"
                className="whitespace-nowrap p-1 font-normal text-fg-muted"
              >
                {shortDate(row.date)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {HOURS.map((h) => (
            <tr key={h}>
              <th
                scope="row"
                className="sticky left-0 bg-surface pr-2 text-right font-normal text-fg-muted"
              >
                {String(h).padStart(2, "0")}:00
              </th>
              {data.map((row) => {
                const count = row.hours[h] ?? 0;
                const label = `${shortDate(row.date)} ${String(h).padStart(2, "0")}:00 — ${count}`;
                return (
                  <td key={row.date} className="p-0">
                    <div
                      title={label}
                      aria-label={label}
                      className={
                        count === 0
                          ? "h-5 w-8 rounded-sm bg-surface-2"
                          : "h-5 w-8 rounded-sm bg-primary"
                      }
                      style={
                        count === 0
                          ? undefined
                          : { opacity: 0.2 + 0.8 * (count / max) }
                      }
                    />
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
