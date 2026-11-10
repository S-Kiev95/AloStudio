import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";

import { HandoffAssigneePanel } from "./handoff-assignee-panel";

let patched: Record<string, unknown> | null = null;

const server = setupServer(
  http.get("*/agents", () =>
    HttpResponse.json([
      { id: 2, name: "Sofía Costa" },
      { id: 3, name: "Yamila Gonzalez" },
    ]),
  ),
  http.patch("*/inboxes/1", async ({ request }) => {
    patched = (await request.json()) as Record<string, unknown>;
    return HttpResponse.json({ id: 1, name: "WhatsApp CTC", ...patched });
  }),
);

beforeAll(() => server.listen({ onUnhandledRequest: "bypass" }));
afterEach(() => {
  patched = null;
  server.resetHandlers();
});
afterAll(() => server.close());

function renderPanel(current: number | null) {
  return render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <HandoffAssigneePanel accountId="1" inboxId={1} current={current} />
    </QueryClientProvider>,
  );
}

describe("HandoffAssigneePanel", () => {
  it("saves the chosen agent", async () => {
    renderPanel(null);
    await screen.findByRole("option", { name: "Sofía Costa" });
    fireEvent.change(screen.getByLabelText("Responsable"), {
      target: { value: "2" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Guardar" }));
    await waitFor(() => expect(patched).toEqual({ handoff_assignee_id: 2 }));
    expect(await screen.findByText("Guardado ✓")).toBeInTheDocument();
  });

  it("sends 0 to clear it when Nadie is picked", async () => {
    renderPanel(2);
    await screen.findByRole("option", { name: "Sofía Costa" });
    expect(screen.getByLabelText("Responsable")).toHaveValue("2");
    fireEvent.change(screen.getByLabelText("Responsable"), {
      target: { value: "" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Guardar" }));
    await waitFor(() => expect(patched).toEqual({ handoff_assignee_id: 0 }));
  });
});
