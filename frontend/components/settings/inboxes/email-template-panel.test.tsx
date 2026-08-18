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

const INBOX: {
  id: number;
  channel_id: number;
  name: string;
  channel_type: string;
  template_html: string;
  template_design?: Record<string, unknown> | null;
} = {
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

const saveBtn = () => screen.getByRole("button", { name: /Guardar plantilla/ });

/** The panel opens on the designer, so a test about the HTML editor has
 *  to ask for it first — same as the author would. */
function codeMode() {
  fireEvent.click(screen.getByRole("button", { name: "HTML" }));
  return screen.getByLabelText("HTML de la plantilla");
}
const field = () => screen.getByLabelText("HTML de la plantilla");

describe("EmailTemplatePanel", () => {
  it("saves the authored HTML", async () => {
    renderPanel();
    codeMode();
    fireEvent.change(field(), {
      target: { value: "<div>{{contenido}}</div>" },
    });
    fireEvent.click(saveBtn());

    await waitFor(() => expect(patched).not.toBeNull());
    expect(patched!.channel!.template_html).toBe("<div>{{contenido}}</div>");
  });

  it("loads the template the mailbox already has", () => {
    // Hand-written HTML has no design behind it, so the panel opens on
    // the code tab rather than showing controls that do not describe it.
    renderPanel({ template_html: "<b>{{contenido}}</b>" });
    expect(field()).toHaveValue("<b>{{contenido}}</b>");
  });

  it("refuses a template that would send an empty message", () => {
    // Named before saving: the server rejects it too, but an error after
    // the fact reads as "the save failed" rather than "this would have
    // gone out without the reply".
    renderPanel();
    codeMode();
    fireEvent.change(field(), { target: { value: "<div>solo encabezado</div>" } });
    expect(saveBtn()).toBeDisabled();
    expect(screen.getByRole("alert")).toHaveTextContent("contenido");
  });

  it("allows an empty template, which means the built-in design", () => {
    renderPanel();
    codeMode();
    expect(saveBtn()).toBeEnabled();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("lists the placeholders an author can use", () => {
    renderPanel();
    codeMode();
    expect(screen.getByText("{{contenido}}")).toBeInTheDocument();
    expect(screen.getByText("{{firma}}")).toBeInTheDocument();
    expect(screen.getByText("{{logo}}")).toBeInTheDocument();
  });

  it("offers a starting point once the box is empty", () => {
    // Arriving from the designer the box already holds what was built,
    // so the example is only offered when there is genuinely nothing.
    renderPanel();
    codeMode();
    fireEvent.change(field(), { target: { value: "" } });
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
    codeMode();
    fireEvent.change(field(), { target: { value: "<p>{{contenido}}</p>" } });
    fireEvent.click(saveBtn());
    expect(await screen.findByRole("alert")).toHaveTextContent("no sirve");
  });
});

describe("EmailTemplatePanel, the visual designer", () => {
  it("opens on the designer for a mailbox with no template", () => {
    // Which is the point: someone who does not write HTML should never
    // have to see a box full of it.
    renderPanel();
    expect(screen.getByLabelText(/Título del encabezado/)).toBeInTheDocument();
  });

  it("opens on the code tab when the HTML was hand-written", () => {
    // There is no design behind it, so the controls would not describe
    // it and saving would replace it.
    renderPanel({ template_html: "<div>{{contenido}}</div>" });
    expect(screen.getByLabelText("HTML de la plantilla")).toBeInTheDocument();
  });

  it("opens on the designer when a design was stored", () => {
    renderPanel({
      template_html: "<div>{{contenido}}</div>",
      template_design: { headerTitle: "Instituto" },
    });
    expect(screen.getByLabelText(/Título del encabezado/)).toHaveValue(
      "Instituto",
    );
  });

  it("saves the generated HTML together with its settings", async () => {
    renderPanel();
    fireEvent.change(screen.getByLabelText(/Título del encabezado/), {
      target: { value: "Instituto Ejemplo" },
    });
    fireEvent.click(saveBtn());

    await waitFor(() => expect(patched).not.toBeNull());
    const ch = patched!.channel!;
    expect(ch.template_html).toContain("{{contenido}}");
    expect(ch.template_html).toContain("Instituto Ejemplo");
    // The settings go too, so reopening shows the controls that built it.
    expect((ch.template_design as Record<string, unknown>).headerTitle).toBe(
      "Instituto Ejemplo",
    );
  });

  it("sends no design when the HTML was edited by hand", async () => {
    // Its absence is what tells the server to forget the stored one.
    renderPanel();
    codeMode();
    fireEvent.change(field(), { target: { value: "<p>{{contenido}}</p>" } });
    fireEvent.click(saveBtn());

    await waitFor(() => expect(patched).not.toBeNull());
    expect(patched!.channel!.template_design).toBeUndefined();
  });

  it("carries the design across when switching to HTML", () => {
    // Starting from a blank box would throw away what they just built.
    renderPanel();
    fireEvent.change(screen.getByLabelText(/Título del encabezado/), {
      target: { value: "Instituto" },
    });
    expect((codeMode() as HTMLTextAreaElement).value).toContain("Instituto");
  });

  it("says when the logo it would show has not been uploaded", () => {
    renderPanel();
    expect(screen.getByText(/no cargaste un logo/)).toBeInTheDocument();
  });
});
