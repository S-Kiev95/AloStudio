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
  vi,
} from "vitest";

import type { OAuthApp, OAuthAuthorization } from "@/lib/api/oauth";

import { SettingsSidebar } from "../settings-sidebar";
import { OAuthAppsView } from "./oauth-apps-view";

vi.mock("next/navigation", () => ({
  usePathname: () => "/accounts/1/settings/oauth_apps",
}));

const ADMIN_PROFILE = {
  data: { id: 1, name: "Admin", email: "admin@alostudio.test", accounts: [{ id: 1, name: "Demo", role: 1 }] },
};
const AGENT_PROFILE = {
  data: { id: 2, name: "Agente", email: "agent@alostudio.test", accounts: [{ id: 1, name: "Demo", role: 0 }] },
};

const APP: OAuthApp = {
  id: 3,
  name: "Mi integración",
  client_id: "alo_app_6f1c2b9e8a",
  confidential: true,
  redirect_uris: ["https://example.com/oauth/callback"],
  authorizations_count: 2,
  created_at: "2026-10-30T15:00:00+00:00",
};

const ENDPOINTS = {
  authorization: "https://host/oauth/authorize",
  token: "https://host/oauth/token",
  revocation: "https://host/oauth/revoke",
  metadata: "https://host/.well-known/oauth-authorization-server",
  mcp: "https://host/mcp",
};

const AUTHORIZATION: OAuthAuthorization = {
  app: { id: 3, name: "Mi integración", client_id: "alo_app_6f1c2b9e8a" },
  scope: "write",
  authorized_at: "2026-10-30T15:10:00+00:00",
  last_used_at: null,
};

let profile = ADMIN_PROFILE;
let apps: OAuthApp[] = [];
let authorizations: OAuthAuthorization[] = [];
let appsRequested = false;

const server = setupServer(
  http.get("*/api/v1/profile", () => HttpResponse.json(profile)),
  http.get("*/api/v1/accounts/1/oauth_apps", () => {
    appsRequested = true;
    return HttpResponse.json({ apps, endpoints: ENDPOINTS });
  }),
  http.get("*/api/v1/accounts/1/oauth_authorizations", () =>
    HttpResponse.json({ authorizations }),
  ),
);

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
beforeEach(() => {
  profile = ADMIN_PROFILE;
  apps = [APP];
  authorizations = [AUTHORIZATION];
  appsRequested = false;
  vi.spyOn(window, "confirm").mockReturnValue(true);
});
afterEach(() => {
  server.resetHandlers();
  vi.restoreAllMocks();
});
afterAll(() => server.close());

function renderView() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={qc}>
      <OAuthAppsView accountId="1" />
    </QueryClientProvider>,
  );
}

