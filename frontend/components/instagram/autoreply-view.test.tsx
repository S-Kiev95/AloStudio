import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";

import { AutoreplyView } from "./autoreply-view";

const ANSWER = {
  id: 1,
  trigger: "hacen envíos?",
  reply: "Sí, a todo el país.",
  enabled: true,
  post_id: null,
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

function renderView(postId?: number) {
  return render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <AutoreplyView accountId="1" postId={postId} />
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

describe("on one publication", () => {
  it("marks a shared answer as reaching every publication", async () => {
    renderView(7);
    expect(await screen.findByText(/Compartida/)).toBeInTheDocument();
  });

  it("does not mark an answer written for this publication", async () => {
    server.use(
      http.get("*/instagram_comment_replies", () =>
        HttpResponse.json([{ ...ANSWER, post_id: 7 }]),
      ),
    );
    renderView(7);
    expect(await screen.findByText("hacen envíos?")).toBeInTheDocument();
    expect(screen.queryByText(/Compartida/)).not.toBeInTheDocument();
  });

  it("scopes a new answer to that publication", async () => {
    let sent: Record<string, unknown> | null = null;
    server.use(
      http.post("*/instagram_comment_replies", async ({ request }) => {
        sent = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json({ ...ANSWER, id: 2, post_id: 7 });
      }),
    );
    renderView(7);
    fireEvent.change(await screen.findByLabelText(/Si preguntan algo como/), {
      target: { value: "cuánto sale?" },
    });
    fireEvent.change(screen.getByLabelText(/Responder/), {
      target: { value: "20 dólares" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Agregar/ }));

    await waitFor(() => expect(sent).not.toBeNull());
    expect(sent!.post_id).toBe(7);
  });

  it("keeps a shared answer shared when edited from a publication", async () => {
    // Editing must not silently narrow an answer other posts rely on.
    let sent: Record<string, unknown> | null = null;
    server.use(
      http.patch("*/instagram_comment_replies/1", async ({ request }) => {
        sent = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json(ANSWER);
      }),
    );
    renderView(7);
    fireEvent.click(await screen.findByRole("button", { name: "Editar" }));
    fireEvent.click(screen.getByRole("button", { name: /Guardar cambios/ }));

    await waitFor(() => expect(sent).not.toBeNull());
    expect(sent!.post_id).toBeNull();
  });
});
