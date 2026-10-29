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
  vi,
} from "vitest";

import { SettingsSidebar } from "../settings-sidebar";
import { MCPTokensView } from "./mcp-tokens-view";

vi.mock("next/navigation", () => ({
  usePathname: () => "/accounts/1/settings/mcp_tokens",
}));

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

describe("MCPTokensView y menú lateral de Ajustes", () => {
  it("muestra el título 'API y MCP', la explicación de uso y lista tokens con alcances", async () => {
    renderWithQuery(<MCPTokensView accountId="1" />);
    expect(
      screen.getByRole("heading", { name: "API y MCP" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/conectar el agente de IA, n8n/i),
    ).toBeInTheDocument();
    expect(await screen.findByText("agente-soporte")).toBeInTheDocument();
    expect(await screen.findByText("lectura-bi")).toBeInTheDocument();
    expect(screen.getByText("Escritura")).toBeInTheDocument();
    expect(screen.getByText("Lectura")).toBeInTheDocument();
    expect(screen.getByText("Nunca usado")).toBeInTheDocument();
  });

  it("incluye el grupo Publicación (Firmas, Sets, Auto post, Plugs) y API y MCP en SettingsSidebar", () => {
    render(<SettingsSidebar accountId="1" />);
    expect(screen.getByText("Publicación")).toBeInTheDocument();
    expect(
      screen.getAllByRole("link", { name: "Firmas" })[0],
    ).toHaveAttribute("href", "/accounts/1/settings/signatures");
    expect(screen.getAllByRole("link", { name: "Sets" })[0]).toHaveAttribute(
      "href",
      "/accounts/1/settings/sets",
    );
    expect(
      screen.getAllByRole("link", { name: "Auto post" })[0],
    ).toHaveAttribute("href", "/accounts/1/settings/autoposts");
    expect(screen.getAllByRole("link", { name: "Plugs" })[0]).toHaveAttribute(
      "href",
      "/accounts/1/settings/plugs",
    );
    expect(
      screen.getAllByRole("link", { name: "API y MCP" })[0],
    ).toHaveAttribute("href", "/accounts/1/settings/mcp_tokens");
  });
});
