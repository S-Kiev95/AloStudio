import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";

import { CollectionsView } from "./collections-view";

const summary = {
  as_of: "2026-11-24",
  month: "2026-11",
  debtors_count: 2,
  overdue_debtors_count: 1,
  currencies: [
    {
      currency: "UYU",
      to_collect: 2600,
      overdue: 600,
      collected_this_month: 1400,
      credit_balance: 0,
    },
  ],
};

const rows = [
  {
    contact: {
      id: 7,
      name: "Lucía Silva",
      email: "lucia@example.com",
      phone_number: "+59899111222",
      avatar_url: null,
    },
    owner: { id: 1, name: "Ana Admin" },
    currencies: [
      {
        currency: "UYU",
        owed_total: 600,
        overdue_total: 600,
        credit_balance: 0,
        net_balance: 600,
      },
    ],
    days_overdue: 10,
    next_due_on: "2026-11-14",
    sales_count: 1,
    overdue_count: 1,
    whatsapp_conversation: { display_id: 42, inbox_id: 3 },
  },
  {
    contact: {
      id: 8,
      name: "Bruno Pérez",
      email: "bruno@example.com",
      phone_number: "+59899333444",
      avatar_url: null,
    },
    owner: { id: 2, name: "Beto Agente" },
    currencies: [
      {
        currency: "UYU",
        owed_total: 2000,
        overdue_total: 0,
        credit_balance: 0,
        net_balance: 2000,
      },
    ],
    days_overdue: 0,
    next_due_on: "2026-12-05",
    sales_count: 2,
    overdue_count: 0,
    whatsapp_conversation: null,
  },
];

let lastStatusParam: string | null = null;

const server = setupServer(
  http.get("*/agents", () =>
    HttpResponse.json([
      { id: 1, name: "Ana Admin", available_name: "Ana Admin" },
      { id: 2, name: "Beto Agente", available_name: "Beto Agente" },
    ]),
  ),
  http.get("*/crm/receivables/summary", () => HttpResponse.json(summary)),
  http.get("*/crm/receivables", ({ request }) => {
    const url = new URL(request.url);
    lastStatusParam = url.searchParams.get("status");
    const filtered =
      lastStatusParam === "overdue"
        ? rows.filter((r) => r.days_overdue > 0)
        : lastStatusParam === "upcoming"
          ? rows.filter((r) => r.days_overdue === 0)
          : rows;
    return HttpResponse.json({
      as_of: "2026-11-24",
      items: filtered,
      meta: { page: 1, per_page: 25, total: filtered.length, total_pages: 1 },
    });
  }),
);

beforeAll(() => server.listen({ onUnhandledRequest: "bypass" }));
afterEach(() => {
  server.resetHandlers();
  lastStatusParam = null;
});
afterAll(() => server.close());

function renderWithQuery(ui: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

describe("CollectionsView", () => {
  it("muestra los totales arriba, la tabla de deudores, filtro vencidos y link de recordatorio", async () => {
    renderWithQuery(<CollectionsView accountId="1" />);

    expect(await screen.findByText("Lucía Silva")).toBeInTheDocument();
    expect(screen.getByText("Bruno Pérez")).toBeInTheDocument();
    expect(screen.getByText("2 clientes con deuda")).toBeInTheDocument();
    expect(screen.getByText("1 con atraso")).toBeInTheDocument();
    expect(screen.getByText("10 d de atraso")).toBeInTheDocument();

    const reminderLink = screen.getByRole("link", {
      name: "Recordar por WhatsApp: Lucía Silva",
    });
    expect(reminderLink).toHaveAttribute(
      "href",
      expect.stringContaining("/accounts/1/conversations/42?draft="),
    );
    // Bruno has no WhatsApp conversation -> button disabled (never auto-sent).
    expect(
      screen.getByRole("button", { name: "Recordar por WhatsApp: Bruno Pérez" }),
    ).toBeDisabled();

    // Filter by Vencidos.
    fireEvent.click(screen.getByRole("button", { name: "Vencidos" }));
    await screen.findByText("Lucía Silva");
    expect(lastStatusParam).toBe("overdue");
    expect(screen.queryByText("Bruno Pérez")).not.toBeInTheDocument();
  });
});
