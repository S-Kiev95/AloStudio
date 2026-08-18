import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";

import { EmailBrandingPanel } from "./email-branding-panel";

let patched: { channel?: Record<string, unknown> } | null = null;

const server = setupServer(
  http.patch("*/inboxes/:id", async ({ request }) => {
    patched = (await request.json()) as { channel?: Record<string, unknown> };
    return HttpResponse.json({ id: 4, name: "Soporte" });
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
  email: "soporte@ejemplo.edu.uy",
  signature: "",
  logo_url: "",
};

function renderPanel(over: Partial<typeof INBOX> = {}) {
  return render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <EmailBrandingPanel accountId="1" inbox={{ ...INBOX, ...over }} />
    </QueryClientProvider>,
  );
}

describe("EmailBrandingPanel", () => {
  it("sends the signature and logo under the channel key", async () => {
    renderPanel();
    fireEvent.change(screen.getByLabelText("Firma"), {
      target: { value: "Instituto Ejemplo" },
    });
    fireEvent.change(screen.getByLabelText("Logo"), {
      target: { value: "https://x.com/logo.png" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Guardar" }));

    await waitFor(() => expect(patched).not.toBeNull());
    expect(patched!.channel).toEqual({
      signature: "Instituto Ejemplo",
      logo_url: "https://x.com/logo.png",
    });
  });

  it("loads what the mailbox already signs with", () => {
    renderPanel({ signature: "Ya estaba", logo_url: "https://x.com/l.png" });
    expect(screen.getByLabelText("Firma")).toHaveValue("Ya estaba");
    expect(screen.getByLabelText("Logo")).toHaveValue("https://x.com/l.png");
  });

  it("offers to save only once something changed", () => {
    renderPanel({ signature: "Ya estaba" });
    expect(screen.getByRole("button", { name: "Guardar" })).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Firma"), {
      target: { value: "Otra cosa" },
    });
    expect(screen.getByRole("button", { name: "Guardar" })).toBeEnabled();
  });

  it("can clear a signature", async () => {
    renderPanel({ signature: "Ya estaba" });
    fireEvent.change(screen.getByLabelText("Firma"), { target: { value: "" } });
    fireEvent.click(screen.getByRole("button", { name: "Guardar" }));

    await waitFor(() => expect(patched).not.toBeNull());
    expect(patched!.channel!.signature).toBe("");
  });

  it("previews the signature as the recipient will see it", () => {
    // A signature goes out on every reply; seeing it before saving is what
    // stops a broken logo reaching customers.
    const { container } = renderPanel({
      signature: "Instituto Ejemplo",
      logo_url: "https://x/l.png",
    });
    const logo = container.querySelector("img");
    expect(logo).toHaveAttribute("src", "https://x/l.png");
    // Decorative, exactly as the sent email renders it: a blocked image
    // should leave a gap, not the word "logo".
    expect(logo).toHaveAttribute("alt", "");
    expect(screen.getAllByText("Instituto Ejemplo").length).toBeGreaterThan(0);
  });

  it("says what an unconfigured mailbox sends", () => {
    renderPanel();
    expect(screen.getByText(/la respuesta sale sola/)).toBeInTheDocument();
  });

  it("surfaces a rejected save", async () => {
    server.use(
      http.patch("*/inboxes/:id", () =>
        HttpResponse.json({ message: "nope" }, { status: 422 }),
      ),
    );
    renderPanel();
    fireEvent.change(screen.getByLabelText("Firma"), {
      target: { value: "x" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Guardar" }));
    expect(await screen.findByRole("alert")).toBeInTheDocument();
  });
});