describe("Ajustes → Apps OAuth", () => {
  it("lista las apps de la cuenta con su client ID, tipo, autorizaciones y la guía de conexión", async () => {
    renderView();
    expect(await screen.findByText("Mi integración")).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Apps" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Apps aprobadas" })).toBeInTheDocument();
    expect(screen.getAllByText("alo_app_6f1c2b9e8a")[0]).toBeInTheDocument();
    expect(screen.getByText("Confidencial")).toBeInTheDocument();
    expect(screen.getByText("2 autorizaciones")).toBeInTheDocument();
    expect(screen.getByText("https://host/oauth/token")).toBeInTheDocument();
    expect(screen.getByText("https://host/mcp")).toBeInTheDocument();
  });

  it("crea una app y muestra el secreto una sola vez", async () => {
    let sent: unknown = null;
    server.use(
      http.post("*/api/v1/accounts/1/oauth_apps", async ({ request }) => {
        sent = await request.json();
        return HttpResponse.json({ ...APP, id: 4, client_id: "alo_app_nueva", client_secret: "alo_secret_unavez" });
      }),
    );
    renderView();
    fireEvent.click(await screen.findByRole("button", { name: "Crear app OAuth" }));
    fireEvent.change(screen.getByLabelText(/Nombre/), { target: { value: "Conector" } });
    fireEvent.change(screen.getByLabelText(/URL de retorno/), {
      target: { value: "https://a.com/cb\n\n  https://b.com/cb  " },
    });
    fireEvent.click(screen.getByRole("button", { name: "Crear app" }));

    expect(await screen.findByText("alo_secret_unavez")).toBeInTheDocument();
    expect(screen.getByText(/no se vuelve a mostrar/)).toBeInTheDocument();
    expect(sent).toEqual({
      name: "Conector",
      redirect_uris: ["https://a.com/cb", "https://b.com/cb"],
      confidential: true,
    });
    fireEvent.click(screen.getByRole("button", { name: "Cerrar" }));
    expect(screen.queryByText("alo_secret_unavez")).not.toBeInTheDocument();
  });

  it("muestra el error del backend junto al formulario", async () => {
    server.use(
      http.post("*/api/v1/accounts/1/oauth_apps", () =>
        HttpResponse.json(
          { message: "http://a.com/cb: tiene que empezar con https://" },
          { status: 422 },
        ),
      ),
    );
    renderView();
    fireEvent.click(await screen.findByRole("button", { name: "Crear app OAuth" }));
    fireEvent.change(screen.getByLabelText(/Nombre/), { target: { value: "X" } });
    fireEvent.change(screen.getByLabelText(/URL de retorno/), { target: { value: "http://a.com/cb" } });
    fireEvent.click(screen.getByRole("button", { name: "Crear app" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("tiene que empezar con https://");
  });

  it("regenera el secreto y borra la app con confirmación", async () => {
    let deleted = false;
    server.use(
      http.post("*/api/v1/accounts/1/oauth_apps/3/secret", () =>
        HttpResponse.json({ ...APP, client_secret: "alo_secret_nuevo" }),
      ),
      http.delete("*/api/v1/accounts/1/oauth_apps/3", () => {
        deleted = true;
        apps = [];
        return HttpResponse.json({});
      }),
    );
    renderView();
    fireEvent.click(await screen.findByRole("button", { name: "Regenerar secreto de Mi integración" }));
    expect(await screen.findByText("alo_secret_nuevo")).toBeInTheDocument();
    expect(window.confirm).toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: "Borrar Mi integración" }));
    await waitFor(() => expect(deleted).toBe(true));
    expect(await screen.findByText("Todavía no registraste ninguna app.")).toBeInTheDocument();
  });

  it("a un agente le muestra solo Apps aprobadas y no pide las apps de la cuenta", async () => {
    profile = AGENT_PROFILE;
    renderView();
    expect(await screen.findByText("Lectura y escritura", { exact: false })).toBeInTheDocument();
    expect(screen.queryByRole("tab", { name: "Apps" })).not.toBeInTheDocument();
    expect(appsRequested).toBe(false);
  });

  it("quita el acceso a una app aprobada", async () => {
    let revoked = false;
    server.use(
      http.delete("*/api/v1/accounts/1/oauth_authorizations/3", () => {
        revoked = true;
        authorizations = [];
        return HttpResponse.json({});
      }),
    );
    renderView();
    fireEvent.click(await screen.findByRole("tab", { name: "Apps aprobadas" }));
    expect(await screen.findByText(/Último uso Nunca/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Quitar acceso" }));
    await waitFor(() => expect(revoked).toBe(true));
    expect(await screen.findByText("No autorizaste ninguna app en esta cuenta.")).toBeInTheDocument();
  });

  it("tiene su entrada en el menú de Ajustes", () => {
    render(<SettingsSidebar accountId="1" />);
    expect(screen.getAllByRole("link", { name: "Apps OAuth" })[0]).toHaveAttribute(
      "href",
      "/accounts/1/settings/oauth_apps",
    );
  });
});
