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
} from "vitest";

import { ROLE_ADMINISTRATOR, ROLE_AGENT } from "@/lib/api/account";
import type {
  Channel,
  Plug,
  PlugCatalogEntry,
} from "@/lib/api/publications";

import { PlugsView } from "./plugs-view";

const IG_CHANNEL: Channel = {
  id: 10,
  network: "instagram",
  name: "AloStudio IG",
  username: "alostudio",
  avatar_url: null,
  inbox_id: 3,
  status: "active",
  status_message: null,
};

const THREADS_CHANNEL: Channel = {
  id: 20,
  network: "threads",
  name: "AloStudio Threads",
  username: "alostudio_th",
  avatar_url: null,
  inbox_id: null,
  status: "active",
  status_message: null,
};

const CATALOG: PlugCatalogEntry[] = [
  {
    network: "threads",
    kinds: [
      {
        kind: "reply",
        label: "Responder al hilo",
        description: "Publica una respuesta automática en el hilo.",
        message_max: 500,
      },
      {
        kind: "repost",
        label: "Repostear publicación",
        description: "Repostea la publicación sin texto adicional.",
        message_max: null,
      },
    ],
  },
];

let currentRole = ROLE_ADMINISTRATOR;
let channelsStore: Channel[] = [];
let plugsStore: Plug[] = [];

const INITIAL_PLUGS: Plug[] = [
  {
    id: 10,
    channel_id: 20,
    kind: "reply",
    likes_threshold: 25,
    message: "Sumate a nuestra newsletter",
    active: true,
    runs: [
      {
        target_id: 301,
        ok: true,
        error_message: null,
        ran_at: "2026-10-20T14:00:00Z",
      },
      {
        target_id: 302,
        ok: false,
        error_message: "Permiso de Threads revocado",
        ran_at: "2026-10-21T14:00:00Z",
      },
    ],
    created_at: "2026-10-15T10:00:00Z",
    updated_at: "2026-10-15T10:00:00Z",
  },
];

const server = setupServer(
  http.get("*/api/v1/profile", () =>
    HttpResponse.json({
      data: {
        id: 1,
        name: "Zeek",
        email: "zeek@alostudio.test",
        accounts: [{ id: 1, name: "AloStudio", role: currentRole }],
      },
    }),
  ),
  http.get("*/api/v1/accounts/:accountId/publications/plugs/catalog", () =>
    HttpResponse.json(CATALOG),
  ),
  http.get("*/api/v1/accounts/:accountId/publications/channels", () =>
    HttpResponse.json(channelsStore),
  ),
  http.get("*/api/v1/accounts/:accountId/publications/plugs", () =>
    HttpResponse.json(plugsStore),
  ),
);

beforeAll(() => server.listen({ onUnhandledRequest: "bypass" }));
beforeEach(() => {
  currentRole = ROLE_ADMINISTRATOR;
  channelsStore = [IG_CHANNEL, THREADS_CHANNEL];
  plugsStore = structuredClone(INITIAL_PLUGS);
});
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

function renderView() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={qc}>
      <PlugsView accountId="1" />
    </QueryClientProvider>,
  );
}

