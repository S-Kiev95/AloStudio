import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
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
  vi,
} from "vitest";

import {
  AuthSingularityShell,
  BLACK_HOLE_DURATION_MS,
  REDUCED_TRANSITION_MS,
} from "@/components/auth/black-hole-context";

import LoginPage from "./page";

const push = vi.fn();
const refresh = vi.fn();
const prefetch = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, refresh, prefetch }),
}));

vi.mock("@/lib/api/installation", () => ({
  usePublicInstallation: () => ({ data: { multitenant: false, signup_enabled: false } }),
}));

let loginStatus = 200;

const server = setupServer(
  http.get("*/api/auth/google", () => HttpResponse.json({ enabled: false })),
  http.post("*/api/auth/login", () =>
    loginStatus === 200
      ? HttpResponse.json({ accountId: 7 })
      : HttpResponse.json({ error: "Credenciales inválidas" }, { status: loginStatus }),
  ),
);

function mockReducedMotion(matches: boolean) {
  Object.defineProperty(window, "matchMedia", {
    writable: true,
    configurable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      matches: query === "(prefers-reduced-motion: reduce)" ? matches : false,
      media: query,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  });
}

function renderLoginInShell() {
  return render(
    <AuthSingularityShell
      topControls={null}
      background={null}
      wordmark={<span>AloStudio</span>}
    >
      <LoginPage />
    </AuthSingularityShell>,
  );
}

function submitCredentials() {
  fireEvent.change(screen.getByLabelText(/email/i), {
    target: { value: "sofia@ctc.edu.uy" },
  });
  fireEvent.change(screen.getByLabelText(/contraseña/i), {
    target: { value: "secreto123" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Entrar" }));
}

beforeAll(() => server.listen({ onUnhandledRequest: "bypass" }));
beforeEach(() => {
  loginStatus = 200;
  window.history.replaceState(null, "", "/login");
  push.mockClear();
  refresh.mockClear();
  prefetch.mockClear();
  mockReducedMotion(false);
});
afterEach(() => {
  vi.useRealTimers();
  server.resetHandlers();
});
afterAll(() => {
  server.close();
  window.history.replaceState(null, "", "/");
});

describe("LoginPage con agujero negro (Anime.js v4)", () => {
  it("no dispara la animación cuando el login falla", async () => {
    loginStatus = 401;
    const { container } = renderLoginInShell();
    submitCredentials();

    expect(await screen.findByRole("alert")).toHaveTextContent(
      /Credenciales inválidas/i,
    );
    expect(container.querySelector("[data-singularity]")).toHaveAttribute(
      "data-singularity",
      "idle",
    );
    expect(push).not.toHaveBeenCalled();
  });

  it(
    "dispara la secuencia de agujero negro (~5s) solo con login correcto y navega al terminar",
    async () => {
      const { container } = renderLoginInShell();
      submitCredentials();

      await waitFor(() => {
        expect(container.querySelector("[data-singularity]")).toHaveAttribute(
          "data-singularity",
          "active",
        );
      });
      expect(prefetch).toHaveBeenCalledWith("/accounts/7");
      expect(screen.getByRole("status")).toHaveTextContent(
        "Entrando a AloStudio…",
      );
      // Does not jump immediately before the animation finishes.
      expect(push).not.toHaveBeenCalled();

      // Completes in ~5 seconds (BLACK_HOLE_DURATION_MS = 5000ms).
      expect(BLACK_HOLE_DURATION_MS).toBe(5000);

      await waitFor(
        () => {
          expect(push).toHaveBeenCalledWith("/accounts/7");
        },
        { timeout: 6500 },
      );
      expect(refresh).toHaveBeenCalled();
    },
    10000,
  );

  it("reemplaza el agujero negro por una transición simple con prefers-reduced-motion", async () => {
    mockReducedMotion(true);
    const { container } = renderLoginInShell();
    submitCredentials();

    await waitFor(() => {
      expect(container.querySelector("[data-singularity]")).toHaveAttribute(
        "data-singularity",
        "reduced",
      );
    });

    expect(REDUCED_TRANSITION_MS).toBeLessThan(500);
    await waitFor(
      () => {
        expect(push).toHaveBeenCalledWith("/accounts/7");
      },
      { timeout: 1000 },
    );
    expect(refresh).toHaveBeenCalled();
    await act(async () => {});
  });
});
