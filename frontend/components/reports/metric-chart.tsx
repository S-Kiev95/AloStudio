"use client";

import type { TimeseriesPoint } from "@/lib/api/reports";
import { shortDate } from "@/lib/time";

/** Dependency-free responsive bar chart for a daily-bucketed series. */
export function MetricChart({
  data,
  formatValue,
}: {
  data: TimeseriesPoint[];
  formatValue: (v: number) => string;
}) {
  if (!data.length) {
    return (
      <p className="py-12 text-center text-sm text-fg-muted">
        Sin datos en el período seleccionado.
      </p>
    );
  }

  const max = Math.max(...data.map((d) => d.value), 1);

  return (
    <div>
      {/* No `items-end` here. It makes each column height-by-content, and a
          percentage height inside a content-sized box resolves to nothing —
          every bar came out 0px tall and the chart rendered empty. Letting
          the columns stretch to this row's fixed height gives the bars
          something to be a percentage of; `justify-end` inside each column
          is what puts the bar on the floor. */}
      <div data-chart-row className="flex h-48 gap-px">
        {data.map((d) => {
          const pct = (d.value / max) * 100;
          return (
            <div
              key={d.timestamp}
              className="group flex flex-1 flex-col justify-end"
              title={`${shortDate(d.timestamp)}: ${formatValue(d.value)}`}
            >
              <div
                data-bar
                className="w-full rounded-t bg-primary/60 transition-colors group-hover:bg-primary"
                style={{ height: `${d.value > 0 ? Math.max(pct, 2) : 0}%` }}
              />
            </div>
          );
        })}
      </div>
      <div data-axis className="mt-2 flex justify-between text-xs text-fg-muted">
        <span>{shortDate(data[0].timestamp)}</span>
        <span>{shortDate(data[data.length - 1].timestamp)}</span>
      </div>
    </div>
  );
}
