"use client";

import { useCallback, useState } from "react";

import type { TrafficRow } from "@/lib/api/reports";

const HOURS = Array.from({ length: 24 }, (_, h) => h);

function shortDate(iso: string): string {
  // "2026-07-01" → "01/07"
  const [, m, d] = iso.split("-");
  return `${d}/${m}`;
}

function hourLabel(h: number): string {
  return `${String(h).padStart(2, "0")}:00`;
}

function countLabel(count: number): string {
  if (count === 0) return "Sin conversaciones";
  return count === 1 ? "1 conversación" : `${count} conversaciones`;
}

type Hovered = { x: number; y: number; when: string; count: number };

/**
 * Conversations-created heatmap: rows are hours 0–23, columns are the dates
 * in range. Cell intensity scales with the count relative to the busiest cell.
 *
 * Readout is a custom tooltip rather than the native `title`: that one only
 * appears after about a second of a perfectly still cursor, which on 32×20px
 * cells means it often never fires at all — a heatmap you cannot read values
 * off of is just a texture.
 *
 * One shared tooltip node, positioned from the hovered cell's rect, rather
 * than one per cell — the grid is 24 × N and per-cell nodes would be hundreds
 * of them. It is `fixed` because the table scrolls inside an `overflow`
 * container, which would otherwise clip an absolutely-positioned tooltip.
 */
export function TrafficHeatmap({ data }: { data: TrafficRow[] }) {
  const [hovered, setHovered] = useState<Hovered | null>(null);

  const show = useCallback(
    (e: React.MouseEvent<HTMLElement>, when: string, count: number) => {
      const r = e.currentTarget.getBoundingClientRect();
      setHovered({
        x: r.left + r.width / 2,
        y: r.top,
        when,
        count,
      });
    },
    [],
  );
  const hide = useCallback(() => setHovered(null), []);

  if (data.length === 0) {
    return (
      <p className="py-8 text-center text-sm text-fg-muted">
        No hay conversaciones en el rango elegido.
      </p>
    );
  }

  const max = Math.max(1, ...data.flatMap((row) => row.hours));

  return (
    <div className="relative">
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
                  {hourLabel(h)}
                </th>
                {data.map((row) => {
                  const count = row.hours[h] ?? 0;
                  const when = `${shortDate(row.date)} ${hourLabel(h)}`;
                  return (
                    <td key={row.date} className="p-0">
                      <div
                        // Kept for screen readers, which read cells through
                        // table navigation rather than hover.
                        aria-label={`${when} — ${countLabel(count)}`}
                        onMouseEnter={(e) => show(e, when, count)}
                        onMouseLeave={hide}
                        className={
                          count === 0
                            ? "h-5 w-8 rounded-sm bg-surface-2 transition-shadow"
                            : "h-5 w-8 rounded-sm bg-primary transition-shadow hover:ring-2 hover:ring-fg/40"
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

      {hovered ? (
        <div
          role="tooltip"
          // -100% lifts it clear of the cell; the 8px gap leaves room for the
          // ring the hovered cell draws.
          style={{
            position: "fixed",
            left: hovered.x,
            top: hovered.y - 8,
            transform: "translate(-50%, -100%)",
            pointerEvents: "none",
          }}
          className="z-50 whitespace-nowrap rounded-lg border border-border bg-surface px-2.5 py-1.5 text-xs shadow-md"
        >
          <p className="font-numeric tabular-nums text-fg-muted">
            {hovered.when}
          </p>
          <p className="font-semibold text-fg">{countLabel(hovered.count)}</p>
        </div>
      ) : null}
    </div>
  );
}
