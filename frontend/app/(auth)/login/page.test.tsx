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

import LoginPage from "./page";

const push = vi.fn();
const refresh = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, refresh }),
}));

const server = setupServer(
  http.post("*/api/auth/login", () => HttpResponse.json({ accountId: 7 })),
  http.get("*/api/v1/installation/public", () =>
    HttpResponse.json({ signup_enabled: false, multitenant: false }),
  ),
);

beforeAll(() => server.listen({ onUnhandledRequest: "bypass" }));
beforeEach(() => {
  window.history.replaceState(null, "", "/login");
  push.mockClear();
  refresh.mockClear();
});
afterEach(() => server.resetHandlers());
afterAll(() => {
  server.close();
  window.history.replaceState(null, "", "/");
});

function openLogin(next?: string) {
  window.history.replaceState(
    null,
    "",
    next === undefined ? "/login" : `/login?next=${encodeURIComponent(next)}`,
  );
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={qc}>
      <LoginPage />
    </QueryClientProvider>,
  );
}

function submitValidCredentials() {
  fireEvent.change(screen.getByLabelText(/email/i), {
    target: { value: "zeek@alostudio.test" },
  });
  fireEvent.change(screen.getByLabelText(/contraseña/i), {
    target: { value: "secreto123" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Entrar" }));
}

describe("LoginPage — a dónde va después de entrar", () => {
  it("vuelve a la ruta interna de next con sus parámetros (el consentimiento OAuth)", async () => {
    const target =
      "/oauth/authorize?client_id=alo_app_1&redirect_uri=https%3A%2F%2Fexample.com%2Fcb&scope=write&state=abc";
    openLogin(target);
    submitValidCredentials();

    await waitFor(() => expect(push).toHaveBeenCalledWith(target));
    expect(refresh).toHaveBeenCalled();
  });

  it("ignora un next externo o protocol-relative y va a la cuenta", async () => {
    for (const unsafe of [
      "https://evil.example/phish",
      "//evil.example/phish",
      "/\\evil.example/phish",
    ]) {
      push.mockClear();
      const { unmount } = openLogin(unsafe);
      submitValidCredentials();
      await waitFor(() => expect(push).toHaveBeenCalledWith("/accounts/7"));
      unmount();
    }
  });

  it("va a la cuenta cuando no hay next", async () => {
    openLogin();
    submitValidCredentials();
    await waitFor(() => expect(push).toHaveBeenCalledWith("/accounts/7"));
  });

  it("muestra el link a /registro solo cuando signup_enabled es true", async () => {
    const { unmount } = openLogin();
    expect(
      screen.queryByRole("link", { name: /¿No tenés cuenta\? Creá una/ }),
    ).toBeNull();
    unmount();

    server.use(
      http.get("*/api/v1/installation/public", () =>
        HttpResponse.json({ signup_enabled: true, multitenant: true }),
      ),
    );
    openLogin();
    const link = await screen.findByRole("link", {
      name: "¿No tenés cuenta? Creá una",
    });
    expect(link).toHaveAttribute("href", "/registro");
  });
});
