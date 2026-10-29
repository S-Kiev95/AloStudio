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
import type { Signature } from "@/lib/api/publications";

import { SignaturesView } from "./signatures-view";

let currentRole = ROLE_ADMINISTRATOR;
let signaturesStore: Signature[] = [];

const INITIAL_SIGNATURES: Signature[] = [
  {
    id: 1,
    content: "— Equipo AloStudio",
    auto_add: true,
    created_at: "2026-10-10T10:00:00Z",
    updated_at: "2026-10-10T10:00:00Z",
  },
  {
    id: 2,
    content: "Consultas por WhatsApp al +54 9 11",
    auto_add: false,
    created_at: "2026-10-11T10:00:00Z",
    updated_at: "2026-10-11T10:00:00Z",
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
  http.get("*/api/v1/accounts/:accountId/publications/signatures", () =>
    HttpResponse.json(signaturesStore),
  ),
);

beforeAll(() => server.listen({ onUnhandledRequest: "bypass" }));
beforeEach(() => {
  currentRole = ROLE_ADMINISTRATOR;
  signaturesStore = structuredClone(INITIAL_SIGNATURES);
});
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

function renderView() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={qc}>
      <SignaturesView accountId="1" />
    </QueryClientProvider>,
  );
}

describe("SignaturesView", () => {
  it("lista firmas, crea (cuerpo correcto y conteo de puntos de código), edita y borra", async () => {
    let createdBody: unknown = null;
    let patchedBody: unknown = null;
    let patchedId: number | null = null;
    let deletedId: number | null = null;

    server.use(
      http.post(
        "*/api/v1/accounts/:accountId/publications/signatures",
        async ({ request }) => {
          const body = (await request.json()) as {
            content: string;
            auto_add?: boolean;
          };
          createdBody = body;
          const next: Signature = {
            id: 3,
            content: body.content,
            auto_add: Boolean(body.auto_add),
            created_at: "2026-10-20T12:00:00Z",
            updated_at: "2026-10-20T12:00:00Z",
          };
          if (next.auto_add) {
            signaturesStore = signaturesStore.map((s) => ({
              ...s,
              auto_add: false,
            }));
          }
          signaturesStore = [...signaturesStore, next];
          return HttpResponse.json(next, { status: 201 });
        },
      ),
      http.patch(
        "*/api/v1/accounts/:accountId/publications/signatures/:id",
        async ({ params, request }) => {
          patchedId = Number(params.id);
          const patch = (await request.json()) as {
            content?: string;
            auto_add?: boolean;
          };
          patchedBody = patch;
          signaturesStore = signaturesStore.map((s) =>
            s.id === patchedId
              ? {
                  ...s,
                  content: patch.content ?? s.content,
                  auto_add: patch.auto_add ?? s.auto_add,
                }
              : patch.auto_add
                ? { ...s, auto_add: false }
                : s,
          );
          const updated = signaturesStore.find((s) => s.id === patchedId)!;
          return HttpResponse.json(updated);
        },
      ),
      http.delete(
        "*/api/v1/accounts/:accountId/publications/signatures/:id",
        ({ params }) => {
          deletedId = Number(params.id);
          signaturesStore = signaturesStore.filter((s) => s.id !== deletedId);
          return HttpResponse.json({});
        },
      ),
    );

    renderView();

    expect(await screen.findByText("— Equipo AloStudio")).toBeInTheDocument();
    expect(screen.getByText("Automática")).toBeInTheDocument();
    expect(
      screen.getByText("Consultas por WhatsApp al +54 9 11"),
    ).toBeInTheDocument();

    // Create a signature with an emoji (🔥 = 1 code point, not 2 UTF-16 units)
    fireEvent.click(await screen.findByRole("button", { name: "Agregar firma" }));
    const textarea = screen.getByLabelText(/texto de la firma/i);
    fireEvent.change(textarea, { target: { value: "Hola 🔥" } });
    // "Hola 🔥" has 6 code points (H-o-l-a-space-🔥)
    expect(screen.getByText("6 / 2000")).toBeInTheDocument();

    fireEvent.click(
      screen.getByLabelText("¿Agregar sola a cada publicación nueva?"),
    );
    fireEvent.click(screen.getByRole("button", { name: "Guardar firma" }));

    await waitFor(() => {
      expect(createdBody).toEqual({
        content: "Hola 🔥",
        auto_add: true,
      });
    });
    const list = screen.getByRole("list");
    expect(await within(list).findByText("Hola 🔥")).toBeInTheDocument();

    // Edit second signature
    const editButtons = screen.getAllByRole("button", { name: "Editar firma" });
    fireEvent.click(editButtons[1]);
    const editTextarea = screen.getByLabelText(/texto de la firma/i);
    fireEvent.change(editTextarea, {
      target: { value: "Escribinos por DM" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Guardar cambios" }));

    await waitFor(() => {
      expect(patchedId).toBe(2);
      expect(patchedBody).toEqual({
        content: "Escribinos por DM",
        auto_add: false,
      });
    });
    expect(
      await within(list).findByText("Escribinos por DM"),
    ).toBeInTheDocument();

    // Delete first signature
    const deleteButtons = screen.getAllByRole("button", {
      name: "Borrar firma",
    });
    fireEvent.click(deleteButtons[0]);

    await waitFor(() => {
      expect(deletedId).toBe(1);
    });
    await waitFor(() => {
      expect(
        screen.queryByText("— Equipo AloStudio"),
      ).not.toBeInTheDocument();
    });
  });

  it("muestra errores 422 tal cual y oculta escritura cuando el usuario es agente", async () => {
    server.use(
      http.post("*/api/v1/accounts/:accountId/publications/signatures", () =>
        HttpResponse.json(
          { message: "Ya tenés el máximo de firmas permitidas en la cuenta." },
          { status: 422 },
        ),
      ),
    );

    const { unmount } = renderView();

    fireEvent.click(await screen.findByRole("button", { name: "Agregar firma" }));
    fireEvent.change(screen.getByLabelText(/texto de la firma/i), {
      target: { value: "Nueva firma" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Guardar firma" }));

    expect(
      await screen.findByText(
        "Ya tenés el máximo de firmas permitidas en la cuenta.",
      ),
    ).toBeInTheDocument();

    unmount();

    // Agent role: read-only
    currentRole = ROLE_AGENT;
    renderView();
    expect(await screen.findByText("— Equipo AloStudio")).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Agregar firma" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Editar firma" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Borrar firma" }),
    ).not.toBeInTheDocument();
  });
});
