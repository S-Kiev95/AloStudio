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

import type {
  AgentStatus,
  AgentThread,
  AgentThreadSummary,
} from "@/lib/api/agent";

import { AgentChatView } from "./agent-chat-view";
import { AgentShell } from "./agent-shell";
import { AgentThreadList } from "./agent-thread-list";

let mockPathname = "/accounts/1/agent";
const push = vi.fn();
const replace = vi.fn();

vi.mock("next/navigation", () => ({
  usePathname: () => mockPathname,
  useRouter: () => ({ push, replace }),
}));

const DEFAULT_STATUS: AgentStatus = {
  enabled: true,
  model: "gpt-5.4-mini",
  can_write: true,
};

const SAMPLE_SUMMARIES: AgentThreadSummary[] = [
  {
    id: 7,
    title: "Post para el lunes",
    updated_at: "2026-10-30T14:02:11Z",
    has_pending_action: true,
  },
  {
    id: 5,
    title: "Resumen del mes",
    updated_at: "2026-10-29T10:00:00Z",
    has_pending_action: false,
  },
];

const THREAD_7_PENDING: AgentThread = {
  id: 7,
  title: "Post para el lunes",
  created_at: "2026-10-30T14:00:02Z",
  updated_at: "2026-10-30T14:02:11Z",
  items: [
    {
      id: 31,
      kind: "user",
      content: "Armame un post para el lunes a las 10 en Instagram",
      created_at: "2026-10-30T14:00:02Z",
    },
    {
      id: 33,
      kind: "tool",
      tool: "list_publication_channels",
      status: "done",
      label: "Consultó tus canales",
      detail: null,
      publication_id: null,
      created_at: "2026-10-30T14:00:05Z",
    },
    {
      id: 35,
      kind: "tool",
      tool: "create_publication",
      status: "pending",
      label: "Espera tu confirmación",
      detail: null,
      publication_id: null,
      created_at: "2026-10-30T14:00:09Z",
    },
  ],
  pending_action: {
    id: "call_Q2x9",
    tool: "create_publication",
    title: "Programar publicación",
    confirm_label: "Programar",
    publication: {
      id: null,
      content:
        "¡Arrancamos la semana con todo!\nLínea 2\nLínea 3\nLínea 4\nLínea 5\nLínea 6\nLínea 7\nLínea 8\nLínea 9 oculta al inicio",
      scheduled_for: "2026-11-02T13:00:00Z",
      channels: [{ id: 4, name: "Tienda Salto", network: "instagram" }],
      media: [
        { id: 9, type: "image", url: "https://cdn.alostudio.test/foto.jpg" },
        { id: 10, type: "video", url: "https://cdn.alostudio.test/clip.mp4" },
      ],
    },
  },
};

const THREAD_5: AgentThread = {
  id: 5,
  title: "Resumen del mes",
  created_at: "2026-10-29T09:58:00Z",
  updated_at: "2026-10-29T10:00:00Z",
  items: [
    {
      id: 10,
      kind: "user",
      content: "¿Cómo les fue a mis publicaciones del último mes?",
      created_at: "2026-10-29T09:58:00Z",
    },
    {
      id: 11,
      kind: "assistant",
      content: "Tuviste 12 publicaciones con un alcance total de 18.400 cuentas.",
      created_at: "2026-10-29T09:58:12Z",
    },
  ],
  pending_action: null,
};

const server = setupServer(
  http.get("*/api/v1/accounts/1/agent", () =>
    HttpResponse.json(DEFAULT_STATUS),
  ),
  http.get("*/api/v1/accounts/1/agent/threads", () =>
    HttpResponse.json({ threads: SAMPLE_SUMMARIES }),
  ),
  http.get("*/api/v1/accounts/1/agent/threads/7", () =>
    HttpResponse.json(THREAD_7_PENDING),
  ),
  http.get("*/api/v1/accounts/1/agent/threads/5", () =>
    HttpResponse.json(THREAD_5),
  ),
);

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));

beforeEach(() => {
  mockPathname = "/accounts/1/agent";
  push.mockReset();
  replace.mockReset();
});

afterEach(() => {
  server.resetHandlers();
  vi.restoreAllMocks();
});

afterAll(() => server.close());

function makeQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
}

