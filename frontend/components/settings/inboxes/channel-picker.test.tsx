import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";

import { ChannelPicker } from "./channel-picker";

const server = setupServer();
beforeAll(() => server.listen({ onUnhandledRequest: "bypass" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

function withPlan({ multitenant, channels }: { multitenant: boolean; channels: string[] | null }) {
  server.use(
    http.get("*/api/v1/installation/public", () =>
      HttpResponse.json({ signup_enabled: true, multitenant }),
    ),
    http.get("*/api/v1/accounts/1/billing", () =>
      HttpResponse.json({
        status: "active",
        has_access: true,
        allows: { inbox_channels: channels, networks: null, whatsapp_calls: false },
      }),
    ),
  );
}

function renderPicker() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <ChannelPicker accountId="1" />
    </QueryClientProvider>,
  );
}

describe("ChannelPicker and the plan (F2)", () => {
  it("dims the channels the plan doesn't include, with a link to the plans", async () => {
    withPlan({ multitenant: true, channels: ["api", "email", "facebook", "instagram", "web_widget", "whatsapp"] });
    renderPicker();

    expect((await screen.findAllByText(/Tu plan no lo incluye/)).length).toBeGreaterThan(0);
    const see = screen.getAllByRole("link", { name: "Ver planes" });
    expect(see[0]).toHaveAttribute("href", "/accounts/1/settings/billing");
    // WhatsApp stays a link to its form; Telegram is not a link any more.
    const links = screen.getAllByRole("link").map((a) => a.getAttribute("href"));
    expect(links).toContain("/accounts/1/settings/inboxes/new/whatsapp");
    expect(links).not.toContain("/accounts/1/settings/inboxes/new/telegram");
  });

  it("offers every channel on a single-tenant install", async () => {
    withPlan({ multitenant: false, channels: ["whatsapp"] });
    renderPicker();

    expect(await screen.findByRole("link", { name: /Telegram/ })).toHaveAttribute(
      "href",
      "/accounts/1/settings/inboxes/new/telegram",
    );
    expect(screen.queryByText(/Tu plan no lo incluye/)).toBeNull();
  });
});
