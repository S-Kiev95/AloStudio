import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
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
import type { Autopost, Channel } from "@/lib/api/publications";

import { AutopostsView } from "./autoposts-view";

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

let currentRole = ROLE_ADMINISTRATOR;
let autopostsStore: Autopost[] = [];

const INITIAL_AUTOPOSTS: Autopost[] = [
  {
    id: 1,
    name: "Blog AloStudio",
    feed_url: "https://alostudio.test/rss.xml",
    mode: "publish",
    active: true,
    start_with_latest: false,
    channel_ids: [],
    last_checked_at: new Date(Date.now() - 5 * 60_000).toISOString(),
    last_error: "Timeout al conectar con el servidor origen",
    created_at: "2026-10-10T10:00:00Z",
    updated_at: "2026-10-10T10:00:00Z",
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
  http.get("*/api/v1/accounts/:accountId/publications/channels", () =>
    HttpResponse.json([IG_CHANNEL]),
  ),
  http.get("*/api/v1/accounts/:accountId/publications/autoposts", () =>
    HttpResponse.json(autopostsStore),
  ),
);

beforeAll(() => server.listen({ onUnhandledRequest: "bypass" }));
beforeEach(() => {
  currentRole = ROLE_ADMINISTRATOR;
  autopostsStore = structuredClone(INITIAL_AUTOPOSTS);
});
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

function renderView() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={qc}>
      <AutopostsView accountId="1" />
    </QueryClientProvider>,
  );
}

describe("AutopostsView", () => {
  it("lista feeds con revisado hace y último error, prueba el feed (entradas y error 422), crea, edita y borra", async () => {
    let createdPayload: unknown = null;
    let patchedPayload: unknown = null;
    let patchedId: number | null = null;
    let deletedId: number | null = null;

    server.use(
      http.post(
        "*/api/v1/accounts/:accountId/publications/autoposts/preview",
        async ({ request }) => {
          const body = (await request.json()) as { feed_url: string };
          if (body.feed_url.includes("127.0.0.1")) {
            return HttpResponse.json(
              { message: "No se permiten direcciones de red privada." },
              { status: 422 },
            );
          }
          return HttpResponse.json({
            items: [
              {
                title: "Guía de automatización 2026",
                link: "https://noticias.test/guia-2026",
                image_url: null,
                published_at: "2026-10-25T10:00:00Z",
              },
              {
                title: "Cómo organizar tu calendario",
                link: "https://noticias.test/calendario",
                image_url: null,
                published_at: "2026-10-24T10:00:00Z",
              },
            ],
          });
        },
      ),
      http.post(
        "*/api/v1/accounts/:accountId/publications/autoposts",
        async ({ request }) => {
          const body = (await request.json()) as Omit<
            Autopost,
            "id" | "last_checked_at" | "last_error" | "created_at" | "updated_at"
          >;
          createdPayload = body;
          const created: Autopost = {
            id: 2,
            ...body,
            last_checked_at: null,
            last_error: null,
            created_at: "2026-10-26T10:00:00Z",
            updated_at: "2026-10-26T10:00:00Z",
          };
          autopostsStore = [...autopostsStore, created];
          return HttpResponse.json(created, { status: 201 });
        },
      ),
      http.patch(
        "*/api/v1/accounts/:accountId/publications/autoposts/:id",
        async ({ params, request }) => {
          patchedId = Number(params.id);
          const patch = (await request.json()) as Partial<Autopost>;
          patchedPayload = patch;
          autopostsStore = autopostsStore.map((item) =>
            item.id === patchedId ? { ...item, ...patch } : item,
          );
          return HttpResponse.json(
            autopostsStore.find((item) => item.id === patchedId)!,
          );
        },
      ),
      http.delete(
        "*/api/v1/accounts/:accountId/publications/autoposts/:id",
        ({ params }) => {
          deletedId = Number(params.id);
          autopostsStore = autopostsStore.filter((i) => i.id !== deletedId);
          return HttpResponse.json({});
        },
      ),
    );

    renderView();

    expect(await screen.findByText("Blog AloStudio")).toBeInTheDocument();
    expect(screen.getByText(/Revisado hace 5m/)).toBeInTheDocument();
    expect(
      screen.getByText(/Timeout al conectar con el servidor origen/),
    ).toBeInTheDocument();

    // Open create dialog & test "Probar" first with a 422 private URL, then with a valid feed
    fireEvent.click(
      await screen.findByRole("button", { name: "Agregar auto post" }),
    );

    const urlInput = screen.getByLabelText(/url del feed/i);
    fireEvent.change(urlInput, {
      target: { value: "http://127.0.0.1/private.xml" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Probar" }));

    expect(
      await screen.findByText("No se permiten direcciones de red privada."),
    ).toBeInTheDocument();

    fireEvent.change(urlInput, {
      target: { value: "https://noticias.test/feed.xml" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Probar" }));

    expect(
      await screen.findByText("Guía de automatización 2026"),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Cómo organizar tu calendario"),
    ).toBeInTheDocument();

    // Fill rest of form and create
    fireEvent.change(screen.getByLabelText(/^nombre/i), {
      target: { value: "Noticias externas" },
    });
    fireEvent.change(
      screen.getByLabelText("¿Qué hacer con cada entrada nueva?"),
      { target: { value: "draft" } },
    );
    fireEvent.click(screen.getByRole("button", { name: "Algunos canales" }));
    fireEvent.click(screen.getByRole("button", { name: /alostudio ig/i }));
    fireEvent.click(
      screen.getByLabelText(
        "Publicar también la última entrada que ya está en el feed",
      ),
    );
    fireEvent.click(screen.getByRole("button", { name: "Guardar auto post" }));

    await waitFor(() => {
      expect(createdPayload).toEqual({
        name: "Noticias externas",
        feed_url: "https://noticias.test/feed.xml",
        mode: "draft",
        active: true,
        start_with_latest: true,
        channel_ids: [10],
      });
    });
    expect(await screen.findByText("Noticias externas")).toBeInTheDocument();

    // Edit first autopost
    const editButtons = screen.getAllByRole("button", {
      name: "Editar auto post",
    });
    fireEvent.click(editButtons[0]);
    fireEvent.change(screen.getByLabelText(/^nombre/i), {
      target: { value: "Blog Principal" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Guardar cambios" }));

    await waitFor(() => {
      expect(patchedId).toBe(1);
      expect(patchedPayload).toMatchObject({
        name: "Blog Principal",
        feed_url: "https://alostudio.test/rss.xml",
      });
    });
    expect(await screen.findByText("Blog Principal")).toBeInTheDocument();

    // Delete first autopost
    const deleteButtons = screen.getAllByRole("button", {
      name: "Borrar auto post",
    });
    fireEvent.click(deleteButtons[0]);

    await waitFor(() => {
      expect(deletedId).toBe(1);
    });
    await waitFor(() => {
      expect(screen.queryByText("Blog Principal")).not.toBeInTheDocument();
    });
  });

  it("oculta escritura cuando el usuario es agente", async () => {
    currentRole = ROLE_AGENT;
    renderView();

    expect(await screen.findByText("Blog AloStudio")).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Agregar auto post" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Editar auto post" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Borrar auto post" }),
    ).not.toBeInTheDocument();
  });
});
