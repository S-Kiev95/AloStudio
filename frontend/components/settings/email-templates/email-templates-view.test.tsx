import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from "vitest";

import { EmailTemplatesView } from "./email-templates-view";

const TEMPLATES = "*/email_templates";

const bienvenida = {
  id: 1,
  name: "Bienvenida",
  template_html: "<p>{{contenido}}</p>",
  template_design: null,
  created_at: null,
  updated_at: null,
};
const cierre = { ...bienvenida, id: 2, name: "Cierre de ticket" };

const mailbox = {
  id: 7,
  channel_id: 3,
  name: "Soporte",
  channel_type: "Channel::Email",
};

const server = setupServer(
  http.get(TEMPLATES, () =>
    HttpResponse.json({ payload: [bienvenida, cierre] }),
  ),
  http.get("*/inboxes", () => HttpResponse.json({ payload: [mailbox] })),
);

beforeAll(() => server.listen({ onUnhandledRequest: "bypass" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

function renderView() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <EmailTemplatesView accountId="1" />
    </QueryClientProvider>,
  );
}

describe("Plantillas de correo", () => {
  it("lista las plantillas de la organización", async () => {
    renderView();
    expect(await screen.findByText("Bienvenida")).toBeInTheDocument();
    expect(screen.getByText("Cierre de ticket")).toBeInTheDocument();
  });

  it("no deja crear una sin nombre", async () => {
    renderView();
    await screen.findByText("Bienvenida");
    expect(screen.getByRole("button", { name: /Crear/ })).toBeDisabled();
  });

  it("una plantilla nueva nace con el diseño por defecto, no en blanco", async () => {
    let sent: Record<string, unknown> | null = null;
    server.use(
      http.post(TEMPLATES, async ({ request }) => {
        sent = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json({ ...bienvenida, id: 9, name: "Avisos" });
      }),
    );
    renderView();
    fireEvent.change(await screen.findByLabelText("Nueva plantilla"), {
      target: { value: "Avisos" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Crear/ }));

    await waitFor(() => expect(sent).not.toBeNull());
    expect(sent).toMatchObject({ name: "Avisos" });
    // Sendable from the start, rather than an empty box.
    expect(String(sent!.template_html)).toContain("{{contenido}}");
  });

  it("al elegir una plantilla se abre su editor", async () => {
    renderView();
    fireEvent.click(await screen.findByText("Bienvenida"));
    expect(
      await screen.findByRole("heading", { name: /Editar «Bienvenida»/ }),
    ).toBeInTheDocument();
  });

  it("avisa si el HTML se queda sin el marcador del mensaje", async () => {
    renderView();
    fireEvent.click(await screen.findByText("Bienvenida"));
    // Abre en HTML porque no tiene design detrás.
    const box = await screen.findByLabelText("HTML de la plantilla");
    fireEvent.change(box, { target: { value: "<p>hola</p>" } });
    expect(await screen.findByRole("alert")).toHaveTextContent(
      /Falta \{\{contenido\}\}/,
    );
  });

  it("no deja mandar la prueba con cambios sin guardar", async () => {
    renderView();
    fireEvent.click(await screen.findByText("Bienvenida"));
    const box = await screen.findByLabelText("HTML de la plantilla");
    fireEvent.change(box, { target: { value: "<p>{{contenido}}</p> nuevo" } });

    expect(
      await screen.findByText(/se envía la plantilla guardada/),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Enviar prueba/ })).toBeDisabled();
  });

  it("manda la prueba por la casilla y a la dirección elegidas", async () => {
    let body: Record<string, unknown> | null = null;
    server.use(
      http.post("*/email_templates/1/test_send", async ({ request }) => {
        body = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json({ message: "Enviamos la prueba a vos@x.com." });
      }),
    );
    renderView();
    fireEvent.click(await screen.findByText("Bienvenida"));
    fireEvent.change(await screen.findByLabelText("Enviar a"), {
      target: { value: "vos@x.com" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Enviar prueba/ }));

    await waitFor(() => expect(body).not.toBeNull());
    expect(body).toEqual({ inbox_id: 7, to: "vos@x.com" });
    expect(await screen.findByRole("status")).toHaveTextContent(/Enviamos/);
  });

  it("sin casillas de correo explica por qué no se puede probar", async () => {
    server.use(http.get("*/inboxes", () => HttpResponse.json({ payload: [] })));
    renderView();
    fireEvent.click(await screen.findByText("Bienvenida"));
    expect(
      await screen.findByText(/hace falta al menos una casilla/),
    ).toBeInTheDocument();
  });

  it("pide confirmación antes de eliminar", async () => {
    const confirm = vi
      .spyOn(window, "confirm")
      .mockImplementation(() => false);
    let deleted = false;
    server.use(
      http.delete("*/email_templates/1", () => {
        deleted = true;
        return HttpResponse.json({ message: "ok" });
      }),
    );
    renderView();
    fireEvent.click(await screen.findByText("Bienvenida"));
    fireEvent.click(screen.getByRole("button", { name: /Eliminar/ }));

    expect(confirm).toHaveBeenCalled();
    expect(deleted).toBe(false);
    confirm.mockRestore();
  });
});
