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

import { useInstagramInboxes } from "./instagram";

const server = setupServer(
  http.get("*/inboxes", () =>
    HttpResponse.json({
      payload: [
        { id: 1, channel_id: 10, name: "IG Tienda", channel_type: "Channel::Instagram" },
        { id: 2, channel_id: 11, name: "API", channel_type: "Channel::Api" },
        { id: 3, channel_id: 12, name: "IG Soporte", channel_type: "Channel::Instagram" },
      ],
    }),
  ),
);

beforeAll(() => server.listen({ onUnhandledRequest: "bypass" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

function wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

describe("useInstagramInboxes", () => {
  it("returns only Instagram inboxes", async () => {
    const { result } = renderHook(() => useInstagramInboxes("1"), { wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toHaveLength(2);
    expect(
      result.current.data?.every((i) => i.channel_type === "Channel::Instagram"),
    ).toBe(true);
  });
});
