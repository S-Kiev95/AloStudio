import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { TrafficHeatmap } from "./traffic-heatmap";

describe("TrafficHeatmap", () => {
  it("renders a labelled cell per hour and the date column header", () => {
    const data = [
      {
        date: "2026-07-01",
        hours: Array.from({ length: 24 }, (_, h) => (h === 10 ? 3 : 0)),
      },
    ];
    render(<TrafficHeatmap data={data} />);

    // Each cell carries "<date> <hour> — <count>" as its accessible label.
    expect(screen.getByLabelText("01/07 10:00 — 3")).toBeInTheDocument();
    expect(screen.getByLabelText("01/07 00:00 — 0")).toBeInTheDocument();
    // The date is the column header.
    expect(screen.getByText("01/07")).toBeInTheDocument();
  });

  it("shows an empty state when there is no data", () => {
    render(<TrafficHeatmap data={[]} />);
    expect(
      screen.getByText(/No hay conversaciones/),
    ).toBeInTheDocument();
  });
});
