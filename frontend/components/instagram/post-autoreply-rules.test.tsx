import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";

import { PostAutoreplyRules } from "./post-autoreply-rules";

let posted: Record<string, unknown> | null = null;

const server = setupServer(
  http.get("*/instagram_autoreply_status", () =>
    HttpResponse.json({ semantic_available: true }),
  ),
  http.get("*/instagram_comment_replies", () => HttpResponse.json([])),
  http.get("*/autoreply_rules", () => HttpResponse.json([])),
  http.post("*/autoreply_rules", async ({ request }) => {
    posted = (await request.json()) as Record<string, unknown>;
    return HttpResponse.json({ id: 1, post_id: 5, ...posted });
  }),
);

beforeAll(() => server.listen({ onUnhandledRequest: "bypass" }));
afterEach(() => {
  posted = null;
  server.resetHandlers();
});
afterAll(() => server.close());

function renderRules() {
  return render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <PostAutoreplyRules accountId="1" postId={5} />
    </QueryClientProvider>,
  );
}

async function openForm() {
  fireEvent.click(await screen.findByRole("button", { name: /Agregar regla/ }));
}

describe("PostAutoreplyRules", () => {
  it("saves a keyword rule", async () => {
    renderRules();
    await openForm();
    fireEvent.change(screen.getByLabelText(/Palabras que lo disparan/), {
      target: { value: "info, link" },
    });
    fireEvent.change(screen.getByLabelText(/Responder/), {
      target: { value: "ahí va: ejemplo.com" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Guardar regla/ }));

    await waitFor(() => expect(posted).not.toBeNull());
    expect(posted!.match_type).toBe("keyword");
    expect(posted!.keywords).toBe("info, link");
  });

  it("saves a similarity rule, which has no text of its own", async () => {
    // The mode the user reported: nothing to type, so nothing to validate.
    renderRules();
    await openForm();
    fireEvent.click(screen.getByRole("button", { name: /Por similitud/ }));
    fireEvent.click(screen.getByRole("button", { name: /Guardar regla/ }));

    await waitFor(() => expect(posted).not.toBeNull());
    expect(posted!.match_type).toBe("semantic");
    expect(posted!.reply_text).toBeNull();
  });

  it("saves a catch-all rule", async () => {
    renderRules();
    await openForm();
    fireEvent.click(screen.getByRole("button", { name: /^Todos/ }));
    fireEvent.change(screen.getByLabelText(/Responder/), {
      target: { value: "¡Gracias por comentar!" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Guardar regla/ }));

    await waitFor(() => expect(posted).not.toBeNull());
    expect(posted!.match_type).toBe("all");
  });

  it("re-reads the list after saving, so the rule replaces the empty state", async () => {
    // The list is served empty until the save lands, so the assertion can
    // only pass if the mutation actually invalidated and refetched it.
    let listed = 0;
    server.use(
      http.get("*/autoreply_rules", () => {
        listed += 1;
        return HttpResponse.json(
          listed > 1
            ? [
                {
                  id: 1,
                  post_id: 5,
                  match_type: "semantic",
                  keywords: null,
                  reply_text: null,
                  delivery: "dm",
                  enabled: true,
                },
              ]
            : [],
        );
      }),
    );
    renderRules();
    expect(await screen.findByText(/^Sin reglas/)).toBeInTheDocument();

    await openForm();
    fireEvent.click(screen.getByRole("button", { name: /Por similitud/ }));
    fireEvent.click(screen.getByRole("button", { name: /Guardar regla/ }));

    await waitFor(() =>
      expect(screen.queryByText(/^Sin reglas/)).not.toBeInTheDocument(),
    );
    expect(screen.getByText("Usa las respuestas preparadas")).toBeInTheDocument();
  });

  it("surfaces a rejected save instead of failing quietly", async () => {
    server.use(
      http.post("*/autoreply_rules", () =>
        HttpResponse.json(
          { message: "Falta el texto de la respuesta" },
          { status: 422 },
        ),
      ),
    );
    renderRules();
    await openForm();
    fireEvent.click(screen.getByRole("button", { name: /Por similitud/ }));
    fireEvent.click(screen.getByRole("button", { name: /Guardar regla/ }));

    expect(await screen.findByRole("alert")).toBeInTheDocument();
  });
});
