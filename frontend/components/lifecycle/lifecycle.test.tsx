import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";

import type { LifecycleStage } from "@/lib/api/lifecycle";

import { ContactStage } from "./contact-stage";
import { LifecycleReportCard } from "./lifecycle-report-card";
import { LifecycleSettingsView } from "./lifecycle-settings-view";

const stages: LifecycleStage[] = [
  { key: "new_lead", name: "Nuevo interesado", emoji: "🆕", description: "", kind: "stage", default: true },
  { key: "hot_lead", name: "Muy interesado", emoji: "🔥", description: "", kind: "stage", default: false },
  { key: "customer", name: "Cliente", emoji: "🤩", description: "", kind: "stage", default: false },
  { key: "cold_lead", name: "Se enfrió", emoji: "🧊", description: "", kind: "lost", default: false },
];

let enabled = true;
let saved: unknown = null;
let moved: unknown = null;

const server = setupServer(
  http.get("*/lifecycle/settings", () => HttpResponse.json({ enabled, stages })),
  http.put("*/lifecycle/settings", async ({ request }) => {
    saved = await request.json();
    return HttpResponse.json(saved as Record<string, unknown>);
  }),
  http.get("*/lifecycle/contacts/55", () =>
    HttpResponse.json({
      stage: stages[0],
      changed_at: "2026-11-10T12:00:00Z",
      changed_by: null,
    }),
  ),
  http.put("*/lifecycle/contacts/55", async ({ request }) => {
    moved = await request.json();
    return HttpResponse.json({
      stage: stages[1],
      changed_at: "2026-11-17T12:00:00Z",
      changed_by: { id: 5, name: "Sofía" },
    });
  }),
  http.get("*/lifecycle/report", () =>
    HttpResponse.json({
      days: 30,
      enabled,
      stages: stages.map((s, i) => ({ ...s, count: [3, 2, 1, 4][i], entered: [5, 2, 1, 4][i] })),
    }),
  ),
);

beforeAll(() => server.listen({ onUnhandledRequest: "bypass" }));
afterEach(() => {
  server.resetHandlers();
  enabled = true;
  saved = null;
  moved = null;
});
afterAll(() => server.close());

function renderWith(ui: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

describe("LifecycleSettingsView", () => {
  it("edits the stages: renames, adds, makes one lost, reorders and removes", async () => {
    enabled = false;
    renderWith(<LifecycleSettingsView accountId="1" />);
    fireEvent.click(await screen.findByRole("checkbox", { name: /Usar etapas/ }));
    fireEvent.change(screen.getByLabelText("Nombre de la etapa 1"), {
      target: { value: "Consultó" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Agregar etapa" }));
    fireEvent.change(screen.getByLabelText("Nombre de la etapa 5"), {
      target: { value: "Se inscribió" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Subir Se inscribió" }));
    fireEvent.click(screen.getByRole("button", { name: "Quitar Cliente" }));
    // The starting stage moves to "Muy interesado"; making it lost drops it.
    fireEvent.click(screen.getAllByRole("radio")[1]);
    fireEvent.change(screen.getByLabelText("Tipo de la etapa 2"), { target: { value: "lost" } });
    fireEvent.click(screen.getByRole("button", { name: "Guardar" }));

    expect(await screen.findByText("Guardado.")).toBeInTheDocument();
    const body = saved as { enabled: boolean; stages: LifecycleStage[] };
    expect(body.enabled).toBe(true);
    expect(body.stages.map((s) => [s.name, s.kind, s.default])).toEqual([
      ["Consultó", "stage", false],
      ["Muy interesado", "lost", false],
      ["Se inscribió", "stage", false],
      ["Se enfrió", "lost", false],
    ]);
  });

  it("explains a refusal", async () => {
    server.use(
      http.put("*/lifecycle/settings", () =>
        HttpResponse.json(
          { message: "duplicate_name", code: "lifecycle.duplicate_name" },
          { status: 422 },
        ),
      ),
    );
    renderWith(<LifecycleSettingsView accountId="1" />);
    await screen.findByRole("checkbox", { name: /Usar etapas/ });
    fireEvent.click(screen.getByRole("button", { name: "Guardar" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Hay dos etapas con el mismo nombre.",
    );
  });
});

describe("ContactStage", () => {
  it("moves the contact and says who did it", async () => {
    renderWith(<ContactStage accountId="1" contactId={55} conversationId={12} />);
    const select = await screen.findByLabelText("Etapa");
    await waitFor(() => expect(select).toHaveValue("new_lead"));
    expect(screen.getByRole("group", { name: "Etapas perdidas" })).toBeInTheDocument();
    fireEvent.change(select, { target: { value: "hot_lead" } });
    await waitFor(() => expect(moved).toEqual({ stage_key: "hot_lead", conversation_id: 12 }));
    expect(await screen.findByText(/La cambió Sofía el/)).toBeInTheDocument();
  });

  it("shows nothing while the account does not use stages", async () => {
    enabled = false;
    renderWith(<ContactStage accountId="1" contactId={55} />);
    await new Promise((r) => setTimeout(r, 50));
    expect(screen.queryByLabelText("Etapa")).not.toBeInTheDocument();
  });
});

describe("LifecycleReportCard", () => {
  it("counts contacts per stage", async () => {
    renderWith(<LifecycleReportCard accountId="1" days={30} />);
    expect(await screen.findByText("🔥 Muy interesado")).toBeInTheDocument();
    expect(screen.getByText("3 ahora · 5 entraron")).toBeInTheDocument();
    expect(screen.getByText("🧊 Se enfrió")).toBeInTheDocument();
  });

  it("points to the settings while stages are off", async () => {
    enabled = false;
    renderWith(<LifecycleReportCard accountId="1" days={30} />);
    expect(await screen.findByRole("link", { name: "Prenderlas en Ajustes" })).toHaveAttribute(
      "href",
      "/accounts/1/settings/lifecycle",
    );
  });
});
