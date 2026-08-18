import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from "vitest";

import { ChannelForm } from "./channel-form";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), refresh: vi.fn() }),
}));

let posted: { channel?: Record<string, unknown> } | null = null;

const server = setupServer(
  http.post("*/inboxes", async ({ request }) => {
    posted = (await request.json()) as { channel?: Record<string, unknown> };
    return HttpResponse.json({ id: 1, name: "Soporte", channel_type: "Channel::Email" });
  }),
);

beforeAll(() => server.listen({ onUnhandledRequest: "bypass" }));
afterEach(() => {
  posted = null;
  server.resetHandlers();
});
afterAll(() => server.close());

function renderForm() {
  return render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <ChannelForm accountId="1" channel="email" />
    </QueryClientProvider>,
  );
}

describe("ChannelForm, creating an email inbox", () => {
  it("draws a checkbox for a boolean field, not a text box", () => {
    // Rendered as text, "Recibir correos (IMAP)" reads like something to
    // type a value into — which is exactly how it was reported.
    renderForm();
    expect(
      screen.getAllByRole("checkbox").length,
    ).toBeGreaterThanOrEqual(2);
  });

  it("sends a real boolean, not the string", async () => {
    // Any non-empty string is truthy server-side, so "false" would switch
    // the side on — the opposite of what the box says.
    renderForm();
    fireEvent.change(screen.getByLabelText(/Nombre de la bandeja/), {
      target: { value: "Soporte" },
    });
    fireEvent.change(screen.getByLabelText(/Dirección de email/), {
      target: { value: "soporte@x.com" },
    });
    fireEvent.click(screen.getAllByRole("checkbox")[0]);
    fireEvent.click(screen.getByRole("button", { name: /Crear canal/ }));

    await waitFor(() => expect(posted).not.toBeNull());
    expect(posted!.channel!.imap_enabled).toBe(true);
  });

  it("omits a box left unticked rather than sending false as text", async () => {
    renderForm();
    fireEvent.change(screen.getByLabelText(/Nombre de la bandeja/), {
      target: { value: "Soporte" },
    });
    fireEvent.change(screen.getByLabelText(/Dirección de email/), {
      target: { value: "soporte@x.com" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Crear canal/ }));

    await waitFor(() => expect(posted).not.toBeNull());
    expect(posted!.channel!.imap_enabled).toBeUndefined();
    expect(posted!.channel!.smtp_enabled).toBeUndefined();
  });

  it("still sends the text fields", async () => {
    renderForm();
    fireEvent.change(screen.getByLabelText(/Nombre de la bandeja/), {
      target: { value: "Soporte" },
    });
    fireEvent.change(screen.getByLabelText(/Dirección de email/), {
      target: { value: "soporte@x.com" },
    });
    fireEvent.change(screen.getByLabelText(/Servidor IMAP/), {
      target: { value: "imap.gmail.com" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Crear canal/ }));

    await waitFor(() => expect(posted).not.toBeNull());
    expect(posted!.channel!.imap_address).toBe("imap.gmail.com");
  });
});
