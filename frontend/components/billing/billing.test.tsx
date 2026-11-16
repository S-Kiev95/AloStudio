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

const CREDITS = {
  balance: 12.5,
  currency: "USD",
  minimum: 5,
  tiers: [
    { from: 100, share: 0.75 },
    { from: 50, share: 0.65 },
    { from: 5, share: 0.5 },
  ],
  purchases: [{ id: 1, paid: 25, credit: 12.5, refunded: false, paid_at: 1_797_000_000 }],
};

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
    http.get("*/api/v1/accounts/1/billing/credits", () => HttpResponse.json(CREDITS)),
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

  it("una prueba cancelada dice cuándo termina, no que se renueva", async () => {
    server.use(
      ...handlers({
        billing: {
          status: "trialing",
          has_access: true,
          plan_name: "Basic",
          current_period_end: 1_797_000_000,
          cancel_at_period_end: true,
        },
      }),
    );
    renderWith(<BillingView accountId="1" />);
    expect(await screen.findByText(/^Termina el/)).toBeVisible();
    expect(screen.queryByText(/La prueba gratis termina/)).toBeNull();
  });

  it("sin acceso no muestra una fecha vieja", async () => {
    server.use(
      ...handlers({
        billing: {
          status: "canceled",
          has_access: false,
          plan_name: "Basic",
          current_period_end: 1_797_000_000,
          cancel_at_period_end: true,
        },
      }),
    );
    renderWith(<BillingView accountId="1" />);
    expect(await screen.findByText("Cancelado")).toBeVisible();
    expect(screen.queryByText(/Termina el|Se renueva/)).toBeNull();
  });

  it("muestra el consumo del mes contra el tope del plan", async () => {
    server.use(
      ...handlers({
        billing: {
          status: "active",
          has_access: true,
          plan_name: "Basic",
          current_period_end: 1_797_000_000,
          cancel_at_period_end: false,
          usage: { cap: 5, spent: 5.5, currency: "USD", credit_balance: 0 },
        },
      }),
    );
    renderWith(<BillingView accountId="1" />);
    expect(await screen.findByText("Consumo de IA del mes")).toBeVisible();
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "100");
    expect(screen.getByRole("alert")).toHaveTextContent(/Llegaste al tope del plan/);
  });
  it("los créditos muestran el saldo, lo que se recibe y el tramo siguiente", async () => {
    server.use(
      ...handlers({
        billing: {
          status: "active",
          has_access: true,
          plan_name: "Basic",
          usage: { cap: 5, spent: 6, currency: "USD", credit_balance: 12.5 },
        },
      }),
    );
    renderWith(<BillingView accountId="1" />);
    expect(await screen.findByText("Créditos de IA")).toBeVisible();
    expect(screen.getByText("Pasaste el tope del plan: la IA sigue con tus créditos.")).toBeVisible();
    const input = await screen.findByLabelText("Monto a cargar (USD)");
    expect(screen.getByText(/Recibís US.{1,3}10,00 de crédito/)).toBeVisible();
    expect(screen.getByText(/Con US.{1,3}50,00 recibís US.{1,3}32,50/)).toBeVisible();
    fireEvent.change(input, { target: { value: "100" } });
    expect(screen.getByText(/Recibís US.{1,3}75,00 de crédito/)).toBeVisible();
    fireEvent.change(input, { target: { value: "3" } });
    expect(screen.getByText(/Mínimo US.{1,3}5,00/)).toBeVisible();
    expect(screen.getByRole("button", { name: "Cargar créditos" })).toBeDisabled();
  });
});
