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

import { IntegrationsView } from "./integrations-view";

const apps = [
  {
    id: "slack",
    name: "Slack",
    description: "Notificaciones en Slack",
    short_description: "Notificaciones en Slack",
    enabled: true,
    allow_multiple_hooks: false,
    hooks: [
      {
        id: 10,
        app_id: "slack",
        status: true,
        account_id: 1,
        hook_type: "account",
        inbox: null,
      },
    ],
  },
  {
    id: "dialogflow",
    name: "Df Bot",
    description: "Bot conversacional por bandeja",
    short_description: "Bot conversacional",
    enabled: true,
    allow_multiple_hooks: true,
    hooks: [],
  },
];

const server = setupServer(
  http.get("*/integrations/apps", () =>
    HttpResponse.json({ payload: apps }),
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

describe("IntegrationsView", () => {
  it("lists apps with connection status", async () => {
    renderWithQuery(<IntegrationsView accountId="1" />);
    expect(await screen.findByText("Slack")).toBeInTheDocument();
    expect(await screen.findByText("Df Bot")).toBeInTheDocument();
    expect(screen.getByText("1 conectado")).toBeInTheDocument();
    expect(screen.getByText("Disponible")).toBeInTheDocument();
  });
});
