import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from "vitest";

const requestDial = vi.fn();
vi.mock("./dialer", () => ({ requestDial: (...args: unknown[]) => requestDial(...args) }));

import { CallButton } from "./call-button";

let permission: Record<string, unknown> = {};
let asked: unknown = null;
const server = setupServer(
  http.get("*/calls/permission", () => HttpResponse.json(permission)),
  http.post("*/calls/permission_request", async ({ request }) => {
    asked = await request.json();
    return HttpResponse.json({ message_id: 99 });
  }),
);

beforeAll(() => server.listen({ onUnhandledRequest: "bypass" }));
afterEach(() => {
  server.resetHandlers();
  asked = null;
  requestDial.mockClear();
});
afterAll(() => server.close());

function renderButton() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <CallButton accountId="1" conversationId={12} contactName="Lucía Pereira" />
    </QueryClientProvider>,
  );
}

describe("CallButton", () => {
  it("calls when the customer allows it", async () => {
    permission = { status: "permanent", expires_at: null, can_call: true, can_request: false };
    renderButton();
    fireEvent.click(screen.getByRole("button", { name: "Llamar por WhatsApp" }));
    expect(await screen.findByText("Aceptó que lo llamen siempre.")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Llamar ahora/ }));
    expect(requestDial).toHaveBeenCalledWith({
      conversationId: 12,
      contactName: "Lucía Pereira",
      thumbnail: undefined,
    });
  });

  it("asks for permission when there is none", async () => {
    permission = { status: "no_permission", expires_at: null, can_call: false, can_request: true };
    renderButton();
    fireEvent.click(screen.getByRole("button", { name: "Llamar por WhatsApp" }));
    expect(await screen.findByText(/Todavía no aceptó que lo llamen/)).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Mensaje del pedido"), {
      target: { value: "¿Te llamamos por tu inscripción?" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Pedir permiso para llamar" }));
    expect(
      await screen.findByText("Pedido enviado. Cuando acepte, vas a poder llamar."),
    ).toBeInTheDocument();
    expect(asked).toEqual({ conversation_id: 12, text: "¿Te llamamos por tu inscripción?" });
    expect(requestDial).not.toHaveBeenCalled();
  });

  it("explains when WhatsApp does not allow asking again yet", async () => {
    permission = { status: "no_permission", expires_at: null, can_call: false, can_request: false };
    renderButton();
    fireEvent.click(screen.getByRole("button", { name: "Llamar por WhatsApp" }));
    expect(await screen.findByText(/un pedido por día y dos por semana/)).toBeInTheDocument();
  });
});
