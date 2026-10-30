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

import type { OAuthConsent as OAuthConsentData } from "@/lib/api/oauth";

import { OAuthConsent } from "./oauth-consent";

const PARAMS = {
  response_type: "code",
  client_id: "alo_app_6f1c2b9e8a",
  redirect_uri: "https://example.com/oauth/callback",
  scope: "write",
  state: "xyz",
  code_challenge: "c".repeat(43),
  code_challenge_method: "S256",
};

let searchParams = new URLSearchParams(PARAMS);

vi.mock("next/navigation", () => ({
  useSearchParams: () => searchParams,
}));

const CONSENT: OAuthConsentData = {
  app: { name: "Mi integración", client_id: PARAMS.client_id, owner_account_name: "Estudio X" },
  scope: "write",
  redirect_uri: PARAMS.redirect_uri,
  accounts: [
    { id: 1, name: "Tienda Salto", role: "administrator", can_grant: true },
    { id: 4, name: "Club", role: "agent", can_grant: false },
  ],
};

let consent: unknown = CONSENT;
let consentStatus = 200;
let submitted: Record<string, unknown> | null = null;

const server = setupServer(
  http.get("*/api/v1/oauth/authorize", () =>
    HttpResponse.json(consent as object, { status: consentStatus }),
  ),
  http.post("*/api/v1/oauth/authorize", async ({ request }) => {
    submitted = (await request.json()) as Record<string, unknown>;
    return HttpResponse.json({
      redirect_to: submitted.approve
        ? `${PARAMS.redirect_uri}?code=alo_code_1&state=xyz`
        : `${PARAMS.redirect_uri}?error=access_denied&state=xyz`,
    });
  }),
);

const original = window.location;
const assign = vi.fn();

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
beforeEach(() => {
  searchParams = new URLSearchParams(PARAMS);
  consent = CONSENT;
  consentStatus = 200;
  submitted = null;
  assign.mockReset();
  // jsdom cannot navigate: a URL (so relative fetches still resolve) with
  // an observable assign.
  Object.defineProperty(window, "location", {
    configurable: true,
    value: Object.assign(new URL("/oauth/authorize", original.href), { assign }),
  });
});
afterEach(() => {
  server.resetHandlers();
  Object.defineProperty(window, "location", { configurable: true, value: original });
});
afterAll(() => server.close());

function renderConsent() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={qc}>
      <OAuthConsent />
    </QueryClientProvider>,
  );
}

describe("Pantalla de consentimiento OAuth", () => {
  it("muestra la app, el permiso y las cuentas, y al autorizar vuelve a la app con el código", async () => {
    renderConsent();
    expect(await screen.findByText("Mi integración")).toBeInTheDocument();
    expect(screen.getByText("Creada por Estudio X")).toBeInTheDocument();
    expect(screen.getByText("Programar y borrar publicaciones")).toBeInTheDocument();
    expect(screen.getByText("Te va a llevar a example.com.", { exact: false })).toBeInTheDocument();
    const club = screen.getByRole("radio", { name: /Club/ });
    expect(club).toBeDisabled();
    expect(screen.getByText("Tu rol en esta cuenta no permite dar este acceso")).toBeInTheDocument();
    // The only account that can grant it comes chosen.
    expect(screen.getByRole("radio", { name: /Tienda Salto/ })).toBeChecked();

    fireEvent.click(screen.getByRole("button", { name: "Autorizar" }));
    await waitFor(() =>
      expect(assign).toHaveBeenCalledWith(`${PARAMS.redirect_uri}?code=alo_code_1&state=xyz`),
    );
    expect(submitted).toEqual({ ...PARAMS, approve: true, account_id: 1 });
  });

  it("al cancelar vuelve a la app con access_denied", async () => {
    renderConsent();
    fireEvent.click(await screen.findByRole("button", { name: "Cancelar" }));
    await waitFor(() =>
      expect(assign).toHaveBeenCalledWith(`${PARAMS.redirect_uri}?error=access_denied&state=xyz`),
    );
    expect(submitted?.approve).toBe(false);
  });

  it("con varias cuentas posibles pide elegir una antes de autorizar", async () => {
    consent = {
      ...CONSENT,
      accounts: [
        { id: 1, name: "Tienda Salto", role: "administrator", can_grant: true },
        { id: 2, name: "Otra", role: "administrator", can_grant: true },
      ],
    };
    renderConsent();
    const authorize = await screen.findByRole("button", { name: "Autorizar" });
    expect(authorize).toBeDisabled();
    fireEvent.click(screen.getByRole("radio", { name: /Otra/ }));
    expect(authorize).toBeEnabled();
  });

  it("con una app o URL de retorno inválida muestra el error y no navega", async () => {
    consent = { message: "La URL de retorno no está registrada para esta app." };
    consentStatus = 400;
    renderConsent();
    expect(await screen.findByRole("alert")).toHaveTextContent("no está registrada");
    expect(screen.getByRole("link", { name: "Volver a AloStudio" })).toHaveAttribute("href", "/accounts");
    expect(assign).not.toHaveBeenCalled();
  });

  it("si el pedido vuelve a la app con un error, navega ahí directamente", async () => {
    consent = { redirect_to: `${PARAMS.redirect_uri}?error=invalid_scope&state=xyz` };
    renderConsent();
    await waitFor(() =>
      expect(assign).toHaveBeenCalledWith(`${PARAMS.redirect_uri}?error=invalid_scope&state=xyz`),
    );
  });
});
