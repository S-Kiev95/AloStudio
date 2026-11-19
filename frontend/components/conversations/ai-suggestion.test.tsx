import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";

import { MessageComposer } from "./message-composer";

let sent: Record<string, unknown> | null = null;
let discarded: string | null = null;
let suggestion: unknown = {
  id: 9,
  content: "Sí, abrimos el sábado de 9 a 13.",
  summary: null,
  handoff: false,
  created_at: null,
};

const server = setupServer(
  http.get("*/canned_responses", () => HttpResponse.json([])),
  http.get("*/conversations/1/ai_reply", () => HttpResponse.json({ ai_reply: suggestion })),
  http.post("*/conversations/1/ai_reply/:id/discard", ({ params }) => {
    discarded = String(params.id);
    suggestion = null;
    return HttpResponse.json({ ai_reply: null });
  }),
  http.post("*/conversations/1/messages", async ({ request }) => {
    sent = (await request.json()) as Record<string, unknown>;
    return HttpResponse.json({ id: 50 });
  }),
);

beforeAll(() => server.listen({ onUnhandledRequest: "bypass" }));
afterEach(() => {
  server.resetHandlers();
  sent = null;
  discarded = null;
});
afterAll(() => server.close());

function wrap(ui: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

describe("AI suggestion above the composer", () => {
  it("puts the suggestion in the box and sends it marked", async () => {
    wrap(<MessageComposer accountId="1" displayId={1} />);
    expect(await screen.findByText("Sí, abrimos el sábado de 9 a 13.")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Usar" }));
    const box = screen.getByLabelText("Respuesta");
    expect(box).toHaveValue("Sí, abrimos el sábado de 9 a 13.");
    // While it is in the box, the card is gone.
    expect(screen.queryByRole("region", { name: "Respuesta propuesta por la IA" })).toBeNull();

    fireEvent.change(box, { target: { value: "Sí, abrimos el sábado de 9 a 12." } });
    fireEvent.keyDown(box, { key: "Enter" });

    await waitFor(() => expect(sent).not.toBeNull());
    expect(sent).toMatchObject({
      content: "Sí, abrimos el sábado de 9 a 12.",
      content_attributes: { ai_reply_id: 9 },
    });
  });

  it("discards it", async () => {
    suggestion = { id: 10, content: "Hola", summary: null, handoff: false, created_at: null };
    wrap(<MessageComposer accountId="1" displayId={1} />);
    fireEvent.click(await screen.findByRole("button", { name: "Descartar" }));

    await waitFor(() => expect(discarded).toBe("10"));
    await waitFor(() => expect(screen.queryByText("Hola")).toBeNull());
  });

  it("lists what the AI would also do", async () => {
    suggestion = {
      id: 11,
      content: "Te agendé el martes a las 10.",
      summary: null,
      handoff: false,
      actions: ["Cita «Entrevista» el 2026-11-24 10:00"],
      created_at: null,
    };
    wrap(<MessageComposer accountId="1" displayId={1} />);
    expect(await screen.findByText("La IA también haría:")).toBeInTheDocument();
    expect(screen.getByText("Cita «Entrevista» el 2026-11-24 10:00")).toBeInTheDocument();
  });

  it("a plain message carries no suggestion", async () => {
    suggestion = null;
    wrap(<MessageComposer accountId="1" displayId={1} />);
    const box = screen.getByLabelText("Respuesta");
    fireEvent.change(box, { target: { value: "Buen día" } });
    fireEvent.keyDown(box, { key: "Enter" });

    await waitFor(() => expect(sent).not.toBeNull());
    expect(sent?.content_attributes).toBeUndefined();
  });
});
