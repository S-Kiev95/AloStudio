import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { Message } from "@/lib/api/conversations";

import { VoiceCallMessage } from "./voice-call-message";

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

  it("shows a missed call", () => {
    render(<VoiceCallMessage message={call({ status: "no-answer" })} />);
    expect(screen.getByText("Llamada perdida")).toBeInTheDocument();
    expect(screen.getByText("Nadie atendió")).toBeInTheDocument();
  });
});
