import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";

import type { Appointment } from "@/lib/api/appointments";

import { AgendaView } from "./agenda-view";

// Wednesday 2026-11-11, 09:30 local.
const NOW = new Date(2026, 10, 11, 9, 30);

const appt = (id: number, at: Date, title: string): Appointment => ({
  id,
  account_id: 1,
  contact_id: 10,
  product_id: null,
  title,
  description: null,
  starts_at: at.toISOString(),
  ends_at: null,
  status: "confirmed",
  notes: null,
  created_by_id: 1,
  created_at: null,
  updated_at: null,
  contact: { id: 10, name: "Ana Lovelace", email: null, phone_number: null },
  product: null,
});

let lastUrl: URL | null = null;
const server = setupServer(
  http.get("*/appointments", ({ request }) => {
    lastUrl = new URL(request.url);
    return HttpResponse.json([
      appt(1, new Date(2026, 10, 11, 15, 0), "Clase de prueba"),
      appt(2, new Date(2026, 10, 20, 11, 0), "Entrevista"),
    ]);
  }),
);

beforeAll(() => server.listen({ onUnhandledRequest: "bypass" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

function renderAgenda() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <AgendaView accountId="1" now={NOW} />
    </QueryClientProvider>,
  );
}

describe("AgendaView", () => {
  it("shows the week as an hourly grid with the now line", async () => {
    renderAgenda();
    const card = await screen.findByTestId("appointment-card-1");
    expect(card).toHaveTextContent("Clase de prueba");
    expect(card).toHaveTextContent("Ana Lovelace");
    expect(screen.getByTestId("agenda-slot-2026-11-11-15")).toContainElement(card);
    expect(screen.getByTestId("agenda-now-line")).toBeInTheDocument();
    // The week asked for: Monday 9 to the next Monday.
    expect(new Date(lastUrl!.searchParams.get("from")!)).toEqual(new Date(2026, 10, 9));
  });

  it("switches to the month grid", async () => {
    renderAgenda();
    await screen.findByTestId("appointment-card-1");
    fireEvent.click(screen.getByRole("button", { name: "Mes" }));
    const day = await screen.findByTestId("agenda-month-day-2026-11-20");
    expect(await screen.findByTestId("appointment-card-2")).toHaveTextContent("11:00");
    expect(day).toContainElement(screen.getByTestId("appointment-card-2"));
  });
});
