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

const server = setupServer(
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

describe("AutoreplyView (prepared answers library)", () => {
  it("lists the account's prepared answers", async () => {
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
