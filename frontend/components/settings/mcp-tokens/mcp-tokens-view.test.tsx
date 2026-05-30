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

import { MCPTokensView } from "./mcp-tokens-view";

const tokens = [
  {
    id: 1,
    account_id: 1,
    user_id: 9,
    name: "agente-soporte",
    scope: "write",
    last_used_at: "2026-05-25T10:00:00Z",
    created_at: "2026-05-20T10:00:00Z",
  },
  {
    id: 2,
    account_id: 1,
    user_id: 9,
    name: "lectura-bi",
    scope: "read",
    last_used_at: null,
    created_at: "2026-05-22T10:00:00Z",
  },
];

const server = setupServer(
  http.get("*/mcp_tokens", () => HttpResponse.json({ payload: tokens })),
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

describe("MCPTokensView", () => {
  it("lists tokens with scope badges and last-used", async () => {
    renderWithQuery(<MCPTokensView accountId="1" />);
    expect(await screen.findByText("agente-soporte")).toBeInTheDocument();
    expect(await screen.findByText("lectura-bi")).toBeInTheDocument();
    expect(screen.getByText("Escritura")).toBeInTheDocument();
    expect(screen.getByText("Lectura")).toBeInTheDocument();
    expect(screen.getByText("Nunca usado")).toBeInTheDocument();
  });
});
