import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import {
  afterAll,
  afterEach,
  beforeAll,
  beforeEach,
  describe,
  expect,
  it,
  vi,
} from "vitest";

import { ROLE_ADMINISTRATOR, ROLE_AGENT } from "@/lib/api/account";
import type { WhatsappTemplateFull } from "@/lib/api/whatsapp-templates";

import { WhatsappTemplatesPanel } from "./whatsapp-templates-panel";

let currentRole = ROLE_ADMINISTRATOR;
let templatesStore: WhatsappTemplateFull[] = [];

const INITIAL_TEMPLATES: WhatsappTemplateFull[] = [
  {
    id: "111",
    name: "recordatorio_turno",
    language: "es",
    status: "APPROVED",
    category: "UTILITY",
    body_text: "Hola {{1}}, tu turno es el {{2}}.",
    variables: [1, 2],
    components: [
      {
        type: "BODY",
        text: "Hola {{1}}, tu turno es el {{2}}.",
        example: { body_text: [["Ana", "martes 10:00"]] },
      },
    ],
  },
  {
    id: "222",
    name: "promo_verano",
    language: "es_AR",
    status: "REJECTED",
    category: "MARKETING",
    body_text: "¡Oferta de verano!",
    variables: [],
    rejected_reason: "INVALID_FORMAT",
    components: [{ type: "BODY", text: "¡Oferta de verano!" }],
  },
  {
    id: "333",
    name: "codigo_acceso",
    language: "es",
    status: "PENDING",
    category: "AUTHENTICATION",
    body_text: "Tu código es {{1}}.",
    variables: [1],
    components: [{ type: "BODY", text: "Tu código es {{1}}." }],
  },
  {
    id: "444",
    name: "campana_pausada",
    language: "pt_BR",
    status: "PAUSED",
    category: "MARKETING",
    body_text: "Novidades da semana",
    variables: [],
    components: [{ type: "BODY", text: "Novidades da semana" }],
  },
  {
    id: "555",
    name: "vieja_desactivada",
    language: "en_US",
    status: "DISABLED",
    category: "UTILITY",
    body_text: "Old template",
    variables: [],
    rejected_reason: "INCORRECT_CATEGORY",
    components: [{ type: "BODY", text: "Old template" }],
  },
];

const server = setupServer(
  http.get("*/api/v1/profile", () =>
    HttpResponse.json({
      data: {
        id: 1,
        name: "Admin",
        email: "admin@alostudio.test",
        accounts: [{ id: 1, name: "AloStudio", role: currentRole }],
      },
    }),
  ),
  http.get(
    "*/api/v1/accounts/:accountId/inboxes/:inboxId/whatsapp/templates",
    ({ request }) => {
      const url = new URL(request.url);
      if (url.searchParams.get("status") === "all") {
        return HttpResponse.json({
          templates: templatesStore,
          last_updated: 1763050000,
        });
      }
      return HttpResponse.json({
        templates: templatesStore.filter((t) => t.status === "APPROVED"),
        last_updated: 1763050000,
      });
    },
  ),
);

beforeAll(() => server.listen({ onUnhandledRequest: "bypass" }));
beforeEach(() => {
  currentRole = ROLE_ADMINISTRATOR;
  templatesStore = structuredClone(INITIAL_TEMPLATES);
});
afterEach(() => {
  vi.restoreAllMocks();
  server.resetHandlers();
});
afterAll(() => server.close());

function renderPanel() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={qc}>
      <WhatsappTemplatesPanel accountId="1" inboxId={7} />
    </QueryClientProvider>,
  );
}