describe("PlugsView", () => {
  it("sin canales compatibles muestra 'Conectá Threads para usar acciones automáticas' con link al calendario", async () => {
    channelsStore = [IG_CHANNEL]; // Only Instagram; catalog only has Threads
    plugsStore = [];

    renderView();

    expect(
      await screen.findByText(
        "Conectá Threads para usar acciones automáticas",
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", {
        name: /ir al calendario para conectar canales/i,
      }),
    ).toHaveAttribute("href", "/accounts/1/publications");
  });

  it("pide mensaje solo cuando la acción tiene message_max, cuenta UTF-8 de Threads y permite listar, crear, editar y borrar", async () => {
    const createdBodies: unknown[] = [];
    let patchedBody: unknown = null;
    let patchedId: number | null = null;
    let deletedId: number | null = null;

    server.use(
      http.post(
        "*/api/v1/accounts/:accountId/publications/plugs",
        async ({ request }) => {
          const body = (await request.json()) as {
            channel_id: number;
            kind: string;
            likes_threshold: number;
            message?: string | null;
            active?: boolean;
          };
          createdBodies.push(body);
          const created: Plug = {
            id: 10 + createdBodies.length,
            channel_id: body.channel_id,
            kind: body.kind,
            likes_threshold: body.likes_threshold,
            message: body.message ?? null,
            active: body.active ?? true,
            runs: [],
            created_at: "2026-10-25T10:00:00Z",
            updated_at: "2026-10-25T10:00:00Z",
          };
          plugsStore = [...plugsStore, created];
          return HttpResponse.json(created, { status: 201 });
        },
      ),
      http.patch(
        "*/api/v1/accounts/:accountId/publications/plugs/:id",
        async ({ params, request }) => {
          patchedId = Number(params.id);
          const patch = (await request.json()) as {
            likes_threshold?: number;
            message?: string | null;
            active?: boolean;
          };
          patchedBody = patch;
          plugsStore = plugsStore.map((p) =>
            p.id === patchedId
              ? {
                  ...p,
                  likes_threshold: patch.likes_threshold ?? p.likes_threshold,
                  message:
                    patch.message !== undefined ? patch.message : p.message,
                  active: patch.active ?? p.active,
                }
              : p,
          );
          return HttpResponse.json(
            plugsStore.find((p) => p.id === patchedId)!,
          );
        },
      ),
      http.delete(
        "*/api/v1/accounts/:accountId/publications/plugs/:id",
        ({ params }) => {
          deletedId = Number(params.id);
          plugsStore = plugsStore.filter((p) => p.id !== deletedId);
          return HttpResponse.json({});
        },
      ),
    );

    renderView();

    // Lists existing plug + runs (Bien & Falló + reason)
    expect(
      await screen.findByText("Sumate a nuestra newsletter"),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Cuando llegue a 25 me gusta"),
    ).toBeInTheDocument();
    expect(screen.getByText("Bien")).toBeInTheDocument();
    expect(screen.getByText("Falló")).toBeInTheDocument();
    expect(
      screen.getByText(/Permiso de Threads revocado/),
    ).toBeInTheDocument();

    // Open dialog: default action is "reply" (message_max: 500) -> message field IS present
    fireEvent.click(await screen.findByRole("button", { name: "Agregar plug" }));
    const msgInput = screen.getByLabelText(/^mensaje/i);
    expect(msgInput).toBeInTheDocument();

    // Verify Threads length calculation: "🔥" = 4 UTF-8 bytes on Threads
    fireEvent.change(msgInput, { target: { value: "🔥" } });
    expect(screen.getByText("4 / 500")).toBeInTheDocument();

    // Switch action to "repost" (message_max: null) -> message field MUST disappear!
    fireEvent.change(screen.getByLabelText(/^acción/i), {
      target: { value: "repost" },
    });
    expect(screen.queryByLabelText(/^mensaje/i)).not.toBeInTheDocument();

    fireEvent.change(screen.getByLabelText(/cuando llegue a n me gusta/i), {
      target: { value: "50" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Guardar plug" }));

    await waitFor(() => {
      expect(createdBodies[0]).toEqual({
        channel_id: 20,
        kind: "repost",
        likes_threshold: 50,
        active: true,
      });
    });
    const channelSection = screen.getByRole("region", {
      name: /plugs de alostudio threads/i,
    });
    expect(
      await within(channelSection).findByText("Repostear publicación"),
    ).toBeInTheDocument();

    // Create a second plug with "reply" (message_max: 500) -> message IS sent
    fireEvent.click(screen.getByRole("button", { name: "Agregar plug" }));
    fireEvent.change(screen.getByLabelText(/cuando llegue a n me gusta/i), {
      target: { value: "15" },
    });
    fireEvent.change(screen.getByLabelText(/^mensaje/i), {
      target: { value: "Gracias por leer 🔥" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Guardar plug" }));

    await waitFor(() => {
      expect(createdBodies[1]).toEqual({
        channel_id: 20,
        kind: "reply",
        likes_threshold: 15,
        message: "Gracias por leer 🔥",
        active: true,
      });
    });
    expect(
      await within(channelSection).findByText("Gracias por leer 🔥"),
    ).toBeInTheDocument();

    // Edit existing plug (#10)
    const editButtons = screen.getAllByRole("button", { name: "Editar plug" });
    fireEvent.click(editButtons[0]);
    fireEvent.change(screen.getByLabelText(/cuando llegue a n me gusta/i), {
      target: { value: "40" },
    });
    fireEvent.change(screen.getByLabelText(/^mensaje/i), {
      target: { value: "Nuevo link en bio" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Guardar cambios" }));

    await waitFor(() => {
      expect(patchedId).toBe(10);
      expect(patchedBody).toEqual({
        likes_threshold: 40,
        message: "Nuevo link en bio",
        active: true,
      });
    });
    expect(
      await within(channelSection).findByText("Nuevo link en bio"),
    ).toBeInTheDocument();

    // Delete plug (#10)
    const deleteButtons = screen.getAllByRole("button", { name: "Borrar plug" });
    fireEvent.click(deleteButtons[0]);

    await waitFor(() => {
      expect(deletedId).toBe(10);
    });
    await waitFor(() => {
      expect(
        within(channelSection).queryByText("Nuevo link en bio"),
      ).not.toBeInTheDocument();
    });
  });

  it("muestra errores 422 tal cual y oculta escritura para agentes", async () => {
    server.use(
      http.post("*/api/v1/accounts/:accountId/publications/plugs", () =>
        HttpResponse.json(
          { message: "El canal elegido necesita reconectarse." },
          { status: 422 },
        ),
      ),
    );

    const { unmount } = renderView();
    fireEvent.click(await screen.findByRole("button", { name: "Agregar plug" }));
    fireEvent.change(screen.getByLabelText(/^mensaje/i), {
      target: { value: "Hola" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Guardar plug" }));

    expect(
      await screen.findByText("El canal elegido necesita reconectarse."),
    ).toBeInTheDocument();

    unmount();

    currentRole = ROLE_AGENT;
    renderView();
    expect(
      await screen.findByText("Sumate a nuestra newsletter"),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Agregar plug" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Editar plug" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Borrar plug" }),
    ).not.toBeInTheDocument();
  });
});
