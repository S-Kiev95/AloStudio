import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
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

let lastCompany: string | null = null;
let filterPayload: unknown = null;

const contactSegments = [
  {
    id: 10,
    name: "VIP",
    filter_type: "contact",
    query: {
      payload: [
        {
          attribute_key: "name",
          filter_operator: "contains",
          values: ["a"],
          query_operator: "AND",
        },
      ],
    },
  },
];

const server = setupServer(
  http.get("*/contacts/companies", () =>
    HttpResponse.json([
      { name: "Acme", count: 2 },
      { name: "Globex", count: 1 },
    ]),
  ),
  http.get("*/custom_filters", () => HttpResponse.json(contactSegments)),
  http.post("*/contacts/filter", async ({ request }) => {
    filterPayload = await request.json();
    return HttpResponse.json({
      meta: { count: 1, current_page: 1 },
      payload: [contacts[0]],
    });
  }),
  http.get("*/contacts", ({ request }) => {
    lastCompany = new URL(request.url).searchParams.get("company");
    return HttpResponse.json({
      meta: { count: 2, current_page: 1 },
      payload: contacts,
    });
  }),
);

beforeAll(() => server.listen({ onUnhandledRequest: "bypass" }));
afterEach(() => {
  server.resetHandlers();
  lastCompany = null;
  filterPayload = null;
});
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

  it("filters the list when a company chip is clicked", async () => {
    renderWithQuery(<ContactsView accountId="1" />);

    // Chips come from /contacts/companies; clicking one re-queries the
    // list with ?company=.
    const acme = await screen.findByRole("button", { name: /Acme/i });
    fireEvent.click(acme);

    await waitFor(() => expect(lastCompany).toBe("Acme"));
  });

  it("applies an advanced filter via the builder", async () => {
    renderWithQuery(<ContactsView accountId="1" />);
    await screen.findByText("Ana Lovelace");

    fireEvent.click(screen.getByRole("button", { name: /Filtros/i }));
    // Default row is name/contains; just fill the value and apply.
    fireEvent.change(screen.getByLabelText("Valor"), {
      target: { value: "ana" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Aplicar" }));

    await waitFor(() =>
      expect(filterPayload).toEqual({
        payload: [
          {
            attribute_key: "name",
            filter_operator: "contains",
            values: ["ana"],
            query_operator: "AND",
          },
        ],
      }),
    );
  });

  it("applies a saved segment when its chip is clicked", async () => {
    renderWithQuery(<ContactsView accountId="1" />);

    // Segment chips come from GET /custom_filters?filter_type=contact.
    fireEvent.click(await screen.findByRole("button", { name: "VIP" }));

    await waitFor(() =>
      expect(filterPayload).toEqual({
        payload: contactSegments[0].query.payload,
      }),
    );
  });
});
