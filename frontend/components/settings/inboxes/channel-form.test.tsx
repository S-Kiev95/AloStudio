import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from "vitest";

import { ChannelForm } from "./channel-form";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), refresh: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
}));

let posted: { channel?: Record<string, unknown> } | null = null;

const server = setupServer(
  http.get("*/api/v1/installation/public", () =>
    HttpResponse.json({ signup_enabled: false, multitenant: false }),
  ),
  http.get("*/api/v1/accounts/1/whatsapp/embedded_signup", () =>
    HttpResponse.json({
      ready: false,
      missing: ["META_APP_ID"],
      app_id: "",
      config_id: "",
      graph_api_version: "v23.0",
    }),
  ),
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

function renderForm(channel = "email") {
  return render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <ChannelForm accountId="1" channel={channel} />
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

describe("ChannelForm en multitenant", () => {
  it("oculta los formularios manuales de WhatsApp, Facebook e Instagram y deja solo los botones de Meta", async () => {
    server.use(
      http.get("*/api/v1/installation/public", () =>
        HttpResponse.json({ signup_enabled: true, multitenant: true }),
      ),
      http.get("*/api/v1/accounts/1/whatsapp/embedded_signup", () =>
        HttpResponse.json({
          ready: true,
          missing: [],
          app_id: "111",
          config_id: "cfg-1",
          graph_api_version: "v23.0",
        }),
      ),
    );

    const wa = renderForm("whatsapp");
    expect(
      await screen.findByRole("button", { name: "Conectar WhatsApp" }),
    ).toBeInTheDocument();
    await waitFor(() =>
      expect(
        screen.queryByRole("button", { name: /Crear canal/ }),
      ).toBeNull(),
    );
    wa.unmount();

    const fb = renderForm("facebook");
    expect(
      await screen.findByRole("button", { name: "Conectar con Facebook" }),
    ).toBeInTheDocument();
    await waitFor(() =>
      expect(
        screen.queryByRole("button", { name: /Crear canal/ }),
      ).toBeNull(),
    );
    fb.unmount();

    const ig = renderForm("instagram");
    expect(
      await screen.findByRole("button", { name: "Facebook Login" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Instagram Login" }),
    ).toBeInTheDocument();
    await waitFor(() =>
      expect(
        screen.queryByRole("button", { name: /Crear canal/ }),
      ).toBeNull(),
    );
    ig.unmount();
  });
});
