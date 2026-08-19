import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { EmailMessage } from "./email-message";
import type { Message } from "@/lib/api/conversations";

const BASE: Message = {
  id: 1,
  content: "Hola,\n\nNo puedo entrar a mi cuenta.\n\nGracias.",
  message_type: 0,
  content_type: "text",
  status: "sent",
  created_at: 1_787_000_000,
  private: false,
  content_attributes: {
    email: {
      subject: "No puedo entrar",
      from: "alice@externo.com",
      from_name: "Alice Waters",
      to: ["soporte@ejemplo.com"],
      cc: ["jefe@externo.com"],
    },
  },
};

function renderMsg(over: Partial<Message> = {}, open = true) {
  return render(
    <EmailMessage message={{ ...BASE, ...over }} defaultOpen={open} />,
  );
}

describe("EmailMessage", () => {
  it("names the writer and their address", () => {
    renderMsg();
    expect(screen.getByText("Alice Waters")).toBeInTheDocument();
    expect(screen.getByText("alice@externo.com")).toBeInTheDocument();
  });

  it("shows who else got a copy", () => {
    // The reason this is not a chat bubble: a reply may be going to
    // people the agent has to know about.
    renderMsg();
    expect(screen.getByText("CC:")).toBeInTheDocument();
    expect(screen.getByText("jefe@externo.com")).toBeInTheDocument();
  });

  it("keeps the line breaks the writer typed", () => {
    const { container } = renderMsg();
    const body = container.querySelector(".whitespace-pre-wrap");
    expect(body).toHaveTextContent("No puedo entrar a mi cuenta.");
    expect(body?.className).toContain("whitespace-pre-wrap");
  });

  it("collapses to a one-line preview", () => {
    // A ten-message thread opened in full is a wall nobody reads.
    renderMsg({}, false);
    expect(screen.queryByText("CC:")).not.toBeInTheDocument();
    expect(
      screen.getByText(/No puedo entrar a mi cuenta/),
    ).toBeInTheDocument();
  });

  it("opens and closes on click", () => {
    renderMsg({}, false);
    const toggle = screen.getByRole("button");
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    fireEvent.click(toggle);
    expect(toggle).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByText("CC:")).toBeInTheDocument();
  });

  it("lists an attachment as a file, not as a picture", () => {
    // Right for a WhatsApp photo, wrong for a 3 MB scan on an email:
    // those get downloaded, not looked at in the thread.
    const { container } = renderMsg({
      attachments: [
        {
          id: 9,
          data_url: "https://x/escaneo.pdf",
          file_type: "file",
          extension: "pdf",
          fallback_title: "escaneo.pdf",
        },
      ],
    });
    expect(screen.getByText("escaneo.pdf")).toBeInTheDocument();
    expect(container.querySelector("img")).toBeNull();
    expect(screen.getByRole("link")).toHaveAttribute(
      "href",
      "https://x/escaneo.pdf",
    );
  });

  it("marks an outgoing reply as sent", () => {
    renderMsg({ message_type: 1 });
    expect(screen.getByText("enviado")).toBeInTheDocument();
  });

  it("falls back to the sender when there are no headers", () => {
    // Messages written from AloStudio have no inbound headers.
    renderMsg({
      message_type: 1,
      content_attributes: {},
      sender: { id: 3, name: "Ana Rodríguez" } as Message["sender"],
    });
    expect(screen.getByText("Ana Rodríguez")).toBeInTheDocument();
  });

  it("says so when a message has no body", () => {
    renderMsg({ content: null });
    expect(screen.getByText("(sin texto)")).toBeInTheDocument();
  });
});