function renderAgentScreen(threadId: number | null, qc = makeQueryClient()) {
  mockPathname =
    threadId === null
      ? "/accounts/1/agent"
      : `/accounts/1/agent/${threadId}`;

  return {
    qc,
    ...render(
      <QueryClientProvider client={qc}>
        <AgentShell list={<AgentThreadList accountId="1" />}>
          <AgentChatView accountId="1" threadId={threadId} />
        </AgentShell>
      </QueryClientProvider>,
    ),
  };
}

describe("Agente — lista de chats y navegación sin recarga", () => {
  it("muestra los chats, la etiqueta 'Por confirmar', no recarga la lista al cambiar de chat y permite borrar con confirmación", async () => {
    let threadsFetches = 0;
    let deletedId: number | null = null;
    let currentThreads = [...SAMPLE_SUMMARIES];

    server.use(
      http.get("*/api/v1/accounts/1/agent/threads", () => {
        threadsFetches += 1;
        return HttpResponse.json({ threads: currentThreads });
      }),
      http.delete("*/api/v1/accounts/1/agent/threads/:threadId", ({ params }) => {
        deletedId = Number(params.threadId);
        currentThreads = currentThreads.filter((t) => t.id !== deletedId);
        return HttpResponse.json({});
      }),
    );

    const qc = makeQueryClient();
    const { rerender } = renderAgentScreen(7, qc);

    const listCol = screen.getByTestId("agent-threads-column");
    expect(
      await within(listCol).findByText("Post para el lunes"),
    ).toBeInTheDocument();
    expect(within(listCol).getByText("Por confirmar")).toBeInTheDocument();
    expect(within(listCol).getByText("Resumen del mes")).toBeInTheDocument();

    const activeLink7 = within(listCol).getByRole("link", {
      name: /Post para el lunes/i,
    });
    expect(activeLink7).toHaveAttribute("aria-current", "page");
    expect(threadsFetches).toBe(1);

    // Switch to thread #5 without unmounting or refetching the thread list
    mockPathname = "/accounts/1/agent/5";
    rerender(
      <QueryClientProvider client={qc}>
        <AgentShell list={<AgentThreadList accountId="1" />}>
          <AgentChatView accountId="1" threadId={5} />
        </AgentShell>
      </QueryClientProvider>,
    );

    expect(
      await screen.findByText(
        "Tuviste 12 publicaciones con un alcance total de 18.400 cuentas.",
      ),
    ).toBeInTheDocument();
    expect(
      within(listCol).getByRole("link", { name: /Resumen del mes/i }),
    ).toHaveAttribute("aria-current", "page");
    expect(threadsFetches).toBe(1);

    // Mobile "Chats" button opens the thread column
    fireEvent.click(screen.getByRole("button", { name: /^Chats$/i }));
    expect(listCol.className).toContain("flex");

    // Delete active thread #5 after confirmation
    vi.spyOn(window, "confirm").mockReturnValueOnce(true);
    fireEvent.click(
      within(listCol).getByRole("button", {
        name: "Borrar chat Resumen del mes",
      }),
    );

    await waitFor(() => expect(deletedId).toBe(5));
    expect(push).toHaveBeenCalledWith("/accounts/1/agent");
    await waitFor(() =>
      expect(
        within(listCol).queryByText("Resumen del mes"),
      ).not.toBeInTheDocument(),
    );
  });

  it("muestra 'Todavía no tenés chats.' cuando la lista viene vacía", async () => {
    server.use(
      http.get("*/api/v1/accounts/1/agent/threads", () =>
        HttpResponse.json({ threads: [] }),
      ),
    );

    renderAgentScreen(null);

    expect(
      await screen.findByText("Todavía no tenés chats."),
    ).toBeInTheDocument();
  });
});

