import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";

import { SummaryTable } from "./summary-table";

const agentRows = [
  {
    id: 2,
    conversations_count: 10,
    resolved_conversations_count: 7,
    avg_resolution_time: 7200, // 2h
    avg_first_response_time: 95, // 1m 35s
    avg_reply_time: 300, // 5m
  },
  {
    id: 3,
    conversations_count: 25,
    resolved_conversations_count: 20,
    avg_resolution_time: 0, // → "—"
    avg_first_response_time: 0,
    avg_reply_time: 0,
  },
];

const server = setupServer(
  http.get("*/agents", () =>
    HttpResponse.json([
      { id: 2, name: "Demo Admin" },
      { id: 3, name: "Sofía Agente" },
    ]),
  ),
  http.get("*/summary_reports/agent", () => HttpResponse.json(agentRows)),
);

beforeAll(() => server.listen({ onUnhandledRequest: "bypass" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

function renderWithQuery(ui: React.ReactElement) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

describe("SummaryTable", () => {
  it("resolves agent names, formats durations, and sorts by volume", async () => {
    renderWithQuery(
      <SummaryTable
        accountId="1"
        scope="agent"
        range={{ since: 0, until: 100 }}
      />,
    );

    // Agent rows lack a name; it must be resolved from the agents list.
    expect(await screen.findByText("Demo Admin")).toBeInTheDocument();
    expect(screen.getByText("Sofía Agente")).toBeInTheDocument();

    // Duration formatting (2h, 1m 35s) + zero → em dash.
    expect(screen.getByText("2h")).toBeInTheDocument();
    expect(screen.getByText("1m 35s")).toBeInTheDocument();
    expect(screen.getAllByText("—").length).toBeGreaterThan(0);

    // Highest-volume agent (25 convs) sorts above the 10-conv one.
    const rows = screen.getAllByRole("row");
    // rows[0] = header; rows[1] = first data row.
    expect(rows[1]).toHaveTextContent("Sofía Agente");
    expect(rows[1]).toHaveTextContent("25");
  });
});
