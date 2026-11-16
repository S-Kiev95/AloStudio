import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
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

import { ROLE_ADMINISTRATOR } from "@/lib/api/account";

import { BillingView } from "./billing-view";
import { SubscriptionGate } from "./subscription-gate";

let pathname = "/accounts/1/conversations";
let searchParams = new URLSearchParams();

const notFound = vi.fn();

vi.mock("next/navigation", () => ({
  useSearchParams: () => searchParams,
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  usePathname: () => pathname,
  notFound: () => notFound(),
}));

const PLANS = [
  { id: "p_basic", name: "Basic", description: "Redes de Meta", amount: 10,
    currency: "USD", interval: "month", trial_days: 30 },
  { id: "p_max", name: "Max", description: null, amount: 50,
    currency: "USD", interval: "month", trial_days: null },
];

function handlers({
  multitenant = true,
  billing = { status: "none", has_access: false } as Record<string, unknown>,
  admin = true,
} = {}) {
  return [
    http.get("*/api/v1/installation/public", () =>
      HttpResponse.json({ signup_enabled: true, multitenant }),
    ),
    http.get("*/api/v1/profile", () =>
      HttpResponse.json({
        data: {
          id: 1,
          name: "Admin",
          email: "admin@alostudio.test",
          accounts: [
            { id: 1, name: "AloStudio", role: admin ? ROLE_ADMINISTRATOR : 0 },
          ],
        },
      }),
    ),
    http.get("*/api/v1/accounts/1/billing", () => HttpResponse.json(billing)),
    http.get("*/api/v1/accounts/1/billing/plans", () =>
      HttpResponse.json({ plans: PLANS }),
    ),
  ];
}

const server = setupServer();

beforeAll(() => server.listen({ onUnhandledRequest: "bypass" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
beforeEach(() => {
  pathname = "/accounts/1/conversations";
  searchParams = new URLSearchParams();
});

function renderWith(ui: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

function renderGate() {
  return renderWith(
    <SubscriptionGate accountId="1">
      <p>contenido</p>
    </SubscriptionGate>,
  );
}

describe("SubscriptionGate", () => {
  it("sin plan muestra los planes en lugar de la página", async () => {
    server.use(...handlers());
    renderGate();
    expect(await screen.findByRole("heading", { name: "Elegí un plan" })).toBeVisible();
    expect(await screen.findByText("30 días de prueba gratis")).toBeVisible();
    expect(screen.getByText("Sin prueba gratis")).toBeVisible();
    expect(screen.getByRole("button", { name: "Elegir Basic" })).toBeEnabled();
    expect(screen.queryByText("contenido")).toBeNull();
  });

  it("a un agente le dice que le pida el plan al admin", async () => {
    server.use(...handlers({ admin: false }));
    renderGate();
    expect(await screen.findByText(/Pedile a un administrador/)).toBeVisible();
    expect(screen.queryByRole("button", { name: /Elegir/ })).toBeNull();
  });

  it("con el plan en prueba deja ver la página", async () => {
    server.use(...handlers({ billing: { status: "trialing", has_access: true } }));
    renderGate();
    expect(await screen.findByText("contenido")).toBeVisible();
  });

  it("en una instalación propia no pregunta por el plan", async () => {
    server.use(...handlers({ multitenant: false }));
    renderGate();
    expect(await screen.findByText("contenido")).toBeVisible();
  });

  it("Facturación queda abierta para poder pagar", async () => {
    pathname = "/accounts/1/settings/billing";
    server.use(...handlers());
    renderGate();
    expect(await screen.findByText("contenido")).toBeVisible();
  });
});

describe("BillingView", () => {
  it("muestra el plan, cuándo termina la prueba y el portal", async () => {
    server.use(
      ...handlers({
        billing: {
          status: "trialing",
          has_access: true,
          plan_name: "Pro",
          current_period_end: 1_797_000_000,
          cancel_at_period_end: false,
        },
      }),
    );
    renderWith(<BillingView accountId="1" />);
    expect(await screen.findByText("Pro")).toBeVisible();
    expect(screen.getByText("En prueba gratis")).toBeVisible();
    expect(screen.getByText(/La prueba gratis termina el/)).toBeVisible();
    expect(
      await screen.findByRole("button", { name: "Administrar pago y facturas" }),
    ).toBeVisible();
    expect(screen.queryByRole("heading", { name: "Planes" })).toBeNull();
  });

  it("sin plan ofrece elegir uno y avisa al volver del pago", async () => {
    searchParams = new URLSearchParams({ checkout_id: "chk_1" });
    server.use(...handlers());
    renderWith(<BillingView accountId="1" />);
    expect(await screen.findByRole("status")).toHaveTextContent(/Recibimos el pago/);
    expect(await screen.findByRole("heading", { name: "Planes" })).toBeVisible();
    expect(screen.queryByRole("button", { name: "Administrar pago y facturas" })).toBeNull();
  });

  it("en una instalación propia no existe", async () => {
    notFound.mockClear();
    server.use(...handlers({ multitenant: false }));
    renderWith(<BillingView accountId="1" />);
    await waitFor(() => expect(notFound).toHaveBeenCalled());
  });
});
