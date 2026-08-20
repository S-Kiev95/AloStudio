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

import { InstagramConnection } from "./instagram-connection";

// Meta redirects the browser to the backend callback, which 303s back here
// with the outcome in the query string. Stub the router hooks so we can
// hand the component that query string.
let searchParams = new URLSearchParams();
const replace = vi.fn();

vi.mock("next/navigation", () => ({
  useSearchParams: () => searchParams,
  useRouter: () => ({ push: vi.fn(), replace }),
  usePathname: () => "/accounts/1/instagram",
}));

const server = setupServer(
  http.get("*/inboxes", () => HttpResponse.json({ payload: [] })),
);

beforeAll(() => server.listen({ onUnhandledRequest: "bypass" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

beforeEach(() => {
  searchParams = new URLSearchParams();
  replace.mockClear();
});

function renderConnection() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <InstagramConnection accountId="1" />
    </QueryClientProvider>,
  );
}

describe("InstagramConnection — vuelta del OAuth", () => {
  it("sin parámetros no muestra ningún cartel", () => {
    renderConnection();
    expect(screen.queryByRole("status")).toBeNull();
    expect(replace).not.toHaveBeenCalled();
  });

  it("nombra la cuenta recién conectada", async () => {
    searchParams = new URLSearchParams({
      ig: "connected",
      ig_login: "instagram",
      ig_user: "s_kiev995",
    });
    renderConnection();
    expect(await screen.findByRole("status")).toHaveTextContent(
      /@s_kiev995 conectada por Instagram Login/,
    );
  });

  it("sin handle dice 'Cuenta' en vez de un arroba vacío", async () => {
    searchParams = new URLSearchParams({ ig: "connected", ig_login: "instagram" });
    renderConnection();
    const banner = await screen.findByRole("status");
    expect(banner).toHaveTextContent(/Cuenta conectada por Instagram Login/);
    expect(banner.textContent).not.toContain("@");
  });

  it("distingue una reconexión de una cuenta nueva", async () => {
    searchParams = new URLSearchParams({
      ig: "reconnected",
      ig_login: "facebook",
      ig_user: "yoruguamaps",
    });
    renderConnection();
    const banner = await screen.findByRole("status");
    expect(banner).toHaveTextContent(/@yoruguamaps reconectada por Facebook Login/);
    expect(banner).toHaveTextContent(/renovó el token/);
  });

  it("muestra el motivo cuando el callback falla", async () => {
    searchParams = new URLSearchParams({
      ig_error: "Esa cuenta ya está conectada en otra cuenta de AloStudio.",
    });
    renderConnection();
    expect(await screen.findByRole("alert")).toHaveTextContent(
      /ya está conectada en otra cuenta/,
    );
  });

  it("limpia la query para que un refresh no repita el cartel", async () => {
    searchParams = new URLSearchParams({ ig: "connected", ig_login: "instagram" });
    renderConnection();
    await waitFor(() =>
      expect(replace).toHaveBeenCalledWith("/accounts/1/instagram", {
        scroll: false,
      }),
    );
    // …pero el cartel sobrevive a esa limpieza.
    expect(screen.getByRole("status")).toBeInTheDocument();
  });
});
