import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";

import { ConversionsView } from "./conversions-view";

const settings = {
  enabled: false,
  currency: "USD",
  rules: {
    opportunity_created: "LeadSubmitted",
    opportunity_qualified: "QualifiedLead",
    opportunity_won: "Purchase",
    closing: {},
  },
  inboxes: [{ inbox_id: 3, name: "WhatsApp CTC", dataset_id: null }],
};

let saved: unknown = null;
let datasetCalls = 0;

const server = setupServer(
  http.get("*/conversions/settings", () => HttpResponse.json(settings)),
  http.get("*/closing_notes/settings", () =>
    HttpResponse.json({
      enabled: true,
      required: false,
      categories: ["Se inscribió", "Consulta respondida"],
    }),
  ),
  http.put("*/conversions/settings", async ({ request }) => {
    saved = await request.json();
    return HttpResponse.json({ ...settings, ...(saved as Record<string, unknown>) });
  }),
  http.post("*/conversions/inboxes/3/dataset", () => {
    datasetCalls += 1;
    if (datasetCalls === 1) {
      return HttpResponse.json(
        { message: "Missing permission", code: "conversions.refused" },
        { status: 502 },
      );
    }
    return HttpResponse.json({
      ...settings,
      inboxes: [{ inbox_id: 3, name: "WhatsApp CTC", dataset_id: "DS1" }],
    });
  }),
  http.get("*/conversions/events", () =>
    HttpResponse.json({
      payload: [
        {
          id: 2,
          conversation_id: 12,
          event_name: "Purchase",
          trigger: "closing",
          detail: "Se inscribió",
          value: 4500,
          currency: "UYU",
          status: "sent",
          error: null,
          created_at: "2026-11-17T10:00:00Z",
          sent_at: "2026-11-17T10:05:00Z",
        },
        {
          id: 1,
          conversation_id: 9,
          event_name: "LeadSubmitted",
          trigger: "opportunity_created",
          detail: "Curso de inglés",
          value: null,
          currency: null,
          status: "failed",
          error: "Missing permission",
          created_at: "2026-11-16T10:00:00Z",
          sent_at: null,
        },
      ],
    }),
  ),
);

beforeAll(() => server.listen({ onUnhandledRequest: "bypass" }));
afterEach(() => {
  server.resetHandlers();
  saved = null;
  datasetCalls = 0;
});
afterAll(() => server.close());

function renderView() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <ConversionsView accountId="1" />
    </QueryClientProvider>,
  );
}

describe("ConversionsView", () => {
  it("turns it on and maps a closing reason to a sale", async () => {
    renderView();
    fireEvent.click(await screen.findByRole("checkbox", { name: /Avisarle a Meta/ }));
    fireEvent.change(screen.getByLabelText("Moneda"), { target: { value: "uyu" } });
    fireEvent.change(screen.getByLabelText("Se crea una oportunidad en el CRM"), {
      target: { value: "" },
    });
    fireEvent.change(await screen.findByLabelText("Se inscribió"), {
      target: { value: "Purchase" },
    });
    fireEvent.change(screen.getByLabelText("Valor de Se inscribió"), { target: { value: "4500" } });
    fireEvent.click(screen.getByRole("button", { name: "Guardar" }));

    expect(await screen.findByText("Guardado.")).toBeInTheDocument();
    expect(saved).toEqual({
      enabled: true,
      currency: "UYU",
      rules: {
        opportunity_created: null,
        opportunity_qualified: "QualifiedLead",
        opportunity_won: "Purchase",
        closing: { "Se inscribió": { event: "Purchase", value: 4500 } },
      },
    });
  });

  it("maps a contact stage to an event", async () => {
    server.use(
      http.get("*/lifecycle/settings", () =>
        HttpResponse.json({
          enabled: true,
          stages: [
            { key: "new_lead", name: "Nuevo interesado", emoji: "🆕", description: "", kind: "stage", default: true },
            { key: "customer", name: "Cliente", emoji: "🤩", description: "", kind: "stage", default: false },
          ],
        }),
      ),
    );
    renderView();
    fireEvent.change(await screen.findByLabelText("Cliente"), { target: { value: "Purchase" } });
    fireEvent.change(screen.getByLabelText("Valor de Cliente"), { target: { value: "4500" } });
    fireEvent.click(screen.getByRole("button", { name: "Guardar" }));
    expect(await screen.findByText("Guardado.")).toBeInTheDocument();
    expect((saved as { rules: { lifecycle: unknown } }).rules.lifecycle).toEqual({
      customer: { event: "Purchase", value: 4500 },
    });
  });

  it("connects a number's dataset, saying why Meta refused first", async () => {
    renderView();
    fireEvent.click(await screen.findByRole("button", { name: "Conectar" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Meta no aceptó el pedido. (Missing permission)",
    );
    fireEvent.click(screen.getByRole("button", { name: "Conectar" }));
    expect(await screen.findByText("Conectado · dataset DS1")).toBeInTheDocument();
  });

  it("lists the latest events and how they went", async () => {
    renderView();
    expect(await screen.findByText("Venta (Purchase)")).toBeInTheDocument();
    expect(screen.getByText("Enviado")).toBeInTheDocument();
    expect(screen.getByText("Falló")).toBeInTheDocument();
    expect(screen.getByText("Missing permission")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "#12" })).toHaveAttribute(
      "href",
      "/accounts/1/conversations/12",
    );
  });
});
