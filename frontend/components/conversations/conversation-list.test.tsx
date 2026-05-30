import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
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
});
