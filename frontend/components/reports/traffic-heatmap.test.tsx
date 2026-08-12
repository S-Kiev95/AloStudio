import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { TrafficHeatmap } from "./traffic-heatmap";

const ONE_DAY = [
  {
    date: "2026-07-01",
    hours: Array.from({ length: 24 }, (_, h) =>
      h === 10 ? 3 : h === 11 ? 1 : 0,
    ),
  },
];

describe("TrafficHeatmap", () => {
  it("renders a labelled cell per hour and the date column header", () => {
    render(<TrafficHeatmap data={ONE_DAY} />);

    expect(
      screen.getByLabelText("01/07 10:00 — 3 conversaciones"),
    ).toBeInTheDocument();
    // Singular, not "1 conversaciones".
    expect(
      screen.getByLabelText("01/07 11:00 — 1 conversación"),
    ).toBeInTheDocument();
    // An empty hour reads as absence rather than "0 conversaciones".
    expect(
      screen.getByLabelText("01/07 00:00 — Sin conversaciones"),
    ).toBeInTheDocument();
    expect(screen.getByText("01/07")).toBeInTheDocument();
  });

  it("shows the count in a tooltip on hover and hides it on leave", () => {
    render(<TrafficHeatmap data={ONE_DAY} />);
    const cell = screen.getByLabelText("01/07 10:00 — 3 conversaciones");

    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();

    fireEvent.mouseEnter(cell);
    const tip = screen.getByRole("tooltip");
    expect(tip).toHaveTextContent("01/07 10:00");
    expect(tip).toHaveTextContent("3 conversaciones");

    fireEvent.mouseLeave(cell);
    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();
  });

  it("shows an empty state when there is no data", () => {
    render(<TrafficHeatmap data={[]} />);
    expect(screen.getByText(/No hay conversaciones/)).toBeInTheDocument();
  });
});
