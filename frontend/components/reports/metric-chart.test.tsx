import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { MetricChart } from "./metric-chart";

/** The bug this covers: every bar rendered 0px tall, so a chart with real
 *  data drew an empty box. jsdom does not lay out, so the assertion is on
 *  the style the bar is given and on the row not forcing content-height
 *  columns — the two things that produced it. */
function bars(container: HTMLElement): HTMLElement[] {
  return [...container.querySelectorAll<HTMLElement>("[data-bar]")];
}

const SERIES = [
  { timestamp: 1_754_870_400, value: 2 },
  { timestamp: 1_754_956_800, value: 5 },
];

describe("MetricChart", () => {
  it("gives the tallest bar the full height", () => {
    const { container } = render(
      <MetricChart data={SERIES} formatValue={(v) => String(v)} />,
    );
    expect(bars(container).map((b) => b.style.height)).toEqual(["40%", "100%"]);
  });

  it("does not size the columns by their content", () => {
    // `items-end` did exactly that, and a percentage height inside a
    // content-sized box resolves to nothing.
    const { container } = render(
      <MetricChart data={SERIES} formatValue={(v) => String(v)} />,
    );
    const row = container.querySelector("[data-chart-row]");
    expect(row?.className).not.toContain("items-end");
    expect(row?.className).toContain("h-48");
  });

  it("keeps a tiny non-zero value visible", () => {
    const { container } = render(
      <MetricChart
        data={[
          { timestamp: 1, value: 1 },
          { timestamp: 2, value: 400 },
        ]}
        formatValue={(v) => String(v)}
      />,
    );
    // 0.25% would be invisible; a day that had traffic must not look empty.
    expect(bars(container)[0].style.height).toBe("2%");
  });

  it("draws nothing for a day with no traffic", () => {
    const { container } = render(
      <MetricChart
        data={[
          { timestamp: 1, value: 0 },
          { timestamp: 2, value: 3 },
        ]}
        formatValue={(v) => String(v)}
      />,
    );
    expect(bars(container)[0].style.height).toBe("0%");
  });

  it("labels the ends of the range", () => {
    const { container } = render(
      <MetricChart data={SERIES} formatValue={(v) => String(v)} />,
    );
    expect(container.querySelectorAll("[data-axis] span")).toHaveLength(2);
  });

  it("says so when there is no data at all", () => {
    render(<MetricChart data={[]} formatValue={(v) => String(v)} />);
    expect(screen.getByText(/Sin datos/)).toBeInTheDocument();
  });
});
