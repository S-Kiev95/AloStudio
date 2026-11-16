import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";

import { MetaCatalogCard } from "./meta-catalog-card";

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
});
