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

import { ContactsView } from "./contacts-view";

const contacts = [
  {
    id: 1,
    name: "Ana Lovelace",
    email: "ana@example.com",
    phone_number: "+59899111111",
    blocked: false,
    identifier: null,
    thumbnail: "",
    availability_status: "offline",
    additional_attributes: {},
    custom_attributes: {},
    created_at: 1_700_000_000,
  },
  {
    id: 2,
    name: null,
    email: null,
    phone_number: "+59899222222",
    blocked: true,
    identifier: "crm-42",
    thumbnail: "",
    availability_status: "offline",
    additional_attributes: {},
    custom_attributes: {},
    created_at: 1_700_000_000,
  },
];

const server = setupServer(
  http.get("*/contacts", () =>
    HttpResponse.json({
      meta: { count: 2, current_page: 1 },
      payload: contacts,
    }),
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

describe("ContactsView", () => {
  it("lists contacts and falls back to phone/identifier when name is empty", async () => {
    renderWithQuery(<ContactsView accountId="1" />);
    expect(await screen.findByText("Ana Lovelace")).toBeInTheDocument();
    // Contact #2 has no name/email — the phone number shows both as the
    // row title (fallback) AND in the icon-prefixed details line.
    expect(
      (await screen.findAllByText("+59899222222")).length,
    ).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("Bloqueado")).toBeInTheDocument();
    // Pagination footer shows the count.
    expect(screen.getByText(/2 contactos/i)).toBeInTheDocument();
  });
});
