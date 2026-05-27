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

import { WebhooksView } from "./webhooks-view";

const webhooks = [
  {
    id: 1,
    name: "Pedidos",
    url: "https://example.com/orders",
    account_id: 1,
    subscriptions: ["conversation_created", "message_created"],
    secret: "shh",
    inbox: { id: 5, name: "Tienda" },
  },
  {
    id: 2,
    name: null,
    url: "https://hooks.example.com/global",
    account_id: 1,
    subscriptions: ["conversation_status_changed"],
    secret: "shh2",
    inbox: null,
  },
];

const server = setupServer(
  http.get("*/webhooks", () =>
    HttpResponse.json({ payload: { webhooks } }),
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

describe("WebhooksView", () => {
  it("lists webhooks with event count and scope", async () => {
    renderWithQuery(<WebhooksView accountId="1" />);
    expect(await screen.findByText("Pedidos")).toBeInTheDocument();
    // Anonymous webhook URL appears twice (title fallback + subtext).
    expect(
      (await screen.findAllByText("https://hooks.example.com/global")).length,
    ).toBeGreaterThanOrEqual(1);
    expect(screen.getByText(/2 eventos · Tienda/)).toBeInTheDocument();
    expect(
      screen.getByText(/1 evento · Todas las bandejas/),
    ).toBeInTheDocument();
  });
});
