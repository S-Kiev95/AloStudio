import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";

import { AutoreplyView } from "./autoreply-view";

const ANSWER = {
  id: 1,
  trigger: "hacen envíos?",
  reply: "Sí, a todo el país.",
  enabled: true,
  indexed: true,
};

function statusHandler(available: boolean) {
  return http.get("*/instagram_autoreply_status", () =>
    HttpResponse.json({ semantic_available: available }),
  );
}

const server = setupServer(
  statusHandler(true),
  http.get("*/instagram_comment_replies", () => HttpResponse.json([ANSWER])),
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

describe("AutoreplyView (prepared answers)", () => {
  it("lists the answers", async () => {
    renderView();
    expect(await screen.findByText("hacen envíos?")).toBeInTheDocument();
    expect(screen.getByText("Sí, a todo el país.")).toBeInTheDocument();
  });

  it("flags an answer that was never embedded", async () => {
    // Without an embedding the answer can never match, so it would look
    // configured while silently doing nothing.
    server.use(
      http.get("*/instagram_comment_replies", () =>
        HttpResponse.json([{ ...ANSWER, indexed: false }]),
      ),
    );
    renderView();
    expect(await screen.findByText(/Sin indexar/)).toBeInTheDocument();
  });

  it("says an empty library answers nothing", async () => {
    server.use(
      http.get("*/instagram_comment_replies", () => HttpResponse.json([])),
    );
    renderView();
    expect(
      await screen.findByText(/este modo no contesta nada/),
    ).toBeInTheDocument();
  });
});

describe("when the server has no embedding provider", () => {
  beforeAll(() => server.use(statusHandler(false)));

  it("says so instead of blaming the answer", async () => {
    server.use(
      http.get("*/instagram_comment_replies", () =>
        HttpResponse.json([{ ...ANSWER, indexed: false }]),
      ),
    );
    renderView();
    expect(
      await screen.findByText(/no está configurada en este servidor/),
    ).toBeInTheDocument();
    // "Volvé a guardarla" would send the admin in a circle — re-saving
    // cannot embed anything while the provider is missing.
    expect(screen.queryByText(/Volvé a guardarla/)).not.toBeInTheDocument();
  });
});