describe("WhatsappTemplatesPanel", () => {
  it("muestra la lista con estados, categorías, motivos de rechazo traducidos y oculta acciones de escritura a agentes", async () => {
    const { unmount } = renderPanel();

    expect(await screen.findByText("recordatorio_turno")).toBeInTheDocument();
    expect(screen.getByText("Aprobada")).toBeInTheDocument();
    expect(screen.getByText("Rechazada")).toBeInTheDocument();
    expect(screen.getByText("Pendiente")).toBeInTheDocument();
    expect(screen.getByText("Pausada")).toBeInTheDocument();
    expect(screen.getByText("Desactivada")).toBeInTheDocument();

    // Motivos traducidos (INVALID_FORMAT -> Formato inválido, INCORRECT_CATEGORY -> Categoría incorrecta)
    expect(screen.getByText(/Formato inválido/)).toBeInTheDocument();
    expect(screen.getByText(/Categoría incorrecta/)).toBeInTheDocument();

    // Admin ve botones de crear, editar y borrar
    expect(
      await screen.findByRole("button", { name: "Nueva plantilla" }),
    ).toBeInTheDocument();
    expect(
      screen.getAllByRole("button", { name: "Editar" }).length,
    ).toBeGreaterThan(0);
    expect(
      screen.getAllByRole("button", { name: "Borrar" }).length,
    ).toBeGreaterThan(0);

    unmount();

    // Un agente solo ve la lista
    currentRole = ROLE_AGENT;
    renderPanel();
    expect(await screen.findByText("recordatorio_turno")).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Nueva plantilla" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Editar" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Borrar" }),
    ).not.toBeInTheDocument();
  });

  it("valida el nombre en vivo, exige ejemplos por variable, muestra vista previa y arma components al crear", async () => {
    let sentPayload: Record<string, unknown> | null = null;
    server.use(
      http.post(
        "*/api/v1/accounts/:accountId/inboxes/:inboxId/whatsapp/templates",
        async ({ request }) => {
          sentPayload = (await request.json()) as Record<string, unknown>;
          const created: WhatsappTemplateFull = {
            id: "999",
            name: String(sentPayload.name),
            language: String(sentPayload.language),
            category: String(sentPayload.category),
            status: "PENDING",
            body_text: "Hola {{1}}, te esperamos el {{2}}.",
            variables: [1, 2],
            components:
              sentPayload.components as WhatsappTemplateFull["components"],
          };
          templatesStore = [...templatesStore, created];
          return HttpResponse.json({
            result: { id: "999", status: "PENDING" },
            templates: templatesStore,
          });
        },
      ),
    );

    renderPanel();
    fireEvent.click(
      await screen.findByRole("button", { name: "Nueva plantilla" }),
    );

    const nameInput = screen.getByLabelText(/Nombre/);
    fireEvent.change(nameInput, { target: { value: "Con Espacios!" } });

    // Validación en vivo del nombre
    expect(
      screen.getByText(
        /Usá solo minúsculas, números y guiones bajos \(_\), sin espacios/,
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Guardar plantilla" }),
    ).toBeDisabled();

    fireEvent.change(nameInput, { target: { value: "confirmacion_curso" } });
    expect(
      screen.getByRole("button", { name: "Guardar plantilla" }),
    ).not.toBeDisabled();

    // Encabezado con variable
    fireEvent.change(screen.getByLabelText(/Encabezado/), {
      target: { value: "Turno {{1}}" },
    });
    fireEvent.change(screen.getByLabelText(/Ejemplo de encabezado/), {
      target: { value: "martes" },
    });

    // Cuerpo + botón "Agregar variable"
    const bodyInput = screen.getByLabelText(/Cuerpo/);
    fireEvent.change(bodyInput, { target: { value: "Hola" } });
    fireEvent.click(screen.getByRole("button", { name: "Agregar variable" }));
    expect(bodyInput).toHaveValue("Hola {{1}}");

    fireEvent.change(bodyInput, {
      target: { value: "Hola {{1}}, te esperamos el" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Agregar variable" }));
    expect(bodyInput).toHaveValue("Hola {{1}}, te esperamos el {{2}}");

    // Intentar guardar sin completar los ejemplos de variables falla antes de llamar a Meta
    fireEvent.click(screen.getByRole("button", { name: "Guardar plantilla" }));
    expect(
      await screen.findByText(
        /Completá un ejemplo para cada variable del cuerpo/,
      ),
    ).toBeInTheDocument();
    expect(sentPayload).toBeNull();

    // Completar ejemplos y verificar vista previa en vivo
    fireEvent.change(screen.getByLabelText("Ejemplo {{1}}"), {
      target: { value: "Ana" },
    });
    fireEvent.change(screen.getByLabelText("Ejemplo {{2}}"), {
      target: { value: "martes 10:00" },
    });

    // Pie y botones (respuesta rápida, URL con variable y teléfono)
    fireEvent.change(screen.getByLabelText(/Pie/), {
      target: { value: "CTC Salto" },
    });

    fireEvent.click(screen.getByRole("button", { name: "+ Respuesta rápida" }));
    fireEvent.click(screen.getByRole("button", { name: "+ Botón URL" }));
    fireEvent.click(screen.getByRole("button", { name: "+ Botón teléfono" }));

    const btnTexts = screen.getAllByLabelText(/Texto del botón/);
    fireEvent.change(btnTexts[0], { target: { value: "Confirmo" } });
    fireEvent.change(btnTexts[1], { target: { value: "Ver curso" } });
    fireEvent.change(btnTexts[2], { target: { value: "Llamar" } });

    fireEvent.change(screen.getByLabelText(/URL/), {
      target: { value: "https://ctc.edu.uy/{{1}}" },
    });
    fireEvent.change(screen.getByLabelText(/Ejemplo de URL/), {
      target: { value: "excel" },
    });
    fireEvent.change(screen.getByLabelText(/Teléfono/), {
      target: { value: "+59847300000" },
    });

    // Vista previa con ejemplos reemplazando variables
    const preview = screen.getByTestId("whatsapp-template-preview");
    expect(within(preview).getByText("Turno martes")).toBeInTheDocument();
    expect(
      within(preview).getByText("Hola Ana, te esperamos el martes 10:00"),
    ).toBeInTheDocument();
    expect(within(preview).getByText("CTC Salto")).toBeInTheDocument();
    expect(within(preview).getByText("Confirmo")).toBeInTheDocument();

    // Guardar
    fireEvent.click(screen.getByRole("button", { name: "Guardar plantilla" }));

    await waitFor(() => expect(sentPayload).not.toBeNull());
    expect(sentPayload).toEqual({
      name: "confirmacion_curso",
      category: "UTILITY",
      language: "es",
      components: [
        {
          type: "HEADER",
          format: "TEXT",
          text: "Turno {{1}}",
          example: { header_text: ["martes"] },
        },
        {
          type: "BODY",
          text: "Hola {{1}}, te esperamos el {{2}}",
          example: { body_text: [["Ana", "martes 10:00"]] },
        },
        {
          type: "FOOTER",
          text: "CTC Salto",
        },
        {
          type: "BUTTONS",
          buttons: [
            { type: "QUICK_REPLY", text: "Confirmo" },
            {
              type: "URL",
              text: "Ver curso",
              url: "https://ctc.edu.uy/{{1}}",
              example: ["excel"],
            },
            {
              type: "PHONE_NUMBER",
              text: "Llamar",
              phone_number: "+59847300000",
            },
          ],
        },
      ],
    });

    // Cierra el editor, muestra el aviso de revisión de Meta y refresca la lista
    expect(
      await screen.findByText(
        "Meta la revisa; puede tardar de minutos a horas.",
      ),
    ).toBeInTheDocument();
    expect(await screen.findByText("confirmacion_curso")).toBeInTheDocument();
  });

  it("muestra el message del 422 cuando Meta rechaza el guardado", async () => {
    server.use(
      http.post(
        "*/api/v1/accounts/:accountId/inboxes/:inboxId/whatsapp/templates",
        () =>
          HttpResponse.json(
            { message: "El nombre ya existe en ese idioma." },
            { status: 422 },
          ),
      ),
    );

    renderPanel();
    fireEvent.click(
      await screen.findByRole("button", { name: "Nueva plantilla" }),
    );
    fireEvent.change(screen.getByLabelText(/Nombre/), {
      target: { value: "recordatorio_turno" },
    });
    fireEvent.change(screen.getByLabelText(/Cuerpo/), {
      target: { value: "Hola" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Guardar plantilla" }));

    expect(
      await screen.findByText("El nombre ya existe en ese idioma."),
    ).toBeInTheDocument();
  });

  it("borra una plantilla tras confirmar 'Se borra también en Meta'", async () => {
    let deletedId: string | null = null;
    server.use(
      http.delete(
        "*/api/v1/accounts/:accountId/inboxes/:inboxId/whatsapp/templates/:id",
        ({ params }) => {
          deletedId = String(params.id);
          templatesStore = templatesStore.filter((t) => t.id !== deletedId);
          return HttpResponse.json({ templates: templatesStore });
        },
      ),
    );

    const confirmSpy = vi
      .spyOn(window, "confirm")
      .mockImplementation(() => true);

    renderPanel();
    expect(await screen.findByText("promo_verano")).toBeInTheDocument();

    const deleteButtons = await screen.findAllByRole("button", {
      name: "Borrar",
    });
    fireEvent.click(deleteButtons[1]); // promo_verano (id 222)

    expect(confirmSpy).toHaveBeenCalledWith(
      expect.stringContaining("Se borra también en Meta"),
    );
    await waitFor(() => expect(deletedId).toBe("222"));
    await waitFor(() =>
      expect(screen.queryByText("promo_verano")).not.toBeInTheDocument(),
    );
  });

  it("edita una plantilla existente (nombre e idioma bloqueados) y permite actualizar desde Meta", async () => {
    let editedId: string | null = null;
    let editedBody: Record<string, unknown> | null = null;
    let synced = false;

    server.use(
      http.post(
        "*/api/v1/accounts/:accountId/inboxes/:inboxId/whatsapp/templates/sync",
        () => {
          synced = true;
          return HttpResponse.json({ templates: templatesStore });
        },
      ),
      http.post(
        "*/api/v1/accounts/:accountId/inboxes/:inboxId/whatsapp/templates/:id",
        async ({ params, request }) => {
          editedId = String(params.id);
          editedBody = (await request.json()) as Record<string, unknown>;
          return HttpResponse.json({
            result: { success: true },
            templates: templatesStore.map((t) =>
              t.id === editedId ? { ...t, status: "PENDING" } : t,
            ),
          });
        },
      ),
    );

    renderPanel();
    expect(await screen.findByText("recordatorio_turno")).toBeInTheDocument();

    fireEvent.click(
      screen.getByRole("button", { name: "Actualizar desde Meta" }),
    );
    await waitFor(() => expect(synced).toBe(true));

    const editButtons = screen.getAllByRole("button", { name: "Editar" });
    fireEvent.click(editButtons[0]); // recordatorio_turno (id 111)

    expect(screen.getByLabelText("Nombre")).toBeDisabled();
    expect(screen.getByLabelText("Idioma")).toBeDisabled();

    fireEvent.change(screen.getByLabelText("Cuerpo"), {
      target: { value: "Hola {{1}}, reprogramamos para el {{2}}." },
    });
    fireEvent.click(screen.getByRole("button", { name: "Guardar plantilla" }));

    await waitFor(() => expect(editedId).toBe("111"));
    expect(editedBody).toEqual({
      category: "UTILITY",
      components: [
        {
          type: "BODY",
          text: "Hola {{1}}, reprogramamos para el {{2}}.",
          example: { body_text: [["Ana", "martes 10:00"]] },
        },
      ],
    });
  });
});
