import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from "vitest";

import { HelpButton } from "./help-button";

vi.mock("next/navigation", () => ({
  usePathname: () => "/accounts/1/settings/lifecycle",
}));

let enabled = true;
let asked: unknown = null;
let reply: Record<string, unknown> = {};
let status = 200;

const server = setupServer(
  http.get("*/help_assistant", () => HttpResponse.json({ enabled, question_max: 300 })),
  http.post("*/help_assistant", async ({ request }) => {
    asked = await request.json();
    return HttpResponse.json(reply, { status });
  }),
);

beforeAll(() => server.listen({ onUnhandledRequest: "bypass" }));
afterEach(() => {
  server.resetHandlers();
  enabled = true;
  asked = null;
  status = 200;
});
afterAll(() => server.close());

function renderButton() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <HelpButton accountId="1" />
    </QueryClientProvider>,
  );
}

async function askQuestion(text: string) {
  fireEvent.click((await screen.findAllByLabelText("Ayuda"))[0]);
  fireEvent.change(screen.getByLabelText("Tu pregunta"), { target: { value: text } });
  fireEvent.click(screen.getByRole("button", { name: "Preguntar" }));
}

describe("HelpButton", () => {
  it("is hidden while the local model is not set up", async () => {
    enabled = false;
    renderButton();
    await new Promise((r) => setTimeout(r, 50));
    expect(screen.queryAllByLabelText("Ayuda")).toHaveLength(0);
  });

  it("answers with a link to the screen and sends where the user is", async () => {
    reply = {
      known: true,
      answer: 'Entrá a Ajustes → Notas de cierre y marcá "Obligatorio".',
      screen: { key: "ajustes_notas_cierre", label: "Ajustes → Notas de cierre", path: "settings/closing_notes" },
      note: null,
      seconds: 9.5,
    };
    renderButton();
    await askQuestion("como pido un motivo al cerrar");
    expect(await screen.findByText(/marcá "Obligatorio"/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Ir a Ajustes → Notas de cierre/ })).toHaveAttribute(
      "href",
      "/accounts/1/settings/closing_notes",
    );
    expect(asked).toEqual({
      question: "como pido un motivo al cerrar",
      page: "/accounts/1/settings/lifecycle",
    });
  });

  it("says when the model is still getting ready", async () => {
    status = 503;
    reply = { message: "busy", code: "help_assistant.busy" };
    renderButton();
    await askQuestion("hola");
    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent("La ayuda se está preparando"),
    );
  });
});
