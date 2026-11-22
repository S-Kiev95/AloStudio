import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, renderHook, screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from "vitest";

import { MetaCatalogCard, useProductCatalogState } from "./meta-catalog-card";

const replace = vi.fn();
let search = "";
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace }),
  usePathname: () => "/accounts/1/products",
  useSearchParams: () => new URLSearchParams(search),
}));

let sent: unknown = null;
const server = setupServer(
  http.put("*/crm/meta-catalog", async ({ request }) => {
    sent = await request.json();
    return HttpResponse.json(
      { message: "Invalid OAuth access token", code: "meta_catalog.token" },
      { status: 422 },
    );
  }),
  http.post("*/crm/meta-catalog/sync", () =>
    HttpResponse.json({
      connected: true,
      catalog_id: "123",
      catalog_name: "Cursos CTC",
      last_sync: { at: 1_794_600_000, validated: true, sent: 3, removed: 0, skipped: 1, failed: 0 },
      result: { sent: 3, removed: 0, skipped: 1, failed: 0 },
    }),
  ),
);

beforeAll(() => server.listen({ onUnhandledRequest: "bypass" }));
afterEach(() => {
  server.resetHandlers();
  sent = null;
  search = "";
  replace.mockClear();
});
afterAll(() => server.close());

function renderCard(catalog: Parameters<typeof MetaCatalogCard>[0]["catalog"]) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <MetaCatalogCard accountId="1" catalog={catalog} />
    </QueryClientProvider>,
  );
}

describe("MetaCatalogCard", () => {
  it("connects with an id and a token, and says why Meta refused", async () => {
    renderCard({ connected: false });
    fireEvent.click(screen.getByRole("button", { name: "Conectar catálogo" }));
    fireEvent.change(screen.getByLabelText("ID del catálogo"), { target: { value: "123" } });
    fireEvent.change(screen.getByLabelText("Token de acceso"), { target: { value: "EAAx" } });
    fireEvent.click(screen.getByRole("button", { name: "Conectar catálogo" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Meta no aceptó el token");
    expect(sent).toEqual({ catalog_id: "123", access_token: "EAAx" });
  });

  it("syncs and reports the outcome", async () => {
    renderCard({ connected: true, catalog_id: "123", catalog_name: "Cursos CTC", last_sync: null });
    expect(screen.getByText("Cursos CTC")).toBeInTheDocument();
    expect(screen.getByText("Todavía no se sincronizó.")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Sincronizar ahora" }));
    expect(await screen.findByRole("status")).toHaveTextContent("3 enviados");
  });

  it("says why the last background sync failed", () => {
    renderCard({
      connected: true,
      catalog_id: "123",
      catalog_name: "Cursos CTC",
      last_sync: null,
      last_error: { code: "token", at: 1_700_000_000 },
    });
    expect(screen.getByRole("alert")).toHaveTextContent(
      "La última sincronización automática falló: Meta no aceptó el token",
    );
  });
});

describe("MetaCatalogCard — connecting with Facebook", () => {
  it("offers Facebook first and keeps pasting the token as the other way", () => {
    renderCard({ connected: false, can_login: true });
    expect(screen.getByRole("button", { name: "Conectar con Facebook" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Pegar ID y token" }));
    expect(screen.getByLabelText("ID del catálogo")).toBeInTheDocument();
  });

  it("hides the Facebook button when the installation can't log in", () => {
    renderCard({ connected: false, can_login: false });
    expect(screen.queryByRole("button", { name: "Conectar con Facebook" })).toBeNull();
    expect(screen.getByRole("button", { name: "Conectar catálogo" })).toBeInTheDocument();
  });

  it("lets the admin pick a catalogue after logging in", async () => {
    search = "catalog_pick=N1";
    let chosen = "";
    server.use(
      http.get("*/crm/meta-catalog/pending/N1", () =>
        HttpResponse.json([
          { id: "555", name: "Cursos", business: "CTC Salto" },
          { id: "666", name: "Tienda", business: "Agencia" },
        ]),
      ),
      http.post("*/crm/meta-catalog/pending/N1/:id", ({ params }) => {
        chosen = String(params.id);
        return HttpResponse.json({
          connected: true,
          can_login: true,
          login: { via: "facebook", expires_at: 1_800_000_000 },
          catalog_id: "666",
          catalog_name: "Tienda",
          last_sync: null,
        });
      }),
    );
    renderCard({ connected: false, can_login: true });
    expect(await screen.findByText("¿Qué catálogo conectás?")).toBeInTheDocument();
    expect(replace).toHaveBeenCalledWith("/accounts/1/products");
    fireEvent.click(await screen.findByRole("button", { name: /Tienda/ }));
    expect(await screen.findByRole("status")).toHaveTextContent("Catálogo conectado.");
    expect(chosen).toBe("666");
  });

  it("says why the connection didn't go through", async () => {
    search = "catalog_error=no_catalogs";
    renderCard({ connected: false, can_login: true });
    expect(screen.getByRole("alert")).toHaveTextContent("Meta no devolvió ningún catálogo");
    await waitFor(() => expect(replace).toHaveBeenCalled());
  });

  it("shows when the Facebook access expires", () => {
    renderCard({
      connected: true,
      can_login: true,
      login: { via: "facebook", expires_at: 1_800_000_000 },
      catalog_id: "555",
      catalog_name: "Cursos CTC",
      last_sync: null,
    });
    expect(screen.getByText(/Conectado con Facebook\. El acceso vence el/)).toBeInTheDocument();
  });
});

describe("useProductCatalogState", () => {
  it("only shows a state for the products chosen for the catalogue", () => {
    const { result } = renderHook(() => useProductCatalogState());
    const state = result.current;
    expect(state({ enabled: true, meta_sync: false, meta_synced_at: 1 })).toBeNull();
    expect(state({ enabled: false, meta_sync: true, meta_synced_at: 1 })).toBeNull();
    expect(state({ enabled: true, meta_sync: true, meta_synced_at: 1 })?.label).toBe("En Meta");
    expect(state({ enabled: true, meta_sync: true, meta_sync_error: "missing:url" })?.label).toBe(
      "No se envía a Meta, falta: enlace",
    );
  });
});
