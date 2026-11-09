import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import Link from "next/link";
import { afterEach, describe, expect, it, vi } from "vitest";

import AccountTemplate, { resetViewTransitionStateForTests } from "./template";

let mockPathname = "/accounts/1";

vi.mock("next/navigation", () => ({
  usePathname: () => mockPathname,
}));

function mockReducedMotion(matches: boolean) {
  Object.defineProperty(window, "matchMedia", {
    writable: true,
    configurable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      matches: query === "(prefers-reduced-motion: reduce)" ? matches : false,
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  });
}

afterEach(() => {
  cleanup();
  resetViewTransitionStateForTests();
  mockPathname = "/accounts/1";
  Reflect.deleteProperty(document, "startViewTransition");
  vi.restoreAllMocks();
});

describe("AccountTemplate", () => {
  it("renderiza a sus hijos dentro del contenedor con animación de entrada y view-transition", () => {
    const { container } = render(
      <AccountTemplate>
        <p>Contenido de la página</p>
      </AccountTemplate>,
    );

    expect(screen.getByText("Contenido de la página")).toBeInTheDocument();
    expect(container.firstElementChild).toHaveClass("page-enter");
    expect(container.firstElementChild).toHaveClass("vt-page");
  });

  it("ejecuta document.startViewTransition al navegar entre rutas de la cuenta", () => {
    mockReducedMotion(false);
    const startViewTransition = vi.fn((cb: () => Promise<void> | void) => {
      void cb();
      return {};
    });
    Object.defineProperty(document, "startViewTransition", {
      configurable: true,
      writable: true,
      value: startViewTransition,
    });

    const { rerender } = render(
      <AccountTemplate>
        <Link
          href="/accounts/1/publications"
          onClick={(e) => e.preventDefault()}
        >
          Ir a Calendario
        </Link>
      </AccountTemplate>,
    );
    expect(startViewTransition).not.toHaveBeenCalled();

    mockPathname = "/accounts/1/publications";
    rerender(
      <AccountTemplate>
        <p>Calendario</p>
      </AccountTemplate>,
    );
    expect(startViewTransition).toHaveBeenCalledTimes(1);
  });

  it("inicia startViewTransition al hacer click en un enlace interno de la cuenta y no lo ejecuta con prefers-reduced-motion: reduce", () => {
    mockReducedMotion(false);
    const startViewTransition = vi.fn((cb: () => Promise<void> | void) => {
      void cb();
      return {};
    });
    Object.defineProperty(document, "startViewTransition", {
      configurable: true,
      writable: true,
      value: startViewTransition,
    });

    const { rerender } = render(
      <AccountTemplate>
        <Link
          href="/accounts/1/conversations"
          onClick={(e) => {
            // Avoid jsdom full navigation; capture listener runs before this bubble handler.
            e.preventDefault();
          }}
        >
          Bandeja
        </Link>
      </AccountTemplate>,
    );

    fireEvent.click(screen.getByRole("link", { name: "Bandeja" }));
    expect(startViewTransition).toHaveBeenCalledTimes(1);

    mockPathname = "/accounts/1/conversations";
    rerender(
      <AccountTemplate>
        <p>Bandeja</p>
      </AccountTemplate>,
    );

    // Con prefers-reduced-motion: reduce no vuelve a disparar startViewTransition
    mockReducedMotion(true);
    mockPathname = "/accounts/1/reports";
    rerender(
      <AccountTemplate>
        <p>Reportes</p>
      </AccountTemplate>,
    );
    expect(startViewTransition).toHaveBeenCalledTimes(1);
  });
});
