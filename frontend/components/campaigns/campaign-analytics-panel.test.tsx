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

import { CampaignAnalyticsPanel } from "./campaign-analytics-panel";

const analytics = {
  campaign_id: 5,
  audience_count: 9,
  conversations_count: 7,
  messages_count: 5,
  delivery: { sent: 4, delivered: 3, read: 2, failed: 1 },
};

const server = setupServer(
  http.get("*/campaigns/5/analytics", () => HttpResponse.json(analytics)),
);

beforeAll(() => server.listen({ onUnhandledRequest: "bypass" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

function wrap(ui: React.ReactElement) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

describe("CampaignAnalyticsPanel", () => {
  it("renders the delivery metrics for the campaign", async () => {
    wrap(<CampaignAnalyticsPanel accountId="1" displayId={5} />);

    // Wait for the data (the title also renders during loading, so key
    // the wait off a metric that only appears once loaded).
    expect(await screen.findByText("Audiencia")).toBeInTheDocument();
    expect(screen.getByText("Entrega")).toBeInTheDocument();
    // Top-line counts (values chosen distinct for unambiguous assertions).
    expect(screen.getByText("9")).toBeInTheDocument();
    expect(screen.getByText("Conversaciones")).toBeInTheDocument();
    expect(screen.getByText("7")).toBeInTheDocument();
    // Delivery breakdown.
    expect(screen.getByText("Enviados")).toBeInTheDocument();
    expect(screen.getByText("4")).toBeInTheDocument();
    expect(screen.getByText("Fallidos")).toBeInTheDocument();
    expect(screen.getByText("1")).toBeInTheDocument();
  });
});
