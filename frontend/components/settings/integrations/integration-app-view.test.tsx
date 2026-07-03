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

import { IntegrationAppView } from "./integration-app-view";

const SLACK_ACTION =
  "https://slack.com/oauth/v2/authorize?scope=commands&client_id=CID&redirect_uri=http://app/cb";

const apps: Record<string, Record<string, unknown>> = {
  slack: {
    id: "slack",
    name: "Slack",
    description: "Slack relay",
    short_description: "Slack",
    enabled: true,
    action: SLACK_ACTION,
    hook_type: "account",
    hooks: [],
  },
  openai: {
    id: "openai",
    name: "OpenAI",
    description: "OpenAI assist",
    short_description: "OpenAI",
    enabled: true,
    action: "/openai",
    hook_type: "account",
    hooks: [],
  },
};

let hookBody: unknown = null;

const server = setupServer(
  http.get("*/integrations/apps/:appId", ({ params }) =>
    HttpResponse.json(apps[params.appId as string]),
  ),
  http.get("*/inboxes", () => HttpResponse.json({ payload: [] })),
  http.post("*/integrations/hooks", async ({ request }) => {
    hookBody = await request.json();
    return HttpResponse.json({
      id: 1,
      app_id: "openai",
      status: true,
      account_id: 1,
      hook_type: "account",
      inbox: null,
    });
  }),
);

beforeAll(() => server.listen({ onUnhandledRequest: "bypass" }));
afterEach(() => {
  server.resetHandlers();
  hookBody = null;
});
afterAll(() => server.close());

function wrap(ui: React.ReactElement) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

describe("IntegrationAppView connect", () => {
  it("renders an OAuth link for external-action apps", async () => {
    wrap(<IntegrationAppView accountId="1" appId="slack" />);

    const link = await screen.findByRole("link", {
      name: /Conectar con Slack/i,
    });
    expect(link.getAttribute("href")).toBe(SLACK_ACTION);
  });

  it("creates a hook from the inline settings form", async () => {
    wrap(<IntegrationAppView accountId="1" appId="openai" />);

    // Inline app → a Connect button that reveals the settings form.
    fireEvent.click(await screen.findByRole("button", { name: "Conectar" }));

    fireEvent.change(screen.getByLabelText("Clave 1"), {
      target: { value: "api_key" },
    });
    fireEvent.change(screen.getByLabelText("Valor 1"), {
      target: { value: "sk-123" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Conectar" }));

    await waitFor(() =>
      expect(hookBody).toEqual({
        hook: {
          app_id: "openai",
          hook_type: "account",
          settings: { api_key: "sk-123" },
        },
      }),
    );
  });
});
