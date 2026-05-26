import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import {
  afterAll,
  afterEach,
  beforeAll,
  describe,
  expect,
  it,
} from "vitest";

import { ReportsView } from "./reports-view";

const summary = {
  conversations_count: 120,
  incoming_messages_count: 800,
  outgoing_messages_count: 650,
  avg_first_response_time: 95, // 1m 35s
  avg_resolution_time: 7200, // 2h
  resolutions_count: 90,
  reply_time: 300, // 5m
  previous: {
    conversations_count: 100,
    incoming_messages_count: 700,
    outgoing_messages_count: 600,
    avg_first_response_time: 120,
    avg_resolution_time: 9000,
    resolutions_count: 80,
    reply_time: 360,
  },
};

const server = setupServer(
  http.get("*/live_reports/conversation_metrics", () =>
    HttpResponse.json({ open: 5, unattended: 2, unassigned: 1, pending: 3 }),
  ),
  http.get("*/reports/summary", () => HttpResponse.json(summary)),
  http.get("*/reports", () =>
    HttpResponse.json([
      { value: 10, timestamp: 1_700_000_000 },
      { value: 14, timestamp: 1_700_086_400 },
    ]),
  ),
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

describe("ReportsView", () => {
  it("renders live counters and summary metrics", async () => {
    renderWithQuery(<ReportsView accountId="1" />);

    // Summary card value (conversations_count) + duration formatting.
    expect(await screen.findByText("120")).toBeInTheDocument();
    expect(await screen.findByText("1m 35s")).toBeInTheDocument();
    // Live snapshot label is present.
    expect(screen.getByText("Sin atender")).toBeInTheDocument();
  });
});
