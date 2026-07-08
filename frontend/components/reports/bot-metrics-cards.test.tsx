import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { BotMetricsCards } from "./bot-metrics-cards";

describe("BotMetricsCards", () => {
  it("renders the four figures with % suffixes on the rates", () => {
    render(
      <BotMetricsCards
        data={{
          conversation_count: 42,
          message_count: 128,
          resolution_rate: 33,
          handoff_rate: 12,
        }}
      />,
    );

    expect(screen.getByText("42")).toBeInTheDocument();
    expect(screen.getByText("128")).toBeInTheDocument();
    // Rates carry a percent suffix (text node split-safe via matcher).
    expect(screen.getByText("33%")).toBeInTheDocument();
    expect(screen.getByText("12%")).toBeInTheDocument();
    expect(screen.getByText("Tasa de resolución")).toBeInTheDocument();
    expect(screen.getByText("Tasa de derivación")).toBeInTheDocument();
  });
});
