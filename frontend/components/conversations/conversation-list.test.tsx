import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import {
  afterAll,
  afterEach,
  beforeAll,
  describe,
  expect,
  it,
} from "vitest";

import { ConversationList } from "./conversation-list";

const conversation = {
  id: 42,
  status: "open",
  priority: null,
  unread_count: 2,
  inbox_id: 1,
  labels: [],
  meta: { sender: { id: 1, name: "Diana" }, channel: "api" },
  messages: [],
  last_non_activity_message: { content: "Hola, necesito ayuda" },
  timestamp: 1_700_000_000,
  last_activity_at: 1_700_000_000,
  created_at: 1_700_000_000,
};

const server = setupServer(
  http.get("*/custom_filters", () => HttpResponse.json([])),
  http.get("*/agents", () => HttpResponse.json([])),
  http.get("*/labels", () => HttpResponse.json({ payload: [] })),
  http.get("*/conversations", () =>
    HttpResponse.json({
      data: {
        meta: {
          mine_count: 1,
          assigned_count: 1,
          unassigned_count: 0,
          all_count: 1,
        },
        payload: [conversation],
      },
    }),
  ),
);

beforeAll(() => server.listen({ onUnhandledRequest: "bypass" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

function renderWithQuery(ui: React.ReactElement) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={qc}>{ui}</QueryClientProvider>,
  );
}

describe("ConversationList", () => {
  it("renders conversations returned by the API", async () => {
    renderWithQuery(<ConversationList accountId="1" />);
    expect(await screen.findByText("Diana")).toBeInTheDocument();
    expect(
      await screen.findByText("Hola, necesito ayuda"),
    ).toBeInTheDocument();
    // unread badge
    expect(await screen.findByText("2")).toBeInTheDocument();
  });

  it("bulk-assigns selected conversations to an agent", async () => {
    let assignBody: unknown = null;
    server.use(
      http.get("*/agents", () =>
        HttpResponse.json([{ id: 9, name: "Pedro" }]),
      ),
      http.post("*/bulk_actions", async ({ request }) => {
        assignBody = await request.json();
        return HttpResponse.json({ payload: { updated: [42] } });
      }),
    );
    renderWithQuery(<ConversationList accountId="1" />);

    // Select the conversation, then pick an agent in the bulk toolbar.
    fireEvent.click(await screen.findByLabelText("Seleccionar Diana"));
    fireEvent.change(await screen.findByLabelText("Asignar a"), {
      target: { value: "9" },
    });

    await waitFor(() => expect(assignBody).not.toBeNull());
    expect(assignBody).toEqual({
      type: "Conversation",
      ids: [42],
      fields: { assignee_id: 9 },
    });
  });

  it("bulk-adds a label to selected conversations", async () => {
    let labelBody: unknown = null;
    server.use(
      http.get("*/labels", () =>
        HttpResponse.json({ payload: [{ id: 3, title: "urgent" }] }),
      ),
      http.post("*/bulk_actions", async ({ request }) => {
        labelBody = await request.json();
        return HttpResponse.json({ payload: { updated: [42] } });
      }),
    );
    renderWithQuery(<ConversationList accountId="1" />);

    fireEvent.click(await screen.findByLabelText("Seleccionar Diana"));
    fireEvent.change(await screen.findByLabelText("Etiquetar"), {
      target: { value: "urgent" },
    });

    await waitFor(() => expect(labelBody).not.toBeNull());
    expect(labelBody).toEqual({
      type: "Conversation",
      ids: [42],
      fields: {},
      labels: { add: ["urgent"] },
    });
  });
});
