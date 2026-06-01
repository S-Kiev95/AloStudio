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

import { AgentsView } from "./agents-view";

const agents = [
  {
    id: 10,
    account_id: 1,
    name: "Ada Lovelace",
    email: "ada@example.com",
    role: 1, // administrator
    confirmed: true,
    available_name: "Ada",
    thumbnail: "",
    availability_status: "offline",
    auto_offline: true,
  },
  {
    id: 11,
    account_id: 1,
    name: "Bob Pending",
    email: "bob@example.com",
    role: 0, // agent
    confirmed: false,
    available_name: "Bob",
    thumbnail: "",
    availability_status: "offline",
    auto_offline: true,
  },
];

const server = setupServer(
  http.get("*/agents", () => HttpResponse.json(agents)),
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

describe("AgentsView", () => {
  it("lists agents with role + pending badge + email", async () => {
    renderWithQuery(<AgentsView accountId="1" />);
    expect(await screen.findByText("Ada Lovelace")).toBeInTheDocument();
    expect(await screen.findByText("Bob Pending")).toBeInTheDocument();
    expect(screen.getByText("ada@example.com")).toBeInTheDocument();
    expect(screen.getByText("Pendiente")).toBeInTheDocument();
    // The role selects show the current role per row.
    const selects = screen.getAllByRole("combobox", { name: /rol/i });
    expect(selects).toHaveLength(2);
    expect((selects[0] as HTMLSelectElement).value).toBe("administrator");
    expect((selects[1] as HTMLSelectElement).value).toBe("agent");
  });
});
