import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import {
  afterAll,
  afterEach,
  beforeAll,
  beforeEach,
  describe,
  expect,
  it,
} from "vitest";

import { ConversationView } from "./conversation-view";
import { INBOX_DETAILS_COLLAPSED_KEY } from "./inbox-shell";

const baseConversation = {
  id: 18,
  status: "open",
  priority: "medium",
  unread_count: 0,
  inbox_id: 2,
  labels: ["soporte"],
  meta: {
    sender: { id: 55, name: "Lucía Fernández" },
    channel: "Channel::Whatsapp",
    assignee: { id: 4, name: "Sofía Costa" },
    team: null,
  },
  messages: [],
  timestamp: 1_700_000_000,
  last_activity_at: 1_700_000_000,
  created_at: 1_700_000_000,
  additional_attributes: {},
};

const server = setupServer(
  http.get("*/api/v1/accounts/:accountId/conversations/18", () =>
    HttpResponse.json(baseConversation),
  ),
  http.get("*/api/v1/accounts/:accountId/conversations/18/messages", () =>
    HttpResponse.json({
      meta: {},
      payload: [
        {
          id: 300,
          content: "Buen día, quería consultar el estado del pedido",
          message_type: 0,
          content_type: "text",
          status: "sent",
          created_at: 1_700_000_000,
          private: false,
          sender: { id: 55, name: "Lucía Fernández", type: "contact" },
        },
      ],
    }),
  ),
  http.get("*/api/v1/accounts/:accountId/conversations/18/participants", () =>
    HttpResponse.json([{ id: 8, name: "Mateo Ruiz", email: "mateo@test.com" }]),
  ),
  http.get("*/api/v1/accounts/:accountId/contacts/55", () =>
    HttpResponse.json({
      payload: {
        id: 55,
        name: "Lucía Fernández",
        email: "lucia@ejemplo.com",
        phone_number: "+5491144556677",
        custom_attributes: {},
      },
    }),
  ),
  http.get("*/api/v1/accounts/:accountId/contacts/55/notes", () =>
    HttpResponse.json([]),
  ),
  http.get("*/api/v1/accounts/:accountId/conversations", () =>
    HttpResponse.json({
      data: {
        meta: {
          mine_count: 0,
          assigned_count: 0,
          unassigned_count: 0,
          all_count: 0,
        },
        payload: [],
      },
    }),
  ),
  http.get("*/api/v1/accounts/:accountId/custom_attribute_definitions", () =>
    HttpResponse.json([]),
  ),
  http.get("*/api/v1/accounts/:accountId/agents", () =>
    HttpResponse.json([
      {
        id: 4,
        name: "Sofía Costa",
        email: "sofia@test.com",
        availability_status: "online",
      },
    ]),
  ),
  http.get("*/api/v1/accounts/:accountId/teams", () => HttpResponse.json([])),
  http.get("*/api/v1/accounts/:accountId/labels", () =>
    HttpResponse.json({ payload: [{ id: 1, title: "soporte" }] }),
  ),
  http.get("*/api/v1/accounts/:accountId/macros", () =>
    HttpResponse.json({ payload: [] }),
  ),
  http.get("*/api/v1/accounts/:accountId/canned_responses", () =>
    HttpResponse.json([]),
  ),
);

beforeAll(() => server.listen({ onUnhandledRequest: "bypass" }));
beforeEach(() => window.localStorage.clear());
afterEach(() => {
  server.resetHandlers();
  window.localStorage.clear();
});
afterAll(() => server.close());

function renderView() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={qc}>
      <ConversationView accountId="1" displayId={18} />
    </QueryClientProvider>,
  );
}

describe("ConversationView — bloque de detalles plegable", () => {
  it("pliega AiHandoff, acciones y participantes juntos, muestra asignado y resumen de IA en el header y persiste", async () => {
    server.use(
      http.get("*/api/v1/accounts/:accountId/conversations/18", () =>
        HttpResponse.json({
          ...baseConversation,
          additional_attributes: {
            thread_control: {
              owner: "app",
              metadata: "Consulta por facturación",
            },
          },
        }),
      ),
    );

    const { unmount } = renderView();

    expect(
      await screen.findByText("La IA la derivó: Consulta por facturación"),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Asignar agente")).toBeInTheDocument();
    expect(await screen.findByText("Mateo Ruiz")).toBeInTheDocument();
    expect(
      screen.queryByTestId("collapsed-assignee-summary"),
    ).not.toBeInTheDocument();

    const toggleBtn = screen.getByRole("button", { name: "Ocultar detalles" });
    expect(toggleBtn).toHaveAttribute("title", "Ocultar detalles");
    expect(toggleBtn).toHaveAttribute("aria-expanded", "true");

    fireEvent.click(toggleBtn);

    expect(window.localStorage.getItem(INBOX_DETAILS_COLLAPSED_KEY)).toBe("1");
    expect(screen.getByTestId("conversation-details-panel")).toHaveAttribute(
      "data-collapsed",
      "true",
    );
    expect(
      screen.queryByRole("button", { name: "Devolver a la IA" }),
    ).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Asignar agente")).not.toBeInTheDocument();
    expect(screen.queryByText("Participantes")).not.toBeInTheDocument();

    expect(
      screen.getByTestId("collapsed-assignee-summary"),
    ).toHaveTextContent("Asignada a Sofía Costa");
    expect(screen.getByTestId("collapsed-ai-summary")).toHaveTextContent(
      "La IA la derivó: Consulta por facturación",
    );

    // Persiste al desmontar y volver a montar.
    unmount();
    renderView();

    expect(
      await screen.findByTestId("collapsed-assignee-summary"),
    ).toHaveTextContent("Asignada a Sofía Costa");
    expect(
      screen.getByRole("button", { name: "Mostrar detalles" }),
    ).toHaveAttribute("aria-expanded", "false");
  });

  it("muestra Sin asignar y Responde la IA de Meta en el header cuando está plegado", async () => {
    window.localStorage.setItem(INBOX_DETAILS_COLLAPSED_KEY, "1");
    server.use(
      http.get("*/api/v1/accounts/:accountId/conversations/18", () =>
        HttpResponse.json({
          ...baseConversation,
          meta: {
            ...baseConversation.meta,
            assignee: null,
          },
          additional_attributes: {
            thread_control: { owner: "ai_agent" },
          },
        }),
      ),
    );

    renderView();

    expect(
      await screen.findByText("Buen día, quería consultar el estado del pedido"),
    ).toBeInTheDocument();
    expect(
      screen.getByTestId("collapsed-assignee-summary"),
    ).toHaveTextContent("Sin asignar");
    expect(screen.getByTestId("collapsed-ai-summary")).toHaveTextContent(
      "Responde la IA de Meta",
    );
  });
});
