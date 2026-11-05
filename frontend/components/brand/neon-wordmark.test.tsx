import { act, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { NeonWordmark } from "./neon-wordmark";

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
  vi.useRealTimers();
  vi.restoreAllMocks();
  document.documentElement.className = "";
  Object.defineProperty(document, "hidden", {
    configurable: true,
    value: false,
  });
});

describe("NeonWordmark", () => {
  it("expone 'AloStudio' una sola vez a lectores de pantalla y separa cada letra en su span aria-hidden", () => {
    mockReducedMotion(false);
    render(<NeonWordmark />);

    const byLabel = screen.getAllByLabelText("AloStudio");
    expect(byLabel).toHaveLength(1);
    expect(screen.getByRole("img", { name: "AloStudio" })).toBe(byLabel[0]);

    const letterSpans = byLabel[0].querySelectorAll("span");
    expect(letterSpans).toHaveLength(9);
    expect(Array.from(letterSpans).map((el) => el.textContent)).toEqual([
      "A",
      "l",
      "o",
      "S",
      "t",
      "u",
      "d",
      "i",
      "o",
    ]);
    for (const span of letterSpans) {
      expect(span).toHaveAttribute("aria-hidden", "true");
    }
  });

  it("renderiza como enlace accesible cuando recibe href", () => {
    mockReducedMotion(false);
    render(<NeonWordmark href="/accounts/1" />);

    const link = screen.getByRole("link", { name: "AloStudio" });
    expect(link).toHaveAttribute("href", "/accounts/1");
    expect(link.querySelectorAll("span")).toHaveLength(9);
  });

  it("no programa temporizadores ni ignición con prefers-reduced-motion: reduce", () => {
    vi.useFakeTimers();
    mockReducedMotion(true);

    render(<NeonWordmark />);

    const wordmark = screen.getByLabelText("AloStudio");
    expect(wordmark.className).not.toContain("neon-wordmark-ignite");
    expect(vi.getTimerCount()).toBe(0);
  });

  it("programa encendido y zumbido en modo oscuro, limpia temporizadores al desmontar y respeta document.hidden", () => {
    vi.useFakeTimers();
    mockReducedMotion(false);
    document.documentElement.classList.add("dark");

    const { unmount } = render(<NeonWordmark />);
    const wordmark = screen.getByLabelText("AloStudio");
    expect(wordmark.className).toContain("neon-wordmark-ignite");
    expect(vi.getTimerCount()).toBeGreaterThan(0);

    // Tras ~920 ms termina el encendido inicial y queda solo el temporizador de zumbido
    act(() => {
      vi.advanceTimersByTime(1000);
    });
    expect(wordmark.className).not.toContain("neon-wordmark-ignite");
    expect(vi.getTimerCount()).toBe(1);

    // Con la pestaña oculta se cancelan y no se programan zumbidos
    Object.defineProperty(document, "hidden", {
      configurable: true,
      value: true,
    });
    act(() => {
      document.dispatchEvent(new Event("visibilitychange"));
    });
    expect(vi.getTimerCount()).toBe(0);

    // Al volver a estar visible se vuelve a programar y al desmontar queda en cero
    Object.defineProperty(document, "hidden", {
      configurable: true,
      value: false,
    });
    act(() => {
      document.dispatchEvent(new Event("visibilitychange"));
    });
    expect(vi.getTimerCount()).toBe(1);

    unmount();
    expect(vi.getTimerCount()).toBe(0);
  });
});
