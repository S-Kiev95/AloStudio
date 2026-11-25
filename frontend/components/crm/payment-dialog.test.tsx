import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from "vitest";

import { PaymentDialog } from "./payment-dialog";

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
      total_sales: 1100,
      paid_total: 0,
      owed_total: 1100,
      credit_balance: 0,
      net_balance: 1100,
      overdue_total: 500,
      days_overdue: 10,
      next_due_on: "2026-11-14",
    },
  ],
  sales: [
    {
      id: 101,
      title: "Curso inicial",
      value: 500,
      currency: "UYU",
      closed_at: 1762000000,
      payment_terms: "credit",
      due_on: "2026-11-14",
      paid_amount: 0,
      owed_amount: 500,
      overdue_amount: 500,
      days_overdue: 10,
      next_due_on: "2026-11-14",
      owner: { id: 1, name: "Ana" },
      installments: [],
    },
    {
      id: 102,
      title: "Curso avanzado",
      value: 600,
      currency: "UYU",
      closed_at: 1762500000,
      payment_terms: "credit",
      due_on: "2026-12-10",
      paid_amount: 0,
      owed_amount: 600,
      overdue_amount: 0,
      days_overdue: 0,
      next_due_on: "2026-12-10",
      owner: { id: 1, name: "Ana" },
      installments: [],
    },
  ],
  payments: [],
};

let postedBody: unknown = null;

const server = setupServer(
  http.get("*/crm/contacts/7/statement", () => HttpResponse.json(statement)),
  http.post("*/crm/payments/preview", async ({ request }) => {
    const body = (await request.json()) as {
      amount: number;
      currency: string | null;
      allocation_mode: "auto" | "manual";
      allocations?: { opportunity_id: number; amount: number }[];
    };
    const allocs =
      body.allocation_mode === "manual"
        ? (body.allocations ?? []).map((a) => ({
            opportunity_id: a.opportunity_id,
            opportunity_title: a.opportunity_id === 101 ? "Curso inicial" : "Curso avanzado",
            installment_id: null,
            installment_number: null,
            due_on: null,
            amount: a.amount,
          }))
        : [
            {
              opportunity_id: 101,
              opportunity_title: "Curso inicial",
              installment_id: null,
              installment_number: null,
              due_on: "2026-11-14",
              amount: Math.min(body.amount, 500),
            },
          ];
    const allocatedTotal = allocs.reduce((acc, item) => acc + item.amount, 0);
    const unallocated = Math.max(0, body.amount - allocatedTotal);
    return HttpResponse.json({
      currency: body.currency,
      amount: body.amount,
      allocated_total: allocatedTotal,
      unallocated_amount: unallocated,
      allocations: allocs,
      balance_before: { owed_total: 1100, credit_balance: 0, net_balance: 1100 },
      balance_after: {
        owed_total: Math.max(0, 1100 - allocatedTotal),
        credit_balance: unallocated,
        net_balance: 1100 - allocatedTotal - unallocated,
      },
    });
  }),
  http.post("*/crm/payments", async ({ request }) => {
    postedBody = await request.json();
    return HttpResponse.json({
      id: 90,
      contact_id: 7,
      amount: 500,
      currency: "UYU",
      paid_on: "2026-11-24",
      method: "transfer",
      note: "Pago parcial",
      allocated_amount: 500,
      unallocated_amount: 0,
      created_by_id: 1,
      created_by: { id: 1, name: "Ana" },
      contact: { id: 7, name: "Lucía Silva", avatar_url: null },
      created_at: 1764000000,
      allocations: [],
    });
  }),
);

beforeAll(() => server.listen({ onUnhandledRequest: "bypass" }));
afterEach(() => {
  server.resetHandlers();
  postedBody = null;
});
afterAll(() => server.close());

function renderWithQuery(ui: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

describe("PaymentDialog", () => {
  it("previsualiza cómo queda el saldo y registra un pago con imputación automática", async () => {
    const onClose = vi.fn();
    renderWithQuery(
      <PaymentDialog
        accountId="1"
        contactId={7}
        contactName="Lucía Silva"
        open={true}
        onClose={onClose}
      />,
    );

    const amountInput = await screen.findByLabelText(/Monto/);
    fireEvent.change(amountInput, { target: { value: "500" } });
    fireEvent.change(screen.getByLabelText("Medio de pago"), {
      target: { value: "transfer" },
    });
    fireEvent.change(screen.getByLabelText("Nota"), {
      target: { value: "Pago parcial" },
    });

    const preview = await screen.findByRole("region", { name: "Cómo queda el saldo" });
    expect(preview).toHaveTextContent("Curso inicial");
    expect(preview).toHaveTextContent(/600/);

    fireEvent.click(screen.getByRole("button", { name: "Guardar pago" }));

    await waitFor(() => expect(onClose).toHaveBeenCalledTimes(1));
    expect(postedBody).toMatchObject({
      contact_id: 7,
      amount: 500,
      currency: "UYU",
      method: "transfer",
      note: "Pago parcial",
      allocation_mode: "auto",
    });
  });

  it("permite elegir ventas y montos manualmente", async () => {
    const onClose = vi.fn();
    renderWithQuery(
      <PaymentDialog
        accountId="1"
        contactId={7}
        contactName="Lucía Silva"
        open={true}
        onClose={onClose}
      />,
    );

    await screen.findByLabelText(/Monto/);
    fireEvent.change(screen.getByLabelText(/Monto/), { target: { value: "300" } });
    fireEvent.click(screen.getByRole("button", { name: "Elegir ventas a mano" }));

    const saleInput = await screen.findByLabelText("Monto para Curso avanzado");
    fireEvent.change(saleInput, { target: { value: "300" } });

    await screen.findByRole("region", { name: "Cómo queda el saldo" });
    fireEvent.click(screen.getByRole("button", { name: "Guardar pago" }));

    await waitFor(() => expect(onClose).toHaveBeenCalledTimes(1));
    expect(postedBody).toMatchObject({
      contact_id: 7,
      amount: 300,
      allocation_mode: "manual",
      allocations: [{ opportunity_id: 102, amount: 300 }],
    });
  });
});
