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
import type { Channel, PublicationSet } from "@/lib/api/publications";

import { SetsView } from "./sets-view";

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

let currentRole = ROLE_ADMINISTRATOR;
let setsStore: PublicationSet[] = [];

const INITIAL_SETS: PublicationSet[] = [
  {
    id: 5,
    name: "Lanzamiento semanal",
    content: "Novedades de la semana",
    media: [],
    targets: [
      {
        channel_id: 10,
        channel: IG_CHANNEL,
        settings: { post_type: "feed" },
        content_override: null,
      },
    ],
    created_at: "2026-10-12T10:00:00Z",
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
  http.get("*/api/v1/accounts/:accountId/publications/channels", () =>
    HttpResponse.json([IG_CHANNEL, THREADS_CHANNEL]),
  ),
  http.get("*/api/v1/accounts/:accountId/publications/sets", () =>
    HttpResponse.json(setsStore),
  ),
  http.get("*/api/v1/accounts/:accountId/publications/signatures", () =>
    HttpResponse.json([]),
  ),
  http.get("*/api/v1/accounts/:accountId/media", () => HttpResponse.json([])),
);

beforeAll(() => server.listen({ onUnhandledRequest: "bypass" }));
beforeEach(() => {
  currentRole = ROLE_ADMINISTRATOR;
  setsStore = structuredClone(INITIAL_SETS);
});
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

function renderView() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={qc}>
      <SetsView accountId="1" />
    </QueryClientProvider>,
  );
}

describe("SetsView", () => {
  it("lista sets con canales y fecha, crea en modo set con el editor, edita y borra", async () => {
    let createdPayload: unknown = null;
    let patchedPayload: unknown = null;
    let patchedId: number | null = null;
    let deletedId: number | null = null;

    server.use(
      http.post(
        "*/api/v1/accounts/:accountId/publications/sets",
        async ({ request }) => {
          const body = (await request.json()) as {
            name: string;
            content?: string | null;
            media?: unknown[];
            targets: { channel_id: number; settings?: { post_type?: string } }[];
          };
          createdPayload = body;
          const created: PublicationSet = {
            id: 6,
            name: body.name,
            content: body.content ?? null,
            media: [],
            targets: body.targets.map((t) => ({
              channel_id: t.channel_id,
              channel:
                t.channel_id === 10
                  ? IG_CHANNEL
                  : t.channel_id === 20
                    ? THREADS_CHANNEL
                    : null,
              settings: t.settings ?? {},
              content_override: null,
            })),
            created_at: "2026-10-22T10:00:00Z",
            updated_at: "2026-10-22T10:00:00Z",
          };
          setsStore = [...setsStore, created];
          return HttpResponse.json(created, { status: 201 });
        },
      ),
      http.patch(
        "*/api/v1/accounts/:accountId/publications/sets/:id",
        async ({ params, request }) => {
          patchedId = Number(params.id);
          const body = (await request.json()) as {
            name?: string;
            content?: string | null;
            targets?: {
              channel_id: number;
              settings?: { post_type?: string };
            }[];
          };
          patchedPayload = body;
          setsStore = setsStore.map((s) =>
            s.id === patchedId
              ? {
                  ...s,
                  name: body.name ?? s.name,
                  content: body.content !== undefined ? body.content : s.content,
                }
              : s,
          );
          return HttpResponse.json(
            setsStore.find((s) => s.id === patchedId)!,
          );
        },
      ),
      http.delete(
        "*/api/v1/accounts/:accountId/publications/sets/:id",
        ({ params }) => {
          deletedId = Number(params.id);
          setsStore = setsStore.filter((s) => s.id !== deletedId);
          return HttpResponse.json({});
        },
      ),
    );

    renderView();

    expect(
      await screen.findByText("Lanzamiento semanal"),
    ).toBeInTheDocument();
    expect(screen.getByText("Sets (1)")).toBeInTheDocument();
    expect(screen.getByLabelText("Canales: AloStudio IG")).toBeInTheDocument();

    // Open PublicationEditorDialog in set mode
    fireEvent.click(await screen.findByRole("button", { name: "Agregar set" }));
    expect(
      screen.queryByRole("button", { name: "Publicar ahora" }),
    ).not.toBeInTheDocument();

    fireEvent.change(screen.getByLabelText(/nombre del set/i), {
      target: { value: "Set Threads Diario" },
    });
    fireEvent.click(
      screen.getByRole("button", { name: /alostudio threads/i }),
    );
    fireEvent.change(screen.getByLabelText(/^texto$/i), {
      target: { value: "Hilo de todos los días" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Guardar set" }));

    await waitFor(() => {
      expect(createdPayload).toEqual({
        name: "Set Threads Diario",
        content: "Hilo de todos los días",
        media: [],
        targets: [{ channel_id: 20 }],
      });
    });
    expect(
      await screen.findByText("Set Threads Diario"),
    ).toBeInTheDocument();
    expect(screen.getByText("Sets (2)")).toBeInTheDocument();

    // Edit existing set (#5)
    const editButtons = screen.getAllByRole("button", { name: "Editar set" });
    fireEvent.click(editButtons[0]);
    const nameInput = screen.getByLabelText(/nombre del set/i);
    expect(nameInput).toHaveValue("Lanzamiento semanal");
    fireEvent.change(nameInput, {
      target: { value: "Lanzamiento mensual" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Guardar set" }));

    await waitFor(() => {
      expect(patchedId).toBe(5);
      expect(patchedPayload).toMatchObject({
        name: "Lanzamiento mensual",
        content: "Novedades de la semana",
      });
    });
    expect(
      await screen.findByText("Lanzamiento mensual"),
    ).toBeInTheDocument();

    // Delete set (#5)
    const deleteButtons = screen.getAllByRole("button", { name: "Borrar set" });
    fireEvent.click(deleteButtons[0]);

    await waitFor(() => {
      expect(deletedId).toBe(5);
    });
    await waitFor(() => {
      expect(
        screen.queryByText("Lanzamiento mensual"),
      ).not.toBeInTheDocument();
    });
  });

  it("oculta botones de escritura para agentes", async () => {
    currentRole = ROLE_AGENT;
    renderView();

    expect(
      await screen.findByText("Lanzamiento semanal"),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Agregar set" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Editar set" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Borrar set" }),
    ).not.toBeInTheDocument();
  });
});
