import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";

import { currentMonth, shiftMonth, type UsageSummary } from "@/lib/api/usage";

import { CostsView } from "./costs-view";

const SUMMARY: UsageSummary = {
  month: currentMonth(),
  whatsapp: {
    currency: "USD",
    total_cost: 0.8,
    messages: 50,
    billable_messages: 10,
    by_category: [
      { category: "MARKETING", volume: 10, cost: 0.8 },
      { category: "SERVICE", volume: 40, cost: 0 },
    ],
    by_country: [{ country: "UY", volume: 50, cost: 0.8 }],
    by_inbox: [{ inbox_id: 7, name: "WA Ventas", volume: 50, cost: 0.8 }],
    by_day: [],
    last_synced_at: 1763100000,
  },
  campaigns: [
    {
      campaign_id: 3,
      title: "Inscripciones",
      inbox_id: 7,
      messages: 3,
      billable_messages: 3,
      estimated_cost: 0.24,
      complete: true,
    },
  ],
  ai: {
    currency: "USD",
    total_cost: 0.02,
    requests: 4,
    prices_checked_on: "2026-11-14",
    items: [
      {
        purpose: "help_center",
        model: "text-embedding-3-small",
        requests: 4,
        input_tokens: 1000000,
        output_tokens: 0,
        cost: 0.02,
      },
    ],
  },
};

let synced = false;
let putBody: unknown = null;
let whatsappCap: number | null = null;
let forbidden = false;
const server = setupServer(
  http.get("*/api/v1/accounts/1/usage", () =>
    forbidden
      ? HttpResponse.json({ error: "not allowed" }, { status: 401 })
      : HttpResponse.json(SUMMARY),
  ),
  http.get("*/api/v1/accounts/1/usage/limits", () =>
    HttpResponse.json({
      limits: [
        {
          kind: "whatsapp",
          monthly_limit: whatsappCap,
          spent: 9.5,
          percent: whatsappCap ? (9.5 / whatsappCap) * 100 : null,
          reached: whatsappCap !== null && 9.5 >= whatsappCap,
        },
        { kind: "ai", monthly_limit: null, spent: 0.02, percent: null, reached: false },
      ],
    }),
  ),
  http.put("*/api/v1/accounts/1/usage/limits/whatsapp", async ({ request }) => {
    putBody = await request.json();
    whatsappCap = (putBody as { monthly_limit: number }).monthly_limit;
    return HttpResponse.json({
      limits: [
        { kind: "whatsapp", monthly_limit: whatsappCap, spent: 9.5, percent: 95, reached: false },
        { kind: "ai", monthly_limit: null, spent: 0.02, percent: null, reached: false },
      ],
    });
  }),
  http.post("*/api/v1/accounts/1/usage/whatsapp/sync", () => {
    synced = true;
    return HttpResponse.json({
      ...SUMMARY,
      sync_errors: [{ inbox_id: 9, name: "WA Viejo", message: "Token vencido" }],
    });
  }),
);

beforeAll(() => server.listen({ onUnhandledRequest: "bypass" }));
afterEach(() => {
  server.resetHandlers();
  synced = false;
  forbidden = false;
  putBody = null;
  whatsappCap = null;
});
afterAll(() => server.close());

function renderView() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <CostsView accountId="1" />
    </QueryClientProvider>,
  );
}

describe("Gastos", () => {
  it("moves between months", () => {
    expect(shiftMonth("2026-01", -1)).toBe("2025-12");
    expect(shiftMonth("2026-12", 1)).toBe("2027-01");
  });

  it("shows WhatsApp by number and category, mass sends and AI", async () => {
    renderView();
    expect(await screen.findByText("WA Ventas")).toBeInTheDocument();
    expect(screen.getByText("Marketing")).toBeInTheDocument();
    expect(screen.getByText("Servicio")).toBeInTheDocument();
    expect(screen.getByText("Inscripciones")).toBeInTheDocument();
    expect(screen.getByText("Help Center")).toBeInTheDocument();
    expect(screen.getByText("text-embedding-3-small")).toBeInTheDocument();
    // The next-month arrow is off on the current month.
    expect(screen.getByRole("button", { name: "Mes siguiente" })).toBeDisabled();
  });

  it("refreshes from Meta and reports a number that failed", async () => {
    renderView();
    fireEvent.click(await screen.findByRole("button", { name: /Actualizar desde Meta/ }));
    await waitFor(() => expect(synced).toBe(true));
    expect(await screen.findByText(/WA Viejo: Token vencido/)).toBeInTheDocument();
  });

  it("sets the monthly WhatsApp cap", async () => {
    renderView();
    const box = await screen.findByTestId("limit-whatsapp");
    fireEvent.click(within(box).getByRole("button", { name: "Poner tope" }));
    fireEvent.change(within(box).getByLabelText("Tope mensual"), { target: { value: "10" } });
    fireEvent.click(within(box).getByRole("button", { name: "Guardar" }));
    await waitFor(() => expect(putBody).toEqual({ monthly_limit: 10 }));
    expect(await within(box).findByRole("progressbar")).toHaveAttribute("aria-valuenow", "95");
  });

  it("warns when the cap is reached", async () => {
    whatsappCap = 5;
    renderView();
    const box = await screen.findByTestId("limit-whatsapp");
    expect(await within(box).findByText(/no salen plantillas/)).toBeInTheDocument();
  });

  it("tells agents the costs are for administrators", async () => {
    forbidden = true;
    renderView();
    expect(await screen.findByText(/Solo los administradores/)).toBeInTheDocument();
  });
});
