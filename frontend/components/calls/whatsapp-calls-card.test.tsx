import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
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
  recording_allowed: false,
  record: false,
  transcribe: false,
  purpose: "control de calidad y seguimiento de tu consulta",
  announcement_language: "es",
  missed_call_reply: true,
  missed_call_text: "¡Hola! Vimos tu llamada y no pudimos atenderla. Te llamamos en unos minutos.",
};

const server = setupServer(
  http.get("*/calls/settings/3", () => HttpResponse.json(off)),
  http.put("*/calls/settings/3", async ({ request }) => {
    sent = await request.json();
    return HttpResponse.json({ ...off, ...(sent as object), restrictions: null });
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
      missed_call_reply: true,
      missed_call_text: off.missed_call_text,
      ai_mode: "off",
    });
  });

  it("changes what a customer nobody answered reads, or turns it off", async () => {
    server.use(http.get("*/calls/settings/3", () => HttpResponse.json({ ...off, enabled: true })));
    renderCard();
    const text = await screen.findByLabelText("Mensaje");
    expect(text).toHaveValue(off.missed_call_text);
    fireEvent.change(text, { target: { value: "Ya te llamamos, gracias por esperar." } });
    fireEvent.click(screen.getByRole("button", { name: "Guardar" }));
    expect(await screen.findByText("Guardado en Meta.")).toBeInTheDocument();
    expect(sent).toMatchObject({
      missed_call_reply: true,
      missed_call_text: "Ya te llamamos, gracias por esperar.",
    });

    fireEvent.click(screen.getByRole("checkbox", { name: /Avisarle al cliente que lo llamamos/ }));
    expect(screen.getByLabelText("Mensaje")).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Guardar" }));
    await waitFor(() => expect(sent).toMatchObject({ missed_call_reply: false }));
  });

  it("keeps recording off until the installation allows it", async () => {
    renderCard();
    expect(
      await screen.findByText(/La habilita el operador en Ajustes → Instalación/),
    ).toBeInTheDocument();
    expect(screen.queryByRole("checkbox", { name: /Grabar las llamadas/ })).not.toBeInTheDocument();
  });

  it("records and transcribes with the notice the inbox chose", async () => {
    server.use(
      http.get("*/calls/settings/3", () =>
        HttpResponse.json({ ...off, enabled: true, recording_allowed: true }),
      ),
    );
    renderCard();
    fireEvent.click(await screen.findByRole("checkbox", { name: /Grabar las llamadas/ }));
    fireEvent.click(screen.getByRole("checkbox", { name: /Transcribir las llamadas/ }));
    fireEvent.change(screen.getByLabelText("Para qué se graba"), {
      target: { value: "seguimiento de tu inscripción" },
    });
    expect(
      screen.getByText(/será grabado con el siguiente fin: seguimiento de tu inscripción/),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Guardar" }));

    expect(await screen.findByText("Guardado en Meta.")).toBeInTheDocument();
    expect(sent).toEqual({
      enabled: true,
      call_icon_visible: true,
      callback_requests: false,
      business_hours: false,
      record: true,
      transcribe: true,
      purpose: "seguimiento de tu inscripción",
      announcement_language: "es",
      missed_call_reply: true,
      missed_call_text: off.missed_call_text,
      ai_mode: "off",
    });
  });

  it("says the voice AI needs the installation set up", async () => {
    server.use(http.get("*/calls/settings/3", () => HttpResponse.json({ ...off, enabled: true })));
    renderCard();
    expect(await screen.findByText(/no está configurado en esta instalación/)).toBeInTheDocument();
    expect(screen.queryByLabelText("Saludo")).not.toBeInTheDocument();
  });

  it("gives the calls to the voice AI with its greeting, what it knows and its voice", async () => {
    server.use(
      http.get("*/calls/settings/3", () =>
        HttpResponse.json({
          ...off,
          enabled: true,
          ai_available: true,
          ai_mode: "off",
          ai_greeting: "",
          ai_instructions: "",
          ai_voice: "Charon",
          ai_voices: ["Charon", "Kore"],
        }),
      ),
    );
    renderCard();
    fireEvent.change(await screen.findByLabelText("Atiende"), {
      target: { value: "no_answer" },
    });
    expect(screen.getByText(/lo que te diga es orientativo y no es vinculante/)).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Saludo"), { target: { value: "Hola, CTC Salto." } });
    fireEvent.change(screen.getByLabelText("Indicaciones solo para las llamadas (opcional)"), {
      target: { value: "Las inscripciones abren en marzo." },
    });
    fireEvent.change(screen.getByLabelText("Voz"), { target: { value: "Kore" } });
    fireEvent.click(screen.getByRole("button", { name: "Guardar" }));

    expect(await screen.findByText("Guardado en Meta.")).toBeInTheDocument();
    expect(sent).toMatchObject({
      ai_mode: "no_answer",
      ai_greeting: "Hola, CTC Salto.",
      ai_instructions: "Las inscripciones abren en marzo.",
      ai_voice: "Kore",
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