describe("Agente — enviar un mensaje, burbuja optimista, 'Pensando…' y composer", () => {
  it("muestra la burbuja optimista y 'Pensando…' al enviar y luego los reemplaza por el Chat devuelto", async () => {
    let resolveTurn!: (thread: AgentThread) => void;
    let receivedPayload: unknown = null;

    server.use(
      http.post("*/api/v1/accounts/1/agent/threads", async ({ request }) => {
        receivedPayload = await request.json();
        const created = await new Promise<AgentThread>((resolve) => {
          resolveTurn = resolve;
        });
        return HttpResponse.json(created);
      }),
    );

    renderAgentScreen(null);

    // Wait for empty state greeting and 3 suggestions
    expect(
      await screen.findByText(/Hola, soy el agente de AloStudio/i),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", {
        name: "Armá una publicación para mañana a las 10 en todos mis canales",
      }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", {
        name: "¿Qué tengo programado esta semana?",
      }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", {
        name: "¿Cómo les fue a mis publicaciones del último mes?",
      }),
    ).toBeInTheDocument();

    const textarea = screen.getByLabelText("Mensaje para el agente");
    const sendBtn = screen.getByRole("button", { name: "Enviar mensaje" });
    expect(sendBtn).toBeDisabled();

    // Shift+Enter does not submit
    fireEvent.change(textarea, {
      target: { value: "Revisá mis posts de esta semana" },
    });
    fireEvent.keyDown(textarea, { key: "Enter", shiftKey: true });
    expect(receivedPayload).toBeNull();

    // Enter submits immediately
    fireEvent.keyDown(textarea, { key: "Enter", shiftKey: false });

    // Optimistic user bubble + "Pensando…" appear right away
    expect(
      await screen.findByText("Revisá mis posts de esta semana"),
    ).toBeInTheDocument();
    const thinking = screen.getByText("Pensando…");
    expect(thinking).toBeInTheDocument();
    expect(thinking).toHaveClass("animate-pulse");
    expect(textarea).toHaveValue("");

    await waitFor(() =>
      expect(receivedPayload).toMatchObject({
        content: "Revisá mis posts de esta semana",
      }),
    );
    expect(
      typeof (receivedPayload as { timezone?: unknown }).timezone,
    ).toBe("string");
    expect(
      ((receivedPayload as { timezone: string }).timezone || "").length,
    ).toBeGreaterThan(0);

    // Resolve the backend turn
    resolveTurn({
      id: 12,
      title: "Posts de la semana",
      created_at: "2026-10-30T15:00:00Z",
      updated_at: "2026-10-30T15:00:08Z",
      items: [
        {
          id: 101,
          kind: "user",
          content: "Revisá mis posts de esta semana",
          created_at: "2026-10-30T15:00:00Z",
        },
        {
          id: 102,
          kind: "tool",
          tool: "list_publications",
          status: "done",
          label: "Consultó tu calendario",
          detail: "2 publicaciones programadas",
          publication_id: 44,
          created_at: "2026-10-30T15:00:04Z",
        },
        {
          id: 103,
          kind: "assistant",
          content: "Tenés dos publicaciones listas:\n- Martes 10:00\n- Jueves 18:00",
          created_at: "2026-10-30T15:00:08Z",
        },
      ],
      pending_action: null,
    });

    expect(
      await screen.findByText(/Tenés dos publicaciones listas:/),
    ).toBeInTheDocument();
    expect(screen.queryByText("Pensando…")).not.toBeInTheDocument();
    expect(screen.getByText("Consultó tu calendario")).toBeInTheDocument();
    expect(screen.getByText("2 publicaciones programadas")).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Ver en el calendario" }),
    ).toHaveAttribute("href", "/accounts/1/publications?publication=44");
    expect(push).toHaveBeenCalledWith("/accounts/1/agent/12");
  });

  it("muestra el contador desde 3500 caracteres y bloquea el envío por encima de 4000", async () => {
    renderAgentScreen(null);
    await screen.findByText(/Hola, soy el agente de AloStudio/i);

    const textarea = screen.getByLabelText("Mensaje para el agente");
    const sendBtn = screen.getByRole("button", { name: "Enviar mensaje" });

    fireEvent.change(textarea, { target: { value: "a".repeat(3499) } });
    expect(screen.queryByText(/\/4000$/)).not.toBeInTheDocument();

    fireEvent.change(textarea, { target: { value: "a".repeat(3500) } });
    expect(screen.getByText("3500/4000")).toBeInTheDocument();
    expect(sendBtn).not.toBeDisabled();

    fireEvent.change(textarea, { target: { value: "a".repeat(4001) } });
    expect(screen.getByText("4001/4000")).toBeInTheDocument();
    expect(sendBtn).toBeDisabled();
  });
});

