import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";

import { DecisionsView } from "./decisions-view";

const questions = [
  {
    key: "intent",
    enabled: true,
    instructions: "¿Qué quiere el cliente en esta conversación?",
    options: [
      { key: "inscripcion", description: "Quiere anotarse o inscribirse a un curso" },
      { key: "precios", description: "Pregunta precios, cuotas o formas de pago" },
    ],
  },
  {
    key: "team",
    enabled: true,
    instructions: "¿Qué equipo debería atender esta conversación?",
    options: [
      { key: "team_3", description: "Ventas" },
      { key: "ninguno", description: "Ningún equipo en particular" },
    ],
  },
];

let savedSettings: unknown = null;
let savedLabels: unknown = null;
let labelingDone = false;

const server = setupServer(
  http.get("*/decisions/settings", () =>
    HttpResponse.json({ enabled: false, configured: false, model: "jev-latest", questions }),
  ),
  http.put("*/decisions/settings", async ({ request }) => {
    savedSettings = await request.json();
    return HttpResponse.json({ enabled: true, configured: false, model: "jev-latest", questions });
  }),
  http.get("*/decisions/labeling/next", () =>
    HttpResponse.json({
      payload: labelingDone
        ? null
        : {
            conversation_id: 12,
            text: "Cliente: ¿Cuánto sale el curso de inglés?",
            questions,
            answered: {},
          },
    }),
  ),
  http.post("*/decisions/labels", async ({ request }) => {
    savedLabels = await request.json();
    labelingDone = true;
    return HttpResponse.json({ saved: 2 });
  }),
  http.get("*/decisions/report", () =>
    HttpResponse.json({
      days: 30,
      conversations: 4,
      labeled_conversations: 2,
      questions: [
        {
          key: "intent",
          instructions: "¿Qué quiere?",
          options: questions[0].options,
          decided: 4,
          compared: 2,
          agreed: 1,
          agreement: 0.5,
          mean_confidence: 0.82,
          answers: { precios: 3, inscripcion: 1 },
        },
      ],
      month: { calls: 4, cost_usd: 0.000084 },
      priority: { set_by_ai: 5, changed_by_others: 1 },
    }),
  ),
);

beforeAll(() => server.listen({ onUnhandledRequest: "bypass" }));
afterEach(() => {
  server.resetHandlers();
  savedSettings = null;
  savedLabels = null;
  labelingDone = false;
});
afterAll(() => server.close());

function renderView() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <DecisionsView accountId="1" />
    </QueryClientProvider>,
  );
}

