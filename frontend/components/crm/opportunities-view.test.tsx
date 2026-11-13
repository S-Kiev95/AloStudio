import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";

import { OpportunitiesView } from "./opportunities-view";

const stage = (id: number, code: string, kind: string, probability: number, position: number) => ({
  id,
  code,
  name: null,
  kind,
  probability,
  position,
});

const pipeline = {
  id: 1,
  name: null,
  is_default: true,
  rotten_days: 30,
  stages: [
    stage(10, "new", "open", 10, 0),
    { ...stage(11, "proposal", "open", 50, 1), name: "Demo agendada" },
    stage(12, "won", "won", 100, 2),
    stage(13, "lost", "lost", 0, 3),
  ],
};

const now = Math.floor(Date.now() / 1000);
const opportunity = (id: number, stage_id: number, title: string, value: number | null) => ({
  id,
  pipeline_id: 1,
  stage_id,
  title,
  description: null,
  value,
  currency: value != null ? "USD" : null,
  contact_id: 5,
  product_id: null,
  owner_id: 1,
  conversation_id: null,
  expected_close_on: null,
  closed_at: null,
  lost_reason: null,
  position: 0,
  stage_changed_at: now,
  created_at: now,
  updated_at: now,
  contact: { id: 5, name: "Lucía Silva", avatar_url: null },
  product: null,
  owner: { id: 1, name: "Ana" },
});

const opportunities = [
  opportunity(100, 10, "Curso de inglés", 1200),
  opportunity(101, 10, "Taller de cerámica", 300),
  opportunity(102, 11, "Plan anual", null),
];

let patched: unknown = null;
const server = setupServer(
  http.get("*/crm/pipelines", () => HttpResponse.json([pipeline])),
  http.get("*/crm/opportunities", () => HttpResponse.json(opportunities)),
  http.patch("*/crm/opportunities/:id", async ({ request, params }) => {
    patched = { id: Number(params.id), body: await request.json() };
    return HttpResponse.json({ ...opportunities[0], stage_id: 12 });
  }),
);

beforeAll(() => server.listen({ onUnhandledRequest: "bypass" }));
afterEach(() => {
  server.resetHandlers();
  patched = null;
});
afterAll(() => server.close());

function renderWithQuery(ui: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

describe("OpportunitiesView", () => {
  it("shows one column per stage, with counts and totals", async () => {
    renderWithQuery(<OpportunitiesView accountId="1" />);
    const fresh = await screen.findByRole("region", { name: "Nueva" });
    expect(within(fresh).getByText("Curso de inglés")).toBeInTheDocument();
    expect(within(fresh).getByText("Taller de cerámica")).toBeInTheDocument();
    expect(within(fresh).getByText("2")).toBeInTheDocument();
    expect(within(fresh).getByText(/1.500/)).toBeInTheDocument();
    // A stage someone renamed shows its own name; the seeded ones, translated.
    const demo = screen.getByRole("region", { name: "Demo agendada" });
    expect(within(demo).getByText("Plan anual")).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Ganada" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Perdida" })).toBeInTheDocument();
  });

  it("dropping a card on another column moves it to that stage", async () => {
    renderWithQuery(<OpportunitiesView accountId="1" />);
    const card = await screen.findByRole("button", { name: /Curso de inglés/ });
    const won = screen.getByRole("region", { name: "Ganada" });
    const data = new Map<string, string>();
    const dataTransfer = {
      setData: (k: string, v: string) => data.set(k, v),
      getData: (k: string) => data.get(k) ?? "",
      effectAllowed: "move",
    };
    fireEvent.dragStart(card, { dataTransfer });
    fireEvent.dragOver(won, { dataTransfer });
    fireEvent.drop(won, { dataTransfer });
    await screen.findByRole("region", { name: "Ganada" });
    await new Promise((r) => setTimeout(r, 50));
    expect(patched).toEqual({ id: 100, body: { stage_id: 12 } });
  });
});
