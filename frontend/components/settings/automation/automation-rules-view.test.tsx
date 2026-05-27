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

import { valuesFromText, valuesToText } from "./condition-row";
import { AutomationRulesView } from "./automation-rules-view";

const rules = [
  {
    id: 1,
    account_id: 1,
    name: "Etiquetar VIP",
    description: "Si el email termina en vip.com",
    event_name: "conversation_created",
    conditions: [
      {
        attribute_key: "email",
        filter_operator: "contains",
        query_operator: "",
        values: ["@vip.com"],
      },
    ],
    actions: [{ action_name: "add_label", action_params: ["vip"] }],
    created_on: 1_700_000_000,
    active: true,
  },
  {
    id: 2,
    account_id: 1,
    name: "Auto-resolver bot",
    description: null,
    event_name: "message_created",
    conditions: [],
    actions: [
      { action_name: "resolve_conversation", action_params: [] },
      { action_name: "add_private_note", action_params: ["bot answered"] },
    ],
    created_on: 1_700_000_000,
    active: false,
  },
];

const server = setupServer(
  http.get("*/automation_rules", () =>
    HttpResponse.json({ payload: rules }),
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

describe("AutomationRulesView", () => {
  it("lists rules with event, counts, and active state", async () => {
    renderWithQuery(<AutomationRulesView accountId="1" />);
    expect(await screen.findByText("Etiquetar VIP")).toBeInTheDocument();
    expect(await screen.findByText("Auto-resolver bot")).toBeInTheDocument();
    // Event label + condition/action counts in the summary line.
    expect(screen.getByText(/Conversación creada/)).toBeInTheDocument();
    expect(screen.getByText(/Mensaje creado/)).toBeInTheDocument();
    expect(screen.getByText("Activa")).toBeInTheDocument();
    expect(screen.getByText("Inactiva")).toBeInTheDocument();
  });
});

describe("condition values helpers", () => {
  it("round-trips comma-separated values", () => {
    expect(valuesFromText("a, b,  c ")).toEqual(["a", "b", "c"]);
    expect(valuesToText(["a", "b", "c"])).toBe("a, b, c");
  });
  it("returns empty array for blank text", () => {
    expect(valuesFromText("")).toEqual([]);
  });
});
