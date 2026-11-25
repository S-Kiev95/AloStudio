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

import RegistroPage from "./page";

const push = vi.fn();
const refresh = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, refresh }),
}));

const server = setupServer(
  http.get("*/api/v1/installation/public", () =>
    HttpResponse.json({ signup_enabled: true, multitenant: true }),
  ),
);

beforeAll(() => server.listen({ onUnhandledRequest: "bypass" }));
beforeEach(() => {
  window.history.replaceState(null, "", "/registro");
  push.mockClear();
  refresh.mockClear();
});
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

function renderRegistro() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={qc}>
      <RegistroPage />
    </QueryClientProvider>,
  );
}

function fillAndSubmit() {
  fireEvent.change(screen.getByLabelText(/Nombre de la empresa/i), {
    target: { value: "Tienda Sur" },
  });
  fireEvent.change(screen.getByLabelText(/Tu nombre/i), {
    target: { value: "Ana Pérez" },
  });
  fireEvent.change(screen.getByLabelText(/Email/i), {
    target: { value: "ana@tiendasur.test" },
  });
  fireEvent.change(screen.getByLabelText(/Contraseña/i), {
    target: { value: "secreto123" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Crear cuenta" }));
}

describe("RegistroPage", () => {
  it("muestra el aviso de confirmación por correo y permite reenviarlo", async () => {
    let resentTo: string | null = null;
    server.use(
      http.post("*/api/auth/signup", () =>
        HttpResponse.json({ email: "ana@tiendasur.test" }),
      ),
      http.post("*/api/auth/resend-confirmation", async ({ request }) => {
        const body = (await request.json()) as { email: string };
        resentTo = body.email;
        return HttpResponse.json({ ok: true });
      }),
    );

    renderRegistro();
    fillAndSubmit();

    expect(await screen.findByRole("status")).toHaveTextContent(
      "Te mandamos un correo a ana@tiendasur.test. Abrilo para activar tu cuenta",
    );
    expect(push).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: "Reenviar correo" }));
    await waitFor(() => expect(resentTo).toBe("ana@tiendasur.test"));
  });

  it("redirige a la cuenta cuando el backend devuelve sesión (instalación dedicada)", async () => {
    server.use(
      http.post("*/api/auth/signup", () =>
        HttpResponse.json({ ok: true, accountId: 9 }),
      ),
    );

    renderRegistro();
    fillAndSubmit();

    await waitFor(() => expect(push).toHaveBeenCalledWith("/accounts/9"));
    expect(refresh).toHaveBeenCalled();
  });

  it("muestra el message del backend ante un 422 y el aviso de límite ante un 429", async () => {
    server.use(
      http.post("*/api/auth/signup", () =>
        HttpResponse.json(
          { message: "El email ya está registrado." },
          { status: 422 },
        ),
      ),
    );

    renderRegistro();
    fillAndSubmit();

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "El email ya está registrado.",
    );

    server.use(
      http.post("*/api/auth/signup", () =>
        HttpResponse.json({}, { status: 429 }),
      ),
    );
    fireEvent.click(screen.getByRole("button", { name: "Crear cuenta" }));

    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent(
        "Demasiados registros seguidos. Probá más tarde.",
      ),
    );
  });

  it("avisa cuando el registro está cerrado en la instalación", async () => {
    server.use(
      http.get("*/api/v1/installation/public", () =>
        HttpResponse.json({ signup_enabled: false, multitenant: true }),
      ),
    );

    renderRegistro();

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "El registro no está abierto en esta instalación",
    );
    expect(
      screen.getByRole("link", { name: /iniciar sesión/i }),
    ).toHaveAttribute("href", "/login");
  });
});
