import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";

import { WhatsappCallsCard } from "./whatsapp-calls-card";

let sent: unknown = null;
const off = {
  enabled: false,
  call_icon_visible: true,
  callback_requests: false,
  business_hours: false,
  restrictions: null,
};

const server = setupServer(
  http.get("*/calls/settings/3", () => HttpResponse.json(off)),
  http.put("*/calls/settings/3", async ({ request }) => {
    sent = await request.json();
    return HttpResponse.json({ ...(sent as object), restrictions: null });
  }),
);

beforeAll(() => server.listen({ onUnhandledRequest: "bypass" }));
afterEach(() => {
  server.resetHandlers();
  sent = null;
});
afterAll(() => server.close());

function renderCard() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <WhatsappCallsCard accountId="1" inboxId={3} />
    </QueryClientProvider>,
  );
}

describe("WhatsappCallsCard", () => {
  it("turns calls on, only during the inbox hours", async () => {
    renderCard();
    const enabled = await screen.findByRole("checkbox", { name: /Recibir llamadas/ });
    const hours = screen.getByRole("checkbox", { name: /Solo en el horario de atención/ });
    expect(hours).toBeDisabled();

    fireEvent.click(enabled);
    fireEvent.click(hours);
    fireEvent.click(screen.getByRole("button", { name: "Guardar" }));

    expect(await screen.findByText("Guardado en Meta.")).toBeInTheDocument();
    expect(sent).toEqual({
      enabled: true,
      call_icon_visible: true,
      callback_requests: false,
      business_hours: true,
    });
  });

  it("explains when the inbox is not a WhatsApp Cloud number", async () => {
    server.use(
      http.get("*/calls/settings/3", () =>
        HttpResponse.json(
          { message: "calls.not_connected", code: "calls.not_connected" },
          { status: 422 },
        ),
      ),
    );
    renderCard();
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "La bandeja no está conectada a un número de WhatsApp Cloud.",
    );
  });
});
