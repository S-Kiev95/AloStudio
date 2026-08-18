import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";

import { EmailTransportPanel } from "./email-transport-panel";

let patched: { channel?: Record<string, unknown> } | null = null;

const server = setupServer(
  http.patch("*/inboxes/:id", async ({ request }) => {
    patched = (await request.json()) as { channel?: Record<string, unknown> };
    return HttpResponse.json({ id: 4 });
  }),
);

beforeAll(() => server.listen({ onUnhandledRequest: "bypass" }));
afterEach(() => {
  patched = null;
  server.resetHandlers();
});
afterAll(() => server.close());

const INBOX = {
  id: 4,
  channel_id: 2,
  name: "Soporte",
  channel_type: "Channel::Email",
  imap_enabled: false,
  imap_address: "",
  imap_port: 0,
  imap_login: "",
  imap_password_set: false,
  smtp_enabled: false,
  smtp_address: "",
  smtp_port: 0,
  smtp_login: "",
  smtp_password_set: false,
};

function renderPanel(over: Partial<typeof INBOX> = {}) {
  return render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <EmailTransportPanel accountId="1" inbox={{ ...INBOX, ...over }} />
    </QueryClientProvider>,
  );
}

const channel = () => patched!.channel!;

describe("EmailTransportPanel", () => {
  it("sends the IMAP settings that make mail arrive", async () => {
    renderPanel();
    const [imapEnabled] = screen.getAllByRole("checkbox");
    fireEvent.click(imapEnabled);
    fireEvent.change(screen.getByLabelText("Servidor", { selector: "#imap-address" }), {
      target: { value: "imap.gmail.com" },
    });
    fireEvent.change(screen.getByLabelText("Usuario", { selector: "#imap-login" }), {
      target: { value: "soporte@x.com" },
    });
    fireEvent.change(
      screen.getByLabelText("Contraseña", { selector: "#imap-password" }),
      { target: { value: "clave" } },
    );
    fireEvent.click(screen.getByRole("button", { name: "Guardar" }));

    await waitFor(() => expect(patched).not.toBeNull());
    expect(channel().imap_enabled).toBe(true);
    expect(channel().imap_address).toBe("imap.gmail.com");
    expect(channel().imap_password).toBe("clave");
  });

  it("sends the port as a number, not the text typed", async () => {
    renderPanel();
    fireEvent.change(screen.getByLabelText("Puerto", { selector: "#imap-port" }), {
      target: { value: "143" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Guardar" }));

    await waitFor(() => expect(patched).not.toBeNull());
    expect(channel().imap_port).toBe(143);
  });

  it("leaves the password blank so a save does not erase the stored one", async () => {
    // The password is never sent to the browser, so there is nothing to
    // re-submit; blank is what tells the server to keep it.
    renderPanel({ imap_password_set: true, imap_address: "imap.x.com" });
    fireEvent.change(screen.getByLabelText("Servidor", { selector: "#imap-address" }), {
      target: { value: "imap.otro.com" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Guardar" }));

    await waitFor(() => expect(patched).not.toBeNull());
    expect(channel().imap_password).toBe("");
    expect(channel().imap_address).toBe("imap.otro.com");
  });

  it("says a password is already stored instead of showing an empty box", () => {
    renderPanel({ smtp_password_set: true });
    expect(
      screen.getByLabelText("Contraseña", { selector: "#smtp-password" }),
    ).toHaveAttribute("placeholder", "Ya hay una guardada");
  });

  it("switches the two sides independently", async () => {
    // Receive-only and send-only are both real configurations.
    renderPanel();
    const boxes = screen.getAllByRole("checkbox");
    fireEvent.click(boxes[1]);
    fireEvent.click(screen.getByRole("button", { name: "Guardar" }));

    await waitFor(() => expect(patched).not.toBeNull());
    expect(channel().smtp_enabled).toBe(true);
    expect(channel().imap_enabled).toBe(false);
  });

  it("clears the typed password after saving", async () => {
    renderPanel();
    const field = screen.getByLabelText("Contraseña", { selector: "#imap-password" });
    fireEvent.change(field, { target: { value: "clave" } });
    fireEvent.click(screen.getByRole("button", { name: "Guardar" }));

    await waitFor(() => expect(patched).not.toBeNull());
    await waitFor(() => expect(field).toHaveValue(""));
  });

  it("surfaces a rejected save", async () => {
    server.use(
      http.patch("*/inboxes/:id", () =>
        HttpResponse.json({ message: "faltan datos" }, { status: 422 }),
      ),
    );
    renderPanel();
    fireEvent.click(screen.getByRole("button", { name: "Guardar" }));
    expect(await screen.findByRole("alert")).toBeInTheDocument();
  });
});
