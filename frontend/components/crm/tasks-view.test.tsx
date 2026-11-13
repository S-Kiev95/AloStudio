import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";

import { notificationHref } from "@/lib/api/notifications";

import { TasksView } from "./tasks-view";

const now = Math.floor(Date.now() / 1000);
const activity = (id: number, title: string, due_at: number | null, kind = "task") => ({
  id,
  kind,
  title,
  description: null,
  due_at,
  done_at: null,
  owner_id: 1,
  contact_id: 5,
  opportunity_id: null,
  created_at: now,
  contact: { id: 5, name: "Lucía Silva", avatar_url: null },
  opportunity: null,
  owner: { id: 1, name: "Ana" },
});

const activities = [
  activity(1, "Mandar presupuesto", now - 3600),
  activity(2, "Llamar a Lucía", now + 10 * 86400, "call"),
  activity(3, "Ordenar fichas", null),
];

let patched: unknown = null;
const server = setupServer(
  http.get("*/crm/activities", () => HttpResponse.json(activities)),
  http.patch("*/crm/activities/:id", async ({ request, params }) => {
    patched = { id: Number(params.id), body: await request.json() };
    return HttpResponse.json({ ...activities[0], done_at: now });
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

describe("TasksView", () => {
  it("groups the tasks by when they are due", async () => {
    renderWithQuery(<TasksView accountId="1" />);
    const overdue = await screen.findByRole("region", { name: "Vencidas" });
    expect(within(overdue).getByText("Mandar presupuesto")).toBeInTheDocument();
    expect(
      within(screen.getByRole("region", { name: "Próximas" })).getByText("Llamar a Lucía"),
    ).toBeInTheDocument();
    expect(
      within(screen.getByRole("region", { name: "Sin fecha" })).getByText("Ordenar fichas"),
    ).toBeInTheDocument();
  });

  it("the checkbox marks a task done", async () => {
    renderWithQuery(<TasksView accountId="1" />);
    fireEvent.click(await screen.findByRole("checkbox", { name: 'Marcar "Mandar presupuesto" como hecha' }));
    await new Promise((r) => setTimeout(r, 50));
    expect(patched).toEqual({ id: 1, body: { done: true } });
  });
});

describe("notificationHref", () => {
  it("sends a due CRM task to the task list", () => {
    expect(
      notificationHref({ primary_actor_type: "CrmActivity", primary_actor: undefined }, "2"),
    ).toBe("/accounts/2/tasks");
  });
});
