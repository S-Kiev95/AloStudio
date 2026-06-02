import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
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

import {
  useNotificationSettings,
  useNotifications,
  useUnreadCount,
} from "./notifications";

const server = setupServer(
  http.get("*/api/v1/accounts/1/notifications", () =>
    HttpResponse.json({
      meta: { count: 2, unread_count: 1, current_page: 1 },
      payload: [
        {
          id: 10,
          notification_type: "conversation_creation",
          primary_actor_type: "Conversation",
          primary_actor_id: 99,
          secondary_actor_type: null,
          secondary_actor_id: null,
          read_at: null,
          snoozed_until: null,
          last_activity_at: 1700000000,
          created_at: 1700000000,
          account_id: 1,
          user_id: 7,
          meta: {},
        },
      ],
    }),
  ),
  http.get("*/api/v1/accounts/1/notifications/unread_count", () =>
    HttpResponse.json(3),
  ),
  http.get("*/api/v1/accounts/1/notification_settings", () =>
    HttpResponse.json({
      id: 1,
      account_id: 1,
      user_id: 7,
      selected_email_flags: ["conversation_creation"],
      selected_push_flags: [
        "conversation_creation",
        "conversation_assignment",
      ],
    }),
  ),
);

beforeAll(() => server.listen({ onUnhandledRequest: "bypass" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

function wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

describe("notifications hooks", () => {
  it("useNotifications unwraps the index envelope", async () => {
    const { result } = renderHook(() => useNotifications("1"), { wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.meta.unread_count).toBe(1);
    expect(result.current.data?.payload[0].notification_type).toBe(
      "conversation_creation",
    );
  });

  it("useUnreadCount returns a bare number", async () => {
    const { result } = renderHook(() => useUnreadCount("1"), { wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toBe(3);
  });

  it("useNotificationSettings exposes selected_email/push_flags", async () => {
    const { result } = renderHook(() => useNotificationSettings("1"), {
      wrapper,
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.selected_email_flags).toEqual([
      "conversation_creation",
    ]);
    expect(result.current.data?.selected_push_flags).toHaveLength(2);
  });
});
