import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { Message } from "@/lib/api/conversations";

import { CallPermissionNote, VoiceCallMessage } from "./voice-call-message";

function call(data: Record<string, unknown>): Message {
  return {
    id: 1,
    content: "Llamada de WhatsApp",
    message_type: 0,
    content_type: "voice_call",
    status: "sent",
    created_at: 1_763_140_000,
    private: false,
    content_attributes: { data },
  };
}

describe("VoiceCallMessage", () => {
  it("shows a call that is still ringing", () => {
    render(<VoiceCallMessage message={call({ status: "ringing" })} />);
    expect(screen.getByText("Llamada entrante")).toBeInTheDocument();
    expect(screen.getByText("Todavía sin atender")).toBeInTheDocument();
  });

  it("shows who answered and for how long", () => {
    render(
      <VoiceCallMessage
        message={call({ status: "completed", duration: 125, answered_by: { id: 2, name: "Sofía" } })}
      />,
    );
    expect(screen.getByText("Llamada de WhatsApp")).toBeInTheDocument();
    expect(screen.getByText("Atendió Sofía · 2:05")).toBeInTheDocument();
  });

  it("says the recording is on its way, then shows what was said", () => {
    const { rerender } = render(
      <VoiceCallMessage
        message={call({ status: "completed", duration: 40, recording: "pending", transcription: "pending" })}
      />,
    );
    expect(screen.getByText("Preparando la grabación…")).toBeInTheDocument();

    rerender(
      <VoiceCallMessage
        message={call({
          status: "completed",
          duration: 40,
          recording: "ready",
          transcription: "ready",
          transcript: [
            { speaker: "business", text: "Hola, Instituto CTC." },
            { speaker: "customer", text: "Quería anotarme al curso." },
          ],
        })}
      />,
    );
    expect(screen.queryByText("Preparando la grabación…")).not.toBeInTheDocument();
    expect(screen.queryByText("Quería anotarme al curso.")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Ver lo que se habló" }));
    expect(screen.getByText("Quería anotarme al curso.")).toBeInTheDocument();
    expect(screen.getByText(/Cliente/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Ocultar" })).toHaveAttribute("aria-expanded", "true");
  });

  it("shows the AI summary above the folded transcript", () => {
    render(
      <VoiceCallMessage
        message={call({
          status: "completed",
          duration: 40,
          transcription: "ready",
          transcript: [{ speaker: "customer", text: "Quería anotarme al curso." }],
          summary: "- Quiere anotarse al curso de inglés.\n- Falta mandarle horarios.",
        })}
      />,
    );
    expect(screen.getByText("Resumen (IA)")).toBeInTheDocument();
    expect(screen.getByText(/Falta mandarle horarios\./)).toBeInTheDocument();
    expect(screen.queryByText("Quería anotarme al curso.")).not.toBeInTheDocument();
  });

  it("shows a call the agent made", () => {
    render(
      <VoiceCallMessage
        message={call({
          call_direction: "outbound",
          status: "completed",
          duration: 42,
          answered_by: { id: 2, name: "Sofía" },
        })}
      />,
    );
    expect(screen.getByText("Llamada saliente")).toBeInTheDocument();
    expect(screen.getByText("Llamó Sofía · 0:42")).toBeInTheDocument();
  });

  it("shows a call the customer did not pick up", () => {
    render(
      <VoiceCallMessage
        message={call({ call_direction: "outbound", status: "no-answer", answered_by: { id: 2, name: "Sofía" } })}
      />,
    );
    expect(screen.getByText("No atendió")).toBeInTheDocument();
  });

  it("shows the permission request and the customer's answer in the reader's words", () => {
    const base = call({});
    const { rerender } = render(
      <CallPermissionNote
        message={{ ...base, content: "¿Te podemos llamar?", content_attributes: { call_permission_request: true } }}
      />,
    );
    expect(screen.getByText("Pedido de permiso para llamar")).toBeInTheDocument();
    expect(screen.getByText("¿Te podemos llamar?")).toBeInTheDocument();
    rerender(
      <CallPermissionNote
        message={{
          ...base,
          content: "stored text",
          content_attributes: { call_permission: { response: "accept", permanent: false, automatic: true } },
        }}
      />,
    );
    expect(screen.getByText("Al llamar, dejó que lo llamen de vuelta por 7 días")).toBeInTheDocument();
  });

  it("shows a missed call", () => {
    render(<VoiceCallMessage message={call({ status: "no-answer" })} />);
    expect(screen.getByText("Llamada perdida")).toBeInTheDocument();
    expect(screen.getByText("Nadie atendió")).toBeInTheDocument();
  });
});
