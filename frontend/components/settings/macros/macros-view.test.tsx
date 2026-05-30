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

import {
  paramsToText,
  textToParams,
} from "./macro-action-row";
import { MacrosView } from "./macros-view";

const macros = [
  {
    id: 1,
    name: "Auto-resolver",
    visibility: "global",
    account_id: 1,
    actions: [
      { action_name: "add_label", action_params: ["vip", "prioridad"] },
      { action_name: "resolve_conversation", action_params: [] },
    ],
    created_by: { id: 10, name: "Ada" },
  },
  {
    id: 2,
    name: "Saludo inicial",
    visibility: "personal",
    account_id: 1,
    actions: [
      { action_name: "send_message", action_params: ["Hola!"] },
    ],
  },
];

const server = setupServer(
  http.get("*/macros", () => HttpResponse.json({ payload: macros })),
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

describe("MacrosView", () => {
  it("lists macros with visibility and action count", async () => {
    renderWithQuery(<MacrosView accountId="1" />);
    expect(await screen.findByText("Auto-resolver")).toBeInTheDocument();
    expect(await screen.findByText("Saludo inicial")).toBeInTheDocument();
    expect(screen.getByText("Global")).toBeInTheDocument();
    expect(screen.getByText("Personal")).toBeInTheDocument();
    expect(screen.getByText(/2 acciones/)).toBeInTheDocument();
    expect(screen.getByText(/1 acción/)).toBeInTheDocument();
  });
});

describe("macro action params helpers", () => {
  it("round-trips list params via comma-separated text", () => {
    expect(paramsToText("add_label", ["a", "b", "c"])).toBe("a, b, c");
    expect(textToParams("add_label", "a, b, c")).toEqual(["a", "b", "c"]);
  });

  it("emits an empty array for no-params actions", () => {
    expect(textToParams("resolve_conversation", "ignored")).toEqual([]);
    expect(paramsToText("resolve_conversation", [])).toBe("");
  });

  it("handles change_priority null clear", () => {
    expect(textToParams("change_priority", "null")).toEqual([null]);
    expect(paramsToText("change_priority", [null])).toBe("null");
  });
});
