import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";

import { AutoreplyView } from "./autoreply-view";

const INBOX = {
  id: 5,
  name: "yoruguamaps",
  channel_type: "Channel::Instagram",
  channel_id: 9,
};

function config(over: Record<string, unknown> = {}) {
  return {
    channel_instagram_id: 9,
    mode: "off",
    text: null,
    max_distance: 0.35,
    semantic_available: true,
    ...over,
  };
}

const server = setupServer(
  http.get("*/inboxes", () => HttpResponse.json({ payload: [INBOX] })),
  http.get("*/autoreply", () => HttpResponse.json(config())),
  http.get("*/instagram_comment_replies", () => HttpResponse.json([])),
);

beforeAll(() => server.listen({ onUnhandledRequest: "bypass" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

function renderView() {
  return render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <AutoreplyView accountId="1" />
    </QueryClientProvider>,
  );
}

describe("AutoreplyView", () => {
  it("offers the three modes and marks the active one", async () => {
    renderView();
    expect(await screen.findByText("Desactivado")).toBeInTheDocument();
    expect(screen.getByText("Respuesta fija")).toBeInTheDocument();
    expect(screen.getByText("Por similitud")).toBeInTheDocument();
    // "off" is the configured mode, so its button is the pressed one.
    const off = screen.getByText("Desactivado").closest("button");
    expect(off).toHaveAttribute("aria-pressed", "true");
  });

  it("disables the semantic mode and says why when there is no API key", async () => {
    server.use(
      http.get("*/autoreply", () =>
        HttpResponse.json(config({ semantic_available: false })),
      ),
    );
    renderView();

    // Wait on the explanation rather than the button: the mode buttons are
    // static and render before the config query resolves, so asserting on
    // them first would check the pre-load state.
    // An admin must be told why, not left with a dead option.
    expect(await screen.findByText(/clave de OpenAI/)).toBeInTheDocument();
    expect(screen.getByText("Por similitud").closest("button")).toBeDisabled();
  });

  it("warns that the semantic mode answers nothing with an empty library", async () => {
    server.use(
      http.get("*/autoreply", () => HttpResponse.json(config({ mode: "semantic" }))),
    );
    renderView();
    expect(
      await screen.findByText(/este modo no contesta nada/),
    ).toBeInTheDocument();
  });

  it("prompts for connecting an account when none exists", async () => {
    server.use(http.get("*/inboxes", () => HttpResponse.json({ payload: [] })));
    renderView();
    expect(
      await screen.findByText(/Conectá una cuenta de Instagram/),
    ).toBeInTheDocument();
  });
});
