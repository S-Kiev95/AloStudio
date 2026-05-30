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

import { TeamsView } from "./teams-view";

const teams = [
  {
    id: 1,
    name: "Soporte",
    description: "Equipo de soporte",
    allow_auto_assign: true,
    account_id: 1,
    is_member: true,
  },
  {
    id: 2,
    name: "Ventas",
    description: null,
    allow_auto_assign: false,
    account_id: 1,
    is_member: false,
  },
];

const server = setupServer(
  http.get("*/teams", () => HttpResponse.json(teams)),
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

describe("TeamsView", () => {
  it("lists teams, marks membership, and flags auto-assign off", async () => {
    renderWithQuery(<TeamsView accountId="1" />);
    expect(await screen.findByText("Soporte")).toBeInTheDocument();
    expect(await screen.findByText("Ventas")).toBeInTheDocument();
    expect(screen.getByText("Sos miembro")).toBeInTheDocument();
    expect(screen.getByText("Sin asignación automática")).toBeInTheDocument();
  });
});