describe("DecisionsView", () => {
  it("turns shadow mode on and edits the intents", async () => {
    renderView();
    expect(await screen.findByText(/Falta cargar el servicio de decisiones/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("checkbox", { name: /Clasificar en modo sombra/ }));
    fireEvent.change(screen.getAllByLabelText("Opción 2")[0], {
      target: { value: "Precios y cuotas" },
    });
    fireEvent.click(screen.getAllByRole("button", { name: /Agregar opción/ })[0]);
    fireEvent.change(screen.getAllByLabelText("Opción 3")[0], { target: { value: "Certificados" } });
    expect(screen.getByText(/Las opciones son los equipos: Ventas/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Guardar" }));

    expect(await screen.findByText("Guardado.")).toBeInTheDocument();
    const body = savedSettings as { enabled: boolean; questions: typeof questions };
    expect(body.enabled).toBe(true);
    expect(body.questions[0].options.map((o) => o.description)).toEqual([
      "Quiere anotarse o inscribirse a un curso",
      "Precios y cuotas",
      "Certificados",
    ]);
    expect(body.questions[1].options).toEqual([]);
  });

  it("lets the local model classify with the business context and set the priority", async () => {
    const urgency = {
      key: "urgency",
      enabled: true,
      instructions: "¿Qué tan urgente es responderle?",
      options: [
        { key: "baja", description: "Puede esperar a mañana" },
        { key: "urgente", description: "Inscripciones para 2027" },
      ],
    };
    server.use(
      http.get("*/decisions/settings", () =>
        HttpResponse.json({
          enabled: true,
          provider: "api",
          providers: { api: false, local: true },
          configured: false,
          model: "jev-latest",
          context: "",
          apply_priority: false,
          questions: [
            {
              key: "intent",
              enabled: true,
              instructions: "¿Qué quiere el cliente?",
              options: [
                { key: "precios", description: "Pregunta precios" },
                { key: "otro", description: "Otra cosa" },
              ],
            },
            urgency,
          ],
        }),
      ),
    );
    renderView();

    // The urgency options say which priority they set.
    expect(await screen.findByText("Prioridad Urgente")).toBeInTheDocument();
    expect(screen.getByText("Prioridad Baja")).toBeInTheDocument();
    // Jev isn't set up here: said next to it.
    expect(screen.getByText("No está configurado")).toBeInTheDocument();
    expect(screen.queryByText(/escribí en cada opción qué conversaciones van ahí/)).toBeNull();

    fireEvent.click(screen.getByRole("radio", { name: /Modelo local \(Qwen/ }));
    // The local model follows each urgency option as a rule: said there,
    // and only there (getByText fails on two).
    expect(screen.getByText(/escribí en cada opción qué conversaciones van ahí/)).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Lo que la IA tiene que saber del negocio"), {
      target: { value: "En enero el instituto está cerrado." },
    });
    fireEvent.click(screen.getByRole("checkbox", { name: /Poner la prioridad de la conversación/ }));
    // The urgency question can set it: no warning.
    expect(screen.queryByText(/Para poner la prioridad/)).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Guardar" }));

    expect(await screen.findByText("Guardado.")).toBeInTheDocument();
    expect(savedSettings).toMatchObject({
      enabled: true,
      provider: "local",
      context: "En enero el instituto está cerrado.",
      apply_priority: true,
    });
  });

  it("warns when the urgency question can't set the priority", async () => {
    server.use(
      http.get("*/decisions/settings", () =>
        HttpResponse.json({
          enabled: true,
          provider: "local",
          providers: { api: false, local: true },
          configured: true,
          model: "qwen3-4b",
          context: "",
          apply_priority: true,
          questions: [
            {
              key: "urgency",
              enabled: false,
              instructions: "¿Qué tan urgente es responderle?",
              options: [
                { key: "baja", description: "Puede esperar" },
                { key: "urgente", description: "Ya" },
              ],
            },
          ],
        }),
      ),
    );
    renderView();
    expect(await screen.findByText(/Para poner la prioridad, la pregunta de urgencia/)).toBeInTheDocument();
  });

  it("labels a conversation without showing the service's answer", async () => {
    renderView();
    fireEvent.click(await screen.findByRole("tab", { name: "Etiquetar" }));
    expect(await screen.findByText("Cliente: ¿Cuánto sale el curso de inglés?")).toBeInTheDocument();
    const save = screen.getByRole("button", { name: "Guardar y seguir" });
    expect(save).toBeDisabled();
    const intent = screen.getByRole("group", { name: "Intención" });
    fireEvent.click(within(intent).getByRole("button", { name: /Pregunta precios/ }));
    fireEvent.click(screen.getByRole("button", { name: "Ventas" }));
    fireEvent.click(save);

    expect(
      await screen.findByText(/No hay conversaciones para etiquetar/),
    ).toBeInTheDocument();
    expect(savedLabels).toEqual({
      conversation_id: 12,
      answers: { intent: "precios", team: "team_3" },
    });
  });

  it("shows how often it agrees with people and what it costs", async () => {
    renderView();
    fireEvent.click(await screen.findByRole("tab", { name: "Resultados" }));
    expect(await screen.findByText(/Acierta 50\s?% \(1 de 2 comparadas\)/)).toBeInTheDocument();
    expect(screen.getByText(/Pregunta precios, cuotas o formas de pago · 3/)).toBeInTheDocument();
    expect(screen.getByText("Costo del mes (4 consultas)")).toBeInTheDocument();
    expect(screen.getByText(/menos de US\$\s?0,01/)).toBeInTheDocument();
    expect(
      screen.getByText("La IA puso la prioridad en 5 conversaciones; una persona o una regla la cambió en 1."),
    ).toBeInTheDocument();
  });
});
