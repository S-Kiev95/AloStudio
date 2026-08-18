import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";

import { EmailTemplatePanel } from "./email-template-panel";

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
  template_html: "",
};

function renderPanel(over: Partial<typeof INBOX> = {}) {
  return render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <EmailTemplatePanel accountId="1" inbox={{ ...INBOX, ...over }} />
    </QueryClientProvider>,
  );
}

const field = () => screen.getByLabelText("HTML de la plantilla");
const saveBtn = () => screen.getByRole("button", { name: /Guardar plantilla/ });

describe("EmailTemplatePanel", () => {
  it("saves the authored HTML", async () => {
    renderPanel();
    fireEvent.change(field(), {
      target: { value: "<div>{{contenido}}</div>" },
    });
    fireEvent.click(saveBtn());

    await waitFor(() => expect(patched).not.toBeNull());
    expect(patched!.channel!.template_html).toBe("<div>{{contenido}}</div>");
  });

  it("loads the template the mailbox already has", () => {
    renderPanel({ template_html: "<b>{{contenido}}</b>" });
    expect(field()).toHaveValue("<b>{{contenido}}</b>");
  });

  it("refuses a template that would send an empty message", () => {
    // Named before saving: the server rejects it too, but an error after
    // the fact reads as "the save failed" rather than "this would have
    // gone out without the reply".
    renderPanel();
    fireEvent.change(field(), { target: { value: "<div>solo encabezado</div>" } });
    expect(saveBtn()).toBeDisabled();
    expect(screen.getByRole("alert")).toHaveTextContent("contenido");
  });

  it("allows an empty template, which means the built-in design", () => {
    renderPanel();
    expect(saveBtn()).toBeEnabled();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("lists the placeholders an author can use", () => {
    renderPanel();
    expect(screen.getByText("{{contenido}}")).toBeInTheDocument();
    expect(screen.getByText("{{firma}}")).toBeInTheDocument();
    expect(screen.getByText("{{logo}}")).toBeInTheDocument();
  });

  it("offers a starting point when there is nothing yet", () => {
    renderPanel();
    fireEvent.click(screen.getByRole("button", { name: /Empezar desde un ejemplo/ }));
    expect((field() as HTMLTextAreaElement).value).toContain("{{contenido}}");
  });

  it("offers a way back to the built-in design", async () => {
    renderPanel({ template_html: "<div>{{contenido}}</div>" });
    fireEvent.click(
      screen.getByRole("button", { name: /Volver al diseño por defecto/ }),
    );
    expect(field()).toHaveValue("");
    fireEvent.click(saveBtn());

    await waitFor(() => expect(patched).not.toBeNull());
    expect(patched!.channel!.template_html).toBe("");
  });

  it("surfaces a rejected save", async () => {
    server.use(
      http.patch("*/inboxes/:id", () =>
        HttpResponse.json({ message: "no sirve" }, { status: 422 }),
      ),
    );
    renderPanel();
    fireEvent.change(field(), { target: { value: "<p>{{contenido}}</p>" } });
    fireEvent.click(saveBtn());
    expect(await screen.findByRole("alert")).toHaveTextContent("no sirve");
  });
});
