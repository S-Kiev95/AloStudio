import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";

import { InboxBotPanel } from "./inbox-bot-panel";

let attached: unknown = undefined;

const server = setupServer(
  http.get("*/api/v1/accounts/1/agent_bots", () =>
    HttpResponse.json([
      { id: 4, name: "Sofi", bot_type: "ai", bot_config: {}, system_bot: false },
      { id: 5, name: "Hook", bot_type: "webhook", bot_config: {}, system_bot: false },
    ]),
  ),
  http.get("*/inboxes/7/agent_bot", () => HttpResponse.json({ agent_bot: null })),
  http.post("*/inboxes/7/set_agent_bot", async ({ request }) => {
    attached = ((await request.json()) as { agent_bot: unknown }).agent_bot;
    return HttpResponse.json({});
  }),
);

beforeAll(() => server.listen({ onUnhandledRequest: "bypass" }));
afterEach(() => {
  server.resetHandlers();
  attached = undefined;
});
afterAll(() => server.close());

describe("InboxBotPanel", () => {
  it("attaches the AI to the inbox", async () => {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={qc}>
        <InboxBotPanel accountId="1" inboxId={7} />
      </QueryClientProvider>,
    );
    await screen.findByRole("option", { name: "Sofi (IA)" });
    fireEvent.change(screen.getByLabelText("Bot"), { target: { value: "4" } });
    fireEvent.click(screen.getByRole("button", { name: "Guardar" }));

    await waitFor(() => expect(attached).toBe(4));
    expect(await screen.findByText("Guardado.")).toBeInTheDocument();
  });
});
