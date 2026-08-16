import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";

import { PostAutoreplyRules } from "./post-autoreply-rules";

let posted: Record<string, unknown> | null = null;
let patched: Record<string, unknown> | null = null;

const KEYWORD_RULE = {
  id: 9,
  post_id: 5,
  match_type: "keyword",
  keywords: "info, link",
  reply_text: "Ahí va: ejemplo.com",
  delivery: "dm",
  enabled: true,
};

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
  http.patch("*/autoreply_rules/:id", async ({ request }) => {
    patched = (await request.json()) as Record<string, unknown>;
    return HttpResponse.json({ ...KEYWORD_RULE, ...patched });
  }),
);

beforeAll(() => server.listen({ onUnhandledRequest: "bypass" }));
afterEach(() => {
  posted = null;
  patched = null;
  server.resetHandlers();
});
afterAll(() => server.close());

function renderRules() {
  return render(
    <QueryClientProvider
      client={
        new QueryClient({ defaultOptions: { queries: { retry: false } } })
      }
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
    expect(
      screen.getByText("Usa las respuestas preparadas"),
    ).toBeInTheDocument();
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

describe("editing a rule", () => {
  function withRule() {
    server.use(
      http.get("*/autoreply_rules", () => HttpResponse.json([KEYWORD_RULE])),
    );
  }

  it("switches a private reply to a public one", async () => {
    // The change the user asked for: a saved rule was unreachable, the
    // list only offered delete.
    withRule();
    renderRules();
    fireEvent.click(
      await screen.findByRole("button", { name: /Editar regla/ }),
    );
    fireEvent.click(screen.getByRole("button", { name: /Respuesta pública/ }));
    fireEvent.click(screen.getByRole("button", { name: /Guardar cambios/ }));

    await waitFor(() => expect(patched).not.toBeNull());
    expect(patched!.delivery).toBe("public");
    expect(patched!.match_type).toBe("keyword");
  });

  it("loads the rule's own values into the form", async () => {
    withRule();
    renderRules();
    fireEvent.click(
      await screen.findByRole("button", { name: /Editar regla/ }),
    );
    expect(screen.getByLabelText(/Palabras que lo disparan/)).toHaveValue(
      "info, link",
    );
    expect(screen.getByLabelText(/Responder/)).toHaveValue(
      "Ahí va: ejemplo.com",
    );
    expect(
      screen.getByRole("button", { name: /Mensaje privado/ }),
    ).toHaveAttribute("aria-pressed", "true");
  });

  it("updates instead of creating a second rule", async () => {
    withRule();
    renderRules();
    fireEvent.click(
      await screen.findByRole("button", { name: /Editar regla/ }),
    );
    fireEvent.change(screen.getByLabelText(/Palabras que lo disparan/), {
      target: { value: "becas" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Guardar cambios/ }));

    await waitFor(() => expect(patched).not.toBeNull());
    expect(patched!.keywords).toBe("becas");
    expect(posted).toBeNull();
  });

  it("does not re-enable a rule that was turned off", async () => {
    server.use(
      http.get("*/autoreply_rules", () =>
        HttpResponse.json([{ ...KEYWORD_RULE, enabled: false }]),
      ),
    );
    renderRules();
    fireEvent.click(
      await screen.findByRole("button", { name: /Editar regla/ }),
    );
    fireEvent.click(screen.getByRole("button", { name: /Guardar cambios/ }));

    await waitFor(() => expect(patched).not.toBeNull());
    expect(patched!.enabled).toBe(false);
  });

  it("names the form so an edit is not mistaken for a new rule", async () => {
    withRule();
    renderRules();
    fireEvent.click(
      await screen.findByRole("button", { name: /Editar regla/ }),
    );
    expect(screen.getByText("Editar regla")).toBeInTheDocument();
  });

  it("leaves the rule alone when the edit is cancelled", async () => {
    withRule();
    renderRules();
    fireEvent.click(
      await screen.findByRole("button", { name: /Editar regla/ }),
    );
    fireEvent.change(screen.getByLabelText(/Palabras que lo disparan/), {
      target: { value: "otra cosa" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Cancelar/ }));

    expect(patched).toBeNull();
    // And the next "Agregar regla" starts blank, not on the abandoned edit.
    fireEvent.click(screen.getByRole("button", { name: /Agregar regla/ }));
    expect(screen.getByLabelText(/Palabras que lo disparan/)).toHaveValue("");
  });
});
