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

import { PortalsView } from "./portals-view";

const portals = [
  {
    id: 1,
    account_id: 1,
    name: "Centro de ayuda",
    slug: "ayuda",
    custom_domain: "ayuda.midominio.com",
    color: "#1f93ff",
    homepage_link: null,
    page_title: null,
    header_text: null,
    config: {},
    archived: false,
  },
  {
    id: 2,
    account_id: 1,
    name: "Docs (Borrador)",
    slug: "docs",
    custom_domain: null,
    color: "#7f8c8d",
    homepage_link: null,
    page_title: null,
    header_text: null,
    config: {},
    archived: true,
  },
];

const server = setupServer(
  http.get("*/portals", () => HttpResponse.json(portals)),
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

describe("PortalsView", () => {
  it("lists portals with archived badge and custom domain", async () => {
    renderWithQuery(<PortalsView accountId="1" />);
    expect(await screen.findByText("Centro de ayuda")).toBeInTheDocument();
    expect(await screen.findByText("Docs (Borrador)")).toBeInTheDocument();
    expect(screen.getByText("Archivado")).toBeInTheDocument();
    expect(
      screen.getByText(/\/ayuda · ayuda\.midominio\.com/),
    ).toBeInTheDocument();
  });
});