describe("Agente — tarjeta de confirmación (confirmar y cancelar)", () => {
  it("renderiza la vista previa y al confirmar pega a /actions/{id}/confirm, actualiza el chat e invalida publicaciones", async () => {
    let confirmedUrl = "";
    const confirmedThread: AgentThread = {
      ...THREAD_7_PENDING,
      updated_at: "2026-10-30T14:03:00Z",
      items: [
        ...THREAD_7_PENDING.items.slice(0, 2),
        {
          id: 35,
          kind: "tool",
          tool: "create_publication",
          status: "done",
          label: "Programó la publicación",
          detail: null,
          publication_id: 88,
          created_at: "2026-10-30T14:02:55Z",
        },
        {
          id: 36,
          kind: "assistant",
          content: "¡Listo! Ya quedó programada tu publicación para el lunes.",
          created_at: "2026-10-30T14:03:00Z",
        },
      ],
      pending_action: null,
    };

    server.use(
      http.post(
        "*/api/v1/accounts/1/agent/threads/7/actions/call_Q2x9/confirm",
        ({ request }) => {
          confirmedUrl = new URL(request.url).pathname;
          return HttpResponse.json(confirmedThread);
        },
      ),
    );

    const qc = makeQueryClient();
    const invalidateSpy = vi.spyOn(qc, "invalidateQueries");
    renderAgentScreen(7, qc);

    const card = await screen.findByTestId("agent-pending-action-card");
    expect(within(card).getByText("Programar publicación")).toBeInTheDocument();
    expect(within(card).getByText("Tienda Salto")).toBeInTheDocument();
    expect(within(card).getByRole("img", { name: "Instagram" })).toBeInTheDocument();
    expect(within(card).getByText(/^Sale el /)).toBeInTheDocument();
    expect(
      within(card).getByText(
        "Si querés cambiar algo, escribilo y el agente arma una nueva propuesta.",
      ),
    ).toBeInTheDocument();

    // Long text offers "Ver más"
    const verMasBtn = within(card).getByRole("button", { name: "Ver más" });
    fireEvent.click(verMasBtn);
    expect(
      within(card).getByRole("button", { name: "Ver menos" }),
    ).toBeInTheDocument();

    // Video thumbnail has preload="metadata" and no controls
    const videoEl = card.querySelector("video");
    expect(videoEl).not.toBeNull();
    expect(videoEl).toHaveAttribute("preload", "metadata");
    expect(videoEl).not.toHaveAttribute("controls");

    // Confirm action
    fireEvent.click(within(card).getByRole("button", { name: "Programar" }));

    expect(
      await screen.findByText(
        "¡Listo! Ya quedó programada tu publicación para el lunes.",
      ),
    ).toBeInTheDocument();
    expect(confirmedUrl).toContain(
      "/api/v1/accounts/1/agent/threads/7/actions/call_Q2x9/confirm",
    );
    expect(
      screen.queryByTestId("agent-pending-action-card"),
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Ver en el calendario" }),
    ).toHaveAttribute("href", "/accounts/1/publications?publication=88");

    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: ["publications", "1"],
    });
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: ["publication", "1", 88],
    });
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: ["publication-analytics", "1"],
    });
  });

  it("al cancelar pega a /actions/{id}/reject y muestra el chat sin la acción pendiente", async () => {
    let rejectedUrl = "";
    const rejectedThread: AgentThread = {
      ...THREAD_7_PENDING,
      items: [
        ...THREAD_7_PENDING.items.slice(0, 2),
        {
          id: 35,
          kind: "tool",
          tool: "create_publication",
          status: "rejected",
          label: "Propuesta cancelada",
          detail: null,
          publication_id: null,
          created_at: "2026-10-30T14:02:30Z",
        },
      ],
      pending_action: null,
    };

    server.use(
      http.post(
        "*/api/v1/accounts/1/agent/threads/7/actions/call_Q2x9/reject",
        ({ request }) => {
          rejectedUrl = new URL(request.url).pathname;
          return HttpResponse.json(rejectedThread);
        },
      ),
    );

    renderAgentScreen(7);

    const card = await screen.findByTestId("agent-pending-action-card");
    fireEvent.click(within(card).getByRole("button", { name: "Cancelar" }));

    expect(await screen.findByText("Propuesta cancelada")).toBeInTheDocument();
    expect(rejectedUrl).toContain(
      "/api/v1/accounts/1/agent/threads/7/actions/call_Q2x9/reject",
    );
    expect(
      screen.queryByTestId("agent-pending-action-card"),
    ).not.toBeInTheDocument();
  });

  it("muestra 'Se va a borrar esta publicación' para cancel_publication y 'Sale en los próximos minutos' cuando scheduled_for es null", async () => {
    server.use(
      http.get("*/api/v1/accounts/1/agent/threads/7", () =>
        HttpResponse.json({
          ...THREAD_7_PENDING,
          pending_action: {
            id: "call_del_1",
            tool: "cancel_publication",
            title: "Borrar publicación",
            confirm_label: "Borrar",
            publication: {
              id: 55,
              content: "Post a cancelar",
              scheduled_for: "2026-11-05T14:00:00Z",
              channels: [{ id: 4, name: "Tienda Salto", network: "instagram" }],
              media: [],
            },
          },
        }),
      ),
    );

    const { unmount } = renderAgentScreen(7);

    const card = await screen.findByTestId("agent-pending-action-card");
    expect(
      within(card).getByText("Se va a borrar esta publicación"),
    ).toBeInTheDocument();
    expect(within(card).getByRole("button", { name: "Borrar" })).toBeInTheDocument();

    unmount();

    server.use(
      http.get("*/api/v1/accounts/1/agent/threads/7", () =>
        HttpResponse.json({
          ...THREAD_7_PENDING,
          pending_action: {
            ...THREAD_7_PENDING.pending_action!,
            confirm_label: "Publicar ahora",
            publication: {
              ...THREAD_7_PENDING.pending_action!.publication,
              scheduled_for: null,
            },
          },
        }),
      ),
    );

    renderAgentScreen(7);
    const immediateCard = await screen.findByTestId("agent-pending-action-card");
    expect(
      within(immediateCard).getByText("Sale en los próximos minutos"),
    ).toBeInTheDocument();
    expect(
      within(immediateCard).getByRole("button", { name: "Publicar ahora" }),
    ).toBeInTheDocument();
  });
});

