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

describe("El constructor por bloques", () => {
  const conBloques = {
    ...bienvenida,
    id: 3,
    name: "Con bloques",
    template_design: {
      kind: "blocks",
      page: {
        pageColor: "#f4f5f7",
        bodyColor: "#ffffff",
        textColor: "#1f2328",
        width: 600,
        fontFamily: "Arial, Helvetica, sans-serif",
      },
      blocks: [{ id: "a1", type: "content" }],
    },
  };

  it("abre en Bloques cuando la plantilla se hizo con bloques", async () => {
    server.use(
      http.get(TEMPLATES, () => HttpResponse.json({ payload: [conBloques] })),
    );
    renderView();
    fireEvent.click(await screen.findByText("Con bloques"));
    expect(
      await screen.findByRole("button", { name: "Bloques" }),
    ).toHaveAttribute("aria-pressed", "true");
  });

  it("abre en HTML cuando el markup se escribió a mano", async () => {
    // Abrir un editor mostraría controles que no lo describen, y guardar
    // lo reemplazaría en silencio.
    renderView();
    fireEvent.click(await screen.findByText("Bienvenida"));
    expect(await screen.findByRole("button", { name: "HTML" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
  });

  it("avisa si falta el bloque del mensaje y lo puede agregar", async () => {
    server.use(
      http.get(TEMPLATES, () =>
        HttpResponse.json({
          payload: [
            {
              ...conBloques,
              template_design: {
                ...conBloques.template_design,
                blocks: [{ id: "d1", type: "divider", color: "#eee" }],
              },
            },
          ],
        }),
      ),
    );
    renderView();
    fireEvent.click(await screen.findByText("Con bloques"));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      /Falta el bloque «El mensaje del agente»/,
    );
  });

  it("guarda el documento de bloques junto al HTML que genera", async () => {
    let sent: Record<string, unknown> | null = null;
    server.use(
      http.get(TEMPLATES, () => HttpResponse.json({ payload: [conBloques] })),
      http.patch("*/email_templates/3", async ({ request }) => {
        sent = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json(conBloques);
      }),
    );
    renderView();
    fireEvent.click(await screen.findByText("Con bloques"));
    fireEvent.click(await screen.findByRole("button", { name: "Guardar" }));

    await waitFor(() => expect(sent).not.toBeNull());
    // El HTML es lo que se manda; el documento es para poder reabrirlo.
    expect(String(sent!.template_html)).toContain("{{contenido}}");
    expect(String(sent!.template_html)).toContain("<table");
    expect((sent!.template_design as { kind?: string }).kind).toBe("blocks");
  });

  it("agrega un bloque y abre sus ajustes", async () => {
    server.use(
      http.get(TEMPLATES, () => HttpResponse.json({ payload: [conBloques] })),
    );
    renderView();
    fireEvent.click(await screen.findByText("Con bloques"));
    fireEvent.click(await screen.findByRole("button", { name: /Texto/ }));
    // Queda seleccionado, así que aparecen sus controles — «Negrita» sólo
    // existe en los de texto.
    expect(await screen.findByLabelText(/Negrita/)).toBeInTheDocument();
  });

  it("el bloque nuevo se puede mover y eliminar", async () => {
    server.use(
      http.get(TEMPLATES, () => HttpResponse.json({ payload: [conBloques] })),
    );
    renderView();
    fireEvent.click(await screen.findByText("Con bloques"));
    fireEvent.click(await screen.findByRole("button", { name: /Imagen/ }));

    expect(
      await screen.findByRole("button", { name: "Subir Imagen" }),
    ).toBeEnabled();
    expect(screen.getByRole("button", { name: "Eliminar Imagen" })).toBeEnabled();
  });

  it("permite agregar, editar, mover, deshacer/rehacer y pasar a HTML y volver", async () => {
    server.use(
      http.get(TEMPLATES, () => HttpResponse.json({ payload: [conBloques] })),
    );
    renderView();
    fireEvent.click(await screen.findByText("Con bloques"));

    // Agregar bloque de Texto y editar su contenido
    fireEvent.click(await screen.findByRole("button", { name: "Texto" }));
    const textInput = await screen.findByLabelText("Texto");
    fireEvent.change(textInput, { target: { value: "Hola desde el lienzo" } });

    // Mover hacia arriba
    fireEvent.click(screen.getByRole("button", { name: "Subir Texto" }));

    // Deshacer y rehacer
    const undoBtn = screen.getByRole("button", { name: "Deshacer" });
    const redoBtn = screen.getByRole("button", { name: "Rehacer" });
    expect(undoBtn).toBeEnabled();
    fireEvent.click(undoBtn);
    expect(redoBtn).toBeEnabled();
    fireEvent.click(redoBtn);

    // Pasar a HTML conserva lo editado y muestra la vista previa en iframe sandbox
    fireEvent.click(screen.getByRole("button", { name: "HTML" }));
    const htmlBox = (await screen.findByLabelText(
      "HTML de la plantilla",
    )) as HTMLTextAreaElement;
    expect(htmlBox.value).toContain("Hola desde el lienzo");
    expect(htmlBox.value).toContain("{{contenido}}");

    // Volver a Bloques mantiene el documento de bloques
    fireEvent.click(screen.getByRole("button", { name: "Bloques" }));
    expect(await screen.findByRole("list", { name: "Bloques del lienzo" })).toBeInTheDocument();
  });

  it("renderiza la vista previa siempre dentro de un iframe sandbox con escritorio/celular y claro/oscuro", async () => {
    server.use(
      http.get(TEMPLATES, () => HttpResponse.json({ payload: [conBloques] })),
    );
    renderView();
    fireEvent.click(await screen.findByText("Con bloques"));

    const iframe = (await screen.findByTitle("Vista previa")) as HTMLIFrameElement;
    expect(iframe.tagName).toBe("IFRAME");
    expect(iframe.getAttribute("sandbox")).toBe("");
    expect(iframe.getAttribute("srcdoc")).toContain("gracias por escribirnos");

    // Cambiar a celular ajusta el ancho a 375px
    fireEvent.click(screen.getByRole("button", { name: "Celular" }));
    expect(iframe.style.width).toBe("375px");

    // Cambiar a modo oscuro actualiza el srcdoc
    fireEvent.click(screen.getByRole("button", { name: "Oscuro" }));
    expect(iframe.getAttribute("srcdoc")).toContain("#111827");
  });
});

describe("Plantillas personales, firmas y diseño con IA", () => {
  it("gestiona plantillas personales y permite marcar una por defecto", async () => {
    let patchBody: Record<string, unknown> | null = null;
    const personal = {
      ...bienvenida,
      id: 20,
      name: "Mi plantilla",
      scope: "personal",
      is_default: false,
    };
    server.use(
      http.get("*/email_templates/personal", () =>
        HttpResponse.json({ payload: [personal] }),
      ),
      http.patch("*/email_templates/personal/20", async ({ request }) => {
        patchBody = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json({ ...personal, is_default: true });
      }),
    );

    renderView();
    fireEvent.click(await screen.findByRole("tab", { name: "Mis plantillas" }));
    fireEvent.click(await screen.findByText("Mi plantilla"));

    fireEvent.click(
      await screen.findByLabelText("Usar como mi plantilla por defecto"),
    );
    fireEvent.click(screen.getByRole("button", { name: "Guardar" }));

    await waitFor(() => expect(patchBody).not.toBeNull());
    expect(patchBody).toMatchObject({ is_default: true });
  });

  it("guarda la firma personal en el lienzo de firmas", async () => {
    let savedSig: Record<string, unknown> | null = null;
    server.use(
      http.get("*/email_signatures/personal", () =>
        HttpResponse.json({
          id: null,
          scope: "personal",
          signature_html: "",
          signature_text: "",
          signature_design: null,
          fallback_text: "",
          created_at: null,
          updated_at: null,
        }),
      ),
      http.get("*/email_signatures/organization", () =>
        HttpResponse.json({
          id: null,
          scope: "organization",
          signature_html: "",
          signature_text: "",
          signature_design: null,
          fallback_text: "",
          created_at: null,
          updated_at: null,
        }),
      ),
      http.put("*/email_signatures/personal", async ({ request }) => {
        savedSig = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json({
          id: 5,
          scope: "personal",
          signature_html: String(savedSig.signature_html ?? ""),
          signature_text: String(savedSig.signature_text ?? ""),
          signature_design: savedSig.signature_design ?? null,
          fallback_text: "",
          created_at: null,
          updated_at: null,
        });
      }),
    );

    renderView();
    fireEvent.click(await screen.findByRole("tab", { name: "Firmas" }));
    expect(await screen.findByText("Mi firma personal")).toBeInTheDocument();

    const saveButtons = screen.getAllByRole("button", { name: "Guardar" });
    fireEvent.click(saveButtons[0]);

    await waitFor(() => expect(savedSig).not.toBeNull());
    expect(String(savedSig!.signature_html)).toContain("{{nombre}}");
    expect(String(savedSig!.signature_html)).not.toContain("{{contenido}}");
  });

  it("diálogo Diseñar con IA abre el HTML en el lienzo sin guardar solo y maneja ai_down", async () => {
    let savedToServer = false;
    let generateBody: Record<string, unknown> | null = null;
    server.use(
      http.patch("*/email_templates/1", () => {
        savedToServer = true;
        return HttpResponse.json(bienvenida);
      }),
      http.post("*/email_templates/generate", async ({ request }) => {
        generateBody = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json({
          html: '<table style="width:600px"><tr><td>Membrete IA {{contenido}}</td></tr></table>',
          notes: "Diseñé un membrete azul limpio.",
          mode: "free",
          seen: null,
        });
      }),
    );

    renderView();
    fireEvent.click(await screen.findByText("Bienvenida"));
    fireEvent.click(
      await screen.findByRole("button", { name: /Diseñar con IA/ }),
    );

    const promptInput = await screen.findByLabelText("¿Qué querés diseñar?");
    fireEvent.change(promptInput, {
      target: { value: "Membrete azul con logo a la izquierda" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Generar diseño/ }));

    await waitFor(() => expect(generateBody).not.toBeNull());
    expect(generateBody).toMatchObject({
      prompt: "Membrete azul con logo a la izquierda",
      kind: "template",
    });

    const htmlBox = (await screen.findByLabelText(
      "HTML de la plantilla",
    )) as HTMLTextAreaElement;
    expect(htmlBox.value).toContain("Membrete IA {{contenido}}");
    expect(
      await screen.findByText(/Diseñé un membrete azul limpio/),
    ).toBeInTheDocument();
    // Nunca se guarda solo.
    expect(savedToServer).toBe(false);

    // Ahora simulamos caída de IA (503 ai_down)
    server.use(
      http.post("*/email_templates/generate", () =>
        HttpResponse.json(
          {
            code: "email_ai.ai_down",
            message: "Servicios de AI temporalmente fuera, intenta mañana",
          },
          { status: 503 },
        ),
      ),
    );
    fireEvent.click(screen.getByRole("button", { name: /Diseñar con IA/ }));
    fireEvent.change(await screen.findByLabelText("¿Qué querés diseñar?"), {
      target: { value: "Otro intento" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Generar diseño/ }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      /Servicios de AI temporalmente fuera, intenta mañana/,
    );
  });
});
