import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";

import { ContactStatementCard } from "./contact-statement-card";

const statement = {
  as_of: "2026-11-24",
  contact: {
    id: 7,
    name: "Lucía Silva",
    email: "lucia@example.com",
    phone_number: "+59899111222",
    avatar_url: null,
  },
  whatsapp_conversation: { display_id: 42, inbox_id: 3 },
  balances: [
    {
      currency: "UYU",
      total_sales: 1000,
      paid_total: 400,
      owed_total: 600,
      credit_balance: 0,
      net_balance: 600,
      overdue_total: 600,
      days_overdue: 12,
      next_due_on: "2026-11-12",
    },
    {
      currency: "USD",
      total_sales: 200,
      paid_total: 250,
      owed_total: 0,
      credit_balance: 50,
      net_balance: -50,
      overdue_total: 0,
      days_overdue: 0,
      next_due_on: null,
    },
  ],
  sales: [
    {
      id: 101,
      title: "Curso de inglés",
      value: 1000,
      currency: "UYU",
      closed_at: 1762000000,
      payment_terms: "credit",
      due_on: "2026-11-12",
      paid_amount: 400,
      owed_amount: 600,
      overdue_amount: 600,
      days_overdue: 12,
      next_due_on: "2026-11-12",
      owner: { id: 1, name: "Ana" },
      installments: [],
    },
  ],
  payments: [
    {
      id: 50,
      contact_id: 7,
      amount: 400,
      currency: "UYU",
      paid_on: "2026-11-15",
      method: "transfer",
      note: "Transferencia BROU",
      allocated_amount: 400,
      unallocated_amount: 0,
      created_by_id: 1,
      created_by: { id: 1, name: "Ana Admin" },
      contact: { id: 7, name: "Lucía Silva", avatar_url: null },
      created_at: 1763200000,
      allocations: [
        {
          id: 1,
          opportunity_id: 101,
          opportunity_title: "Curso de inglés",
          installment_id: null,
          installment_number: null,
          amount: 400,
        },
      ],
    },
  ],
};

const server = setupServer(
  http.get("*/crm/contacts/7/statement", () => HttpResponse.json(statement)),
  http.get("*/profile", () =>
    HttpResponse.json({
      id: 1,
      name: "Ana Admin",
      accounts: [{ id: 1, role: "administrator" }],
    }),
  ),
);

beforeAll(() => server.listen({ onUnhandledRequest: "bypass" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

function renderWithQuery(ui: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

describe("ContactStatementCard", () => {
  it("muestra saldos separados por moneda, ventas, vencido, historial de pagos y link de recordatorio", async () => {
    renderWithQuery(
      <ContactStatementCard accountId="1" contact={{ id: 7, name: "Lucía Silva" }} />,
    );

    expect(await screen.findByText("Curso de inglés")).toBeInTheDocument();
    expect(screen.getByText(/Saldo · UYU/)).toBeInTheDocument();
    expect(screen.getByText(/Saldo · USD/)).toBeInTheDocument();
    expect(screen.getAllByText(/12 d de atraso/).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("Transferencia BROU")).toBeInTheDocument();
    expect(screen.getByText("Registrado por Ana Admin")).toBeInTheDocument();

    const reminderLink = screen.getByRole("link", { name: /Recordar por WhatsApp/ });
    const href = reminderLink.getAttribute("href") ?? "";
    expect(href).toContain("/accounts/1/conversations/42?draft=");
    const draft = new URL(href, "http://test").searchParams.get("draft");
    expect(draft).toContain("Lucía Silva");
  });
});