describe("Agente — errores del backend (503, 502, 409, 422) y sugerencias", () => {
  it("envía una sugerencia al tocarla y muestra el message si el backend responde 503", async () => {
    let sentBody: unknown = null;
    server.use(
      http.post("*/api/v1/accounts/1/agent/threads", async ({ request }) => {
        sentBody = await request.json();
        return HttpResponse.json(
          { message: "Falta configurar la clave de OpenAI." },
          { status: 503 },
        );
      }),
    );

    renderAgentScreen(null);

    const suggestionBtn = await screen.findByRole("button", {
      name: "¿Qué tengo programado esta semana?",
    });
    fireEvent.click(suggestionBtn);

    await waitFor(() =>
      expect(sentBody).toMatchObject({
        content: "¿Qué tengo programado esta semana?",
      }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Falta configurar la clave de OpenAI.",
    );
  });
  it("ante un 502 muestra el message junto al composer, no repone el texto y vuelve a pedir el chat con el mensaje guardado", async () => {
    let threadFetches = 0;
    let currentThread: AgentThread = { ...THREAD_5 };

    server.use(
      http.get("*/api/v1/accounts/1/agent/threads/5", () => {
        threadFetches += 1;
        return HttpResponse.json(currentThread);
      }),
      http.post(
        "*/api/v1/accounts/1/agent/threads/5/messages",
        async ({ request }) => {
          const body = (await request.json()) as { content: string };
          // The backend persisted the user's message before OpenAI timed out
          currentThread = {
            ...currentThread,
            items: [
              ...currentThread.items,
              {
                id: 99,
                kind: "user",
                content: body.content,
                created_at: "2026-10-30T16:00:00Z",
              },
            ],
          };
          return HttpResponse.json(
            { message: "OpenAI tardó demasiado en responder. Intentá de nuevo." },
            { status: 502 },
          );
        },
      ),
    );

    renderAgentScreen(5);

    expect(
      await screen.findByText(
        "Tuviste 12 publicaciones con un alcance total de 18.400 cuentas.",
      ),
    ).toBeInTheDocument();
    expect(threadFetches).toBe(1);

    const textarea = screen.getByLabelText("Mensaje para el agente");
    fireEvent.change(textarea, {
      target: { value: "Comparalo con el mes anterior" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Enviar mensaje" }));

    // Error message appears near composer
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "OpenAI tardó demasiado en responder. Intentá de nuevo.",
    );

    // Composer stays empty (not refilled) and the chat was refetched with the saved user message
    expect(textarea).toHaveValue("");
    await waitFor(() => expect(threadFetches).toBe(2));
    expect(
      await screen.findByText("Comparalo con el mes anterior"),
    ).toBeInTheDocument();
  });

  it("ante un 409 al confirmar vuelve a pedir el chat y conserva el mensaje de error visible", async () => {
    let currentThread: AgentThread = { ...THREAD_7_PENDING };

    server.use(
      http.get("*/api/v1/accounts/1/agent/threads/7", () =>
        HttpResponse.json(currentThread),
      ),
      http.post(
        "*/api/v1/accounts/1/agent/threads/7/actions/call_Q2x9/confirm",
        () => {
          currentThread = { ...THREAD_7_PENDING, pending_action: null };
          return HttpResponse.json(
            { message: "La acción ya no está pendiente." },
            { status: 409 },
          );
        },
      ),
    );

    renderAgentScreen(7);

    const card = await screen.findByTestId("agent-pending-action-card");
    fireEvent.click(within(card).getByRole("button", { name: "Programar" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "La acción ya no está pendiente.",
    );
    await waitFor(() =>
      expect(
        screen.queryByTestId("agent-pending-action-card"),
      ).not.toBeInTheDocument(),
    );
    expect(screen.getByRole("alert")).toHaveTextContent(
      "La acción ya no está pendiente.",
    );
  });

  it("ante un 422 muestra el message junto al composer", async () => {
    server.use(
      http.post("*/api/v1/accounts/1/agent/threads/5/messages", () =>
        HttpResponse.json(
          { message: "La zona horaria no es válida." },
          { status: 422 },
        ),
      ),
    );

    renderAgentScreen(5);
    await screen.findByText(
      "Tuviste 12 publicaciones con un alcance total de 18.400 cuentas.",
    );

    const textarea = screen.getByLabelText("Mensaje para el agente");
    fireEvent.change(textarea, { target: { value: "Hola" } });
    fireEvent.click(screen.getByRole("button", { name: "Enviar mensaje" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "La zona horaria no es válida.",
    );
    expect(textarea).toHaveValue("Hola");
  });
});

describe("Agente — enabled: false y can_write: false", () => {
  it("con enabled: false muestra el aviso de configuración en lugar del estado vacío, deshabilita el composer y deja leer chats viejos", async () => {
    server.use(
      http.get("*/api/v1/accounts/1/agent", () =>
        HttpResponse.json({
          enabled: false,
          model: "gpt-5.4-mini",
          can_write: true,
        }),
      ),
    );

    const qc = makeQueryClient();
    const { rerender } = renderAgentScreen(null, qc);

    expect(
      await screen.findByText(
        "El agente todavía no está configurado. Un operador de la instalación tiene que cargar la clave de OpenAI en Ajustes → Instalación → Inteligencia artificial.",
      ),
    ).toBeInTheDocument();
    expect(
      screen.queryByText(/Hola, soy el agente de AloStudio/i),
    ).not.toBeInTheDocument();
    expect(screen.getByLabelText("Mensaje para el agente")).toBeDisabled();
    expect(
      screen.getByRole("button", { name: "Enviar mensaje" }),
    ).toBeDisabled();

    // Existing thread remains readable while composer stays disabled
    mockPathname = "/accounts/1/agent/5";
    rerender(
      <QueryClientProvider client={qc}>
        <AgentShell list={<AgentThreadList accountId="1" />}>
          <AgentChatView accountId="1" threadId={5} />
        </AgentShell>
      </QueryClientProvider>,
    );

    expect(
      await screen.findByText(
        "Tuviste 12 publicaciones con un alcance total de 18.400 cuentas.",
      ),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Mensaje para el agente")).toBeDisabled();
  });

  it("con can_write: false muestra la nota de solo lectura bajo el encabezado y oculta la sugerencia de armar publicación", async () => {
    server.use(
      http.get("*/api/v1/accounts/1/agent", () =>
        HttpResponse.json({
          enabled: true,
          model: "gpt-5.4-mini",
          can_write: false,
        }),
      ),
    );

    renderAgentScreen(null);

    expect(
      await screen.findByText(
        "Podés consultar publicaciones y estadísticas. Crear o borrar publicaciones lo hace un administrador.",
      ),
    ).toBeInTheDocument();

    expect(
      screen.getByText(/Hola, soy el agente de AloStudio/i),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", {
        name: "Armá una publicación para mañana a las 10 en todos mis canales",
      }),
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole("button", {
        name: "¿Qué tengo programado esta semana?",
      }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", {
        name: "¿Cómo les fue a mis publicaciones del último mes?",
      }),
    ).toBeInTheDocument();
  });
});
