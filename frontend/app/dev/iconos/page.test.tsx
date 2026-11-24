import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

const notFoundMock = vi.fn(() => {
  throw new Error("NEXT_NOT_FOUND");
});

vi.mock("next/navigation", () => ({
  notFound: () => notFoundMock(),
}));

vi.mock("next-themes", () => ({
  useTheme: () => ({ resolvedTheme: "dark", setTheme: vi.fn() }),
}));

import DevIconsPage from "./page";

afterEach(() => {
  vi.unstubAllEnvs();
  notFoundMock.mockClear();
});

describe("app/dev/iconos — página de muestra solo desarrollo", () => {
  it("devuelve 404 fuera de development", () => {
    vi.stubEnv("NODE_ENV", "production");
    expect(() => DevIconsPage()).toThrow("NEXT_NOT_FOUND");
    expect(notFoundMock).toHaveBeenCalledTimes(1);
  });

  it("renderiza los 18 íconos a 24 px y 48 px con controles de tema en development", () => {
    vi.stubEnv("NODE_ENV", "development");
    const { container } = render(DevIconsPage());

    expect(
      screen.getByRole("heading", { level: 1, name: "Íconos animados" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Oscuro" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Claro" })).toBeInTheDocument();

    const cards = container.querySelectorAll("[data-showcase-icon]");
    expect(cards).toHaveLength(18);
    expect(container.querySelectorAll("svg.h-6.w-6")).toHaveLength(18);
    expect(container.querySelectorAll("svg.h-12.w-12")).toHaveLength(18);

    expect(
      container.querySelector(
        "[data-showcase-icon='hourglass'] svg[data-icon-animate='loop']",
      ),
    ).not.toBeNull();
    expect(
      container.querySelector(
        "[data-showcase-icon='clock'] svg[data-icon-animate='loop']",
      ),
    ).not.toBeNull();
    expect(
      container.querySelector(
        "[data-showcase-icon='inbox'] svg[data-icon-animate='hover']",
      ),
    ).not.toBeNull();
  });
});
