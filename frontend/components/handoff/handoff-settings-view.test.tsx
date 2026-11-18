import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import type { ReactNode } from "react";
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";

import { ContactHandoff } from "./contact-handoff";
import { HandoffSettingsView } from "./handoff-settings-view";

let savedRules: unknown = null;
let savedContact: unknown = null;
let role = 1;

const server = setupServer(
  http.get("*/api/v1/accounts/1/handoff", () =>
    HttpResponse.json({
      account: { user_id: 7, to_ai: false },
      labels: [{ label_id: 2, user_id: 7, to_ai: false }],
      ai_available: false,
    }),
  ),
  http.put("*/api/v1/accounts/1/handoff", async ({ request }) => {
    savedRules = await request.json();
    return HttpResponse.json({ ...(savedRules as object), ai_available: false });
  }),
  http.get("*/handoff/contacts/5", () =>
    HttpResponse.json({ contact: null, ai_available: false }),
  ),
  http.put("*/handoff/contacts/5", async ({ request }) => {
    savedContact = await request.json();
    return HttpResponse.json({ contact: savedContact });
  }),
  http.get("*/api/v1/accounts/1/labels", () =>
    HttpResponse.json({
      payload: [
        { id: 2, title: "admin" },
        { id: 3, title: "ventas" },
      ],
    }),
  ),
  http.get("*/api/v1/accounts/1/agents", () =>
    HttpResponse.json([
      { id: 7, name: "Sofía" },
      { id: 8, name: "Yamila" },
    ]),
  ),
  http.get("*/api/v1/profile", () =>
    HttpResponse.json({ data: { id: 1, name: "Owner", accounts: [{ id: 1, role }] } }),
  ),
);

beforeAll(() => server.listen({ onUnhandledRequest: "bypass" }));
afterEach(() => {
  server.resetHandlers();
  savedRules = null;
  savedContact = null;
  role = 1;
});
afterAll(() => server.close());

function renderWith(ui: ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

describe("HandoffSettingsView", () => {
  it("adds a label rule, orders it first and saves the general responsible", async () => {
    renderWith(<HandoffSettingsView accountId="1" />);
    await screen.findAllByRole("option", { name: "Yamila" }, { timeout: 3000 });
    await screen.findByRole("option", { name: "ventas" });

    fireEvent.click(screen.getByRole("button", { name: "Agregar regla" }));
    fireEvent.change(screen.getByLabelText("Etiqueta de la regla 2"), { target: { value: "3" } });
    fireEvent.change(screen.getByLabelText("Responsable de la regla 2"), { target: { value: "8" } });
    fireEvent.click(screen.getByRole("button", { name: "Subir la regla 2" }));
    fireEvent.change(screen.getByLabelText("Responsable general"), { target: { value: "" } });
    fireEvent.click(screen.getByRole("button", { name: "Guardar" }));

    expect(await screen.findByText("Guardado.")).toBeInTheDocument();
    expect(savedRules).toEqual({
      account: { user_id: null, to_ai: false },
      labels: [
        { label_id: 3, user_id: 8, to_ai: false },
        { label_id: 2, user_id: 7, to_ai: false },
      ],
    });
    // The AI isn't offered while the account doesn't have it.
    expect(screen.queryByRole("option", { name: "IA de AloStudio" })).toBeNull();
  });
});

describe("ContactHandoff", () => {
  it("lets an administrator pick the chat's responsible", async () => {
    renderWith(<ContactHandoff accountId="1" contactId={5} />);
    const select = await screen.findByLabelText("Derivación de este chat");
    await screen.findByRole("option", { name: "Sofía" });

    fireEvent.change(select, { target: { value: "7" } });

    await waitFor(() => expect(savedContact).toEqual({ user_id: 7, to_ai: false }));
  });

  it("shows nothing to agents", async () => {
    role = 0;
    renderWith(<ContactHandoff accountId="1" contactId={5} />);
    await new Promise((r) => setTimeout(r, 200));
    expect(screen.queryByLabelText("Derivación de este chat")).toBeNull();
  });
});
