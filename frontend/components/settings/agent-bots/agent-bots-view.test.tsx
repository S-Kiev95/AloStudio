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

import { AgentBotsView } from "./agent-bots-view";

const bots = [
  {
    id: 1,
    name: "Captain Hook",
    description: "Saluda y enruta",
    thumbnail: "",
    outgoing_url: "https://bot.example.com",
    bot_type: "webhook",
    bot_config: {},
    account_id: 1,
    secret: "abc",
    system_bot: false,
  },
  {
    id: 2,
    name: "Csat Bot",
    description: null,
    thumbnail: "",
    bot_type: "webhook",
    bot_config: {},
    account_id: null,
    system_bot: true,
  },
];

const server = setupServer(
  http.get("*/agent_bots", () => HttpResponse.json(bots)),
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

describe("AgentBotsView", () => {
  it("lists bots and flags system bots", async () => {
    renderWithQuery(<AgentBotsView accountId="1" />);
    expect(await screen.findByText("Captain Hook")).toBeInTheDocument();
    expect(await screen.findByText("Csat Bot")).toBeInTheDocument();
    expect(screen.getByText("Sistema")).toBeInTheDocument();
    expect(screen.getByText("https://bot.example.com")).toBeInTheDocument();
  });
});
