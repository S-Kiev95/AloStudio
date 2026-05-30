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

import { CustomAttributesView } from "./custom-attributes-view";

const attrs = [
  {
    id: 1,
    attribute_display_name: "Plan",
    attribute_display_type: "list",
    attribute_description: "Plan contratado",
    attribute_key: "plan",
    regex_pattern: null,
    regex_cue: null,
    attribute_values: ["basic", "pro"],
    attribute_model: "contact_attribute",
    default_value: null,
    created_at: null,
    updated_at: null,
  },
  {
    id: 2,
    attribute_display_name: "Ticket #",
    attribute_display_type: "text",
    attribute_description: null,
    attribute_key: "ticket",
    regex_pattern: "^[A-Z]+-\\d+$",
    regex_cue: "Ej. ABC-1234",
    attribute_values: [],
    attribute_model: "conversation_attribute",
    default_value: null,
    created_at: null,
    updated_at: null,
  },
];

const server = setupServer(
  http.get("*/custom_attribute_definitions", () => HttpResponse.json(attrs)),
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

describe("CustomAttributesView", () => {
  it("lists attributes with model badge and type", async () => {
    renderWithQuery(<CustomAttributesView accountId="1" />);
    expect(await screen.findByText("Plan")).toBeInTheDocument();
    expect(await screen.findByText("Ticket #")).toBeInTheDocument();
    // Description is in the same line as the key, separated by " · ".
    expect(screen.getByText(/Plan contratado/)).toBeInTheDocument();
    // "Conversaciones" shows up both as a filter chip and as a row badge.
    expect(screen.getAllByText("Conversaciones").length).toBeGreaterThanOrEqual(
      2,
    );
    expect(screen.getAllByText("Contactos").length).toBeGreaterThanOrEqual(2);
  });
});
