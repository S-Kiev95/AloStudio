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

import { CampaignsView } from "./campaigns-view";

const campaigns = [
  {
    id: 1,
    display_id: 1,
    title: "Bienvenida web",
    description: null,
    message: "Hola!",
    sender_id: null,
    enabled: true,
    account_id: 1,
    inbox_id: 5,
    trigger_rules: { url: "/pricing", time_on_page: 30 },
    campaign_type: "ongoing",
    campaign_status: "active",
    audience: [],
    scheduled_at: null,
    trigger_only_during_business_hours: false,
    template_params: null,
    created_at: 1_700_000_000,
  },
  {
    id: 2,
    display_id: 2,
    title: "Black Friday",
    description: null,
    message: "30% off",
    sender_id: 9,
    enabled: false,
    account_id: 1,
    inbox_id: 5,
    trigger_rules: {},
    campaign_type: "one_off",
    campaign_status: "active",
    audience: [{ type: "Label", id: 1 }],
    scheduled_at: "2026-11-28T10:00:00Z",
    trigger_only_during_business_hours: null,
    template_params: null,
    created_at: 1_700_000_000,
  },
];

const server = setupServer(
  http.get("*/campaigns", () => HttpResponse.json(campaigns)),
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

describe("CampaignsView", () => {
  it("lists campaigns with type and enabled badges", async () => {
    renderWithQuery(<CampaignsView accountId="1" />);
    expect(await screen.findByText("Bienvenida web")).toBeInTheDocument();
    expect(await screen.findByText("Black Friday")).toBeInTheDocument();
    expect(screen.getByText("Continua")).toBeInTheDocument();
    expect(screen.getByText("Puntual")).toBeInTheDocument();
    // Activa badge appears for the enabled campaign + as filter chip too.
    expect(screen.getAllByText("Activa").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("Inactiva")).toBeInTheDocument();
  });
});
