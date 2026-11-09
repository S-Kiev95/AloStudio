import { act, cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import {
  BREATHE_DURATION_MS,
  IGNITE_CLEAR_MS,
  LAST_O_DURATION_MS,
  NeonWordmark,
  NORMAL_DURATION_MS,
  RANDOM_BEAT_DIM_MS,
  RANDOM_BEAT_PEAK_MS,
  RANDOM_BEAT_PULSE_MS,
  SEQUENTIAL_DIM_MS,
  SEQUENTIAL_DURATION_MS,
  SEQUENTIAL_STEP_MS,
} from "./neon-wordmark";

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

  it("repite las cinco escenas en bucle y sin pausas, una sola por vez", () => {
    vi.useFakeTimers();
    mockReducedMotion(false);
    document.documentElement.classList.add("dark");
    // Con Math.random() = 0.5 cada pulso de random-beat enciende 1 letra (0.5 >= 0.25).
    vi.spyOn(Math, "random").mockReturnValue(0.5);

    render(<NeonWordmark />);
    const wordmark = screen.getByLabelText("AloStudio");
    const letters = wordmark.querySelectorAll("span");

    expect(wordmark).not.toHaveAttribute("data-scene");

    // Escena 1: breathe, apenas termina el encendido inicial
    act(() => {
      vi.advanceTimersByTime(IGNITE_CLEAR_MS);
    });
    expect(wordmark).toHaveAttribute("data-scene", "breathe");

    // Escena 2: sequential
    act(() => {
      vi.advanceTimersByTime(BREATHE_DURATION_MS);
    });
    expect(wordmark).toHaveAttribute("data-scene", "sequential");
    for (const span of letters) {
      expect(span).toHaveAttribute("data-tube", "off");
    }

    // Tras 300 ms se enciende la primera letra y el resto sigue apagado
    act(() => {
      vi.advanceTimersByTime(SEQUENTIAL_DIM_MS);
    });
    expect(letters[0]).toHaveAttribute("data-tube", "lit");
    expect(letters[1]).toHaveAttribute("data-tube", "off");

    // Al encenderse las 9 letras hacen el pico de brillo conjunto
    act(() => {
      vi.advanceTimersByTime(9 * SEQUENTIAL_STEP_MS);
    });
    for (const span of letters) {
      expect(span).toHaveAttribute("data-tube", "peak");
    }

    // Escena 3: last-o
    act(() => {
      vi.advanceTimersByTime(
        SEQUENTIAL_DURATION_MS - SEQUENTIAL_DIM_MS - 9 * SEQUENTIAL_STEP_MS,
      );
    });
    expect(wordmark).toHaveAttribute("data-scene", "last-o");

    // Escena 4: random-beat
    act(() => {
      vi.advanceTimersByTime(LAST_O_DURATION_MS);
    });
    expect(wordmark).toHaveAttribute("data-scene", "random-beat");

    // Escena 5: normal, con el cartel encendido entero
    const randomBeatTotalMs =
      RANDOM_BEAT_DIM_MS + 9 * RANDOM_BEAT_PULSE_MS + RANDOM_BEAT_PEAK_MS;
    act(() => {
      vi.advanceTimersByTime(randomBeatTotalMs);
    });
    expect(wordmark).toHaveAttribute("data-scene", "normal");
    for (const span of letters) {
      expect(span).not.toHaveAttribute("data-tube");
    }

    // Y vuelve a empezar: breathe
    act(() => {
      vi.advanceTimersByTime(NORMAL_DURATION_MS);
    });
    expect(wordmark).toHaveAttribute("data-scene", "breathe");
  });

  it("en la escena last-o solo afecta a la última letra y mantiene las otras ocho intactas", () => {
    vi.useFakeTimers();
    mockReducedMotion(false);
    document.documentElement.classList.add("dark");

    render(<NeonWordmark />);
    const wordmark = screen.getByLabelText("AloStudio");
    const letters = Array.from(wordmark.querySelectorAll("span"));

    // Avanzar por escena 1 (breathe) y escena 2 (sequential) hasta llegar a escena 3 (last-o)
    act(() => {
      vi.advanceTimersByTime(IGNITE_CLEAR_MS + BREATHE_DURATION_MS);
    });
    act(() => {
      vi.advanceTimersByTime(SEQUENTIAL_DURATION_MS);
    });

    expect(wordmark).toHaveAttribute("data-scene", "last-o");
    for (let i = 0; i < 8; i += 1) {
      expect(letters[i]).not.toHaveAttribute("data-tube");
    }
    expect(letters[8]).toHaveTextContent("o");
    expect(letters[8]).toHaveAttribute("data-tube", "last-o");

    act(() => {
      vi.advanceTimersByTime(LAST_O_DURATION_MS);
    });
    expect(wordmark).toHaveAttribute("data-scene", "random-beat");
  });

  it("en random-beat enciende cada letra una sola vez sobre un pulso fijo y al final están las nueve", () => {
    vi.useFakeTimers();
    mockReducedMotion(false);
    document.documentElement.classList.add("dark");

    const randomValues = [
      // Pulsos de random-beat (alternando pulsos de 2 letras y de 1 letra en orden aleatorio):
      0.1, // pulso 1: 2 letras (< 0.25)
      0.7, // elige índice de remaining
      0.2, // elige segundo índice de remaining
      0.8, // pulso 2: 1 letra (>= 0.25)
      0.5,
      0.15, // pulso 3: 2 letras (< 0.25)
      0.9,
      0.3,
      0.6, // pulso 4: 1 letra
      0.4,
      0.05, // pulso 5: 2 letras
      0.8,
      0.1,
      0.9, // pulso 6: última letra restante
      0.0,
    ];
    let callIdx = 0;
    vi.spyOn(Math, "random").mockImplementation(() => {
      const value = randomValues[callIdx] ?? 0.5;
      callIdx += 1;
      return value;
    });

    render(<NeonWordmark />);
    const wordmark = screen.getByLabelText("AloStudio");
    const letters = Array.from(wordmark.querySelectorAll("span"));

    // Avanzar hasta el inicio de la 4ª escena (random-beat)
    act(() => {
      vi.advanceTimersByTime(IGNITE_CLEAR_MS + BREATHE_DURATION_MS);
      vi.advanceTimersByTime(SEQUENTIAL_DURATION_MS);
      vi.advanceTimersByTime(LAST_O_DURATION_MS);
    });

    expect(wordmark).toHaveAttribute("data-scene", "random-beat");
    for (const span of letters) {
      expect(span).toHaveAttribute("data-tube", "off");
    }

    const litOrder: number[] = [];
    const seenLit = new Set<number>();

    // Primer pulso tras los 300 ms de apagado inicial
    act(() => {
      vi.advanceTimersByTime(RANDOM_BEAT_DIM_MS);
    });

    for (let safety = 0; safety < 9; safety += 1) {
      const newlyLit: number[] = [];
      letters.forEach((span, idx) => {
        const tube = span.getAttribute("data-tube");
        if (tube === "lit") {
          if (!seenLit.has(idx)) {
            seenLit.add(idx);
            newlyLit.push(idx);
            litOrder.push(idx);
          }
        } else {
          // Ninguna letra que ya se encendió puede volver a apagarse
          expect(seenLit.has(idx)).toBe(false);
          expect(tube).toBe("off");
        }
      });

      expect(newlyLit.length).toBeGreaterThanOrEqual(1);
      expect(newlyLit.length).toBeLessThanOrEqual(2);

      if (seenLit.size === 9) {
        break;
      }

      act(() => {
        vi.advanceTimersByTime(RANDOM_BEAT_PULSE_MS);
      });
    }

    // Se encendieron las 9 letras exactamente una vez y en orden no secuencial
    expect(seenLit.size).toBe(9);
    expect(litOrder).toHaveLength(9);
    expect([...litOrder].sort((a, b) => a - b)).toEqual([
      0, 1, 2, 3, 4, 5, 6, 7, 8,
    ]);
    expect(litOrder).not.toEqual([0, 1, 2, 3, 4, 5, 6, 7, 8]);
    for (const span of letters) {
      expect(span).toHaveAttribute("data-tube", "lit");
    }

    // Último pulso con todo el cartel brillando (peak) y vuelta al brillo normal
    act(() => {
      vi.advanceTimersByTime(RANDOM_BEAT_PULSE_MS);
    });
    for (const span of letters) {
      expect(span).toHaveAttribute("data-tube", "peak");
    }

    act(() => {
      vi.advanceTimersByTime(RANDOM_BEAT_PEAK_MS);
    });
    expect(wordmark).toHaveAttribute("data-scene", "normal");
    for (const span of letters) {
      expect(span).not.toHaveAttribute("data-tube");
    }
  });

  it("no usa temporizadores con prefers-reduced-motion, limpia en pestaña oculta o al desmontar y no corre escenas en tema claro", async () => {
    vi.useFakeTimers();

    // 1. Con prefers-reduced-motion: reduce no hay encendido ni temporizadores
    mockReducedMotion(true);
    document.documentElement.classList.add("dark");
    const reducedRender = render(<NeonWordmark />);
    const reducedWordmark = screen.getByLabelText("AloStudio");
    expect(reducedWordmark.className).not.toContain("neon-wordmark-ignite");
    expect(reducedWordmark).not.toHaveAttribute("data-scene");
    expect(vi.getTimerCount()).toBe(0);
    reducedRender.unmount();

    // 2. En tema claro no hay encendido ni corre ninguna escena
    mockReducedMotion(false);
    document.documentElement.className = "light";
    const lightRender = render(<NeonWordmark />);
    const lightWordmark = screen.getByLabelText("AloStudio");
    expect(lightWordmark.className).not.toContain("neon-wordmark-ignite");
    expect(vi.getTimerCount()).toBe(0);
    act(() => {
      vi.advanceTimersByTime(60_000);
    });
    expect(lightWordmark).not.toHaveAttribute("data-scene");
    lightRender.unmount();

    // 3. En modo oscuro: respeta document.hidden en medio de una escena, cambio a tema claro y desmontaje
    document.documentElement.className = "dark";
    const { unmount } = render(<NeonWordmark />);
    const wordmark = screen.getByLabelText("AloStudio");
    expect(wordmark.className).toContain("neon-wordmark-ignite");

    // Termina el encendido inicial y arranca la escena 1 (breathe)
    act(() => {
      vi.advanceTimersByTime(IGNITE_CLEAR_MS);
    });
    expect(wordmark.className).not.toContain("neon-wordmark-ignite");
    expect(wordmark).toHaveAttribute("data-scene", "breathe");
    expect(vi.getTimerCount()).toBe(1);

    // Si la pestaña se oculta en medio de una escena, vuelve a encendido entero y quedan 0 temporizadores
    Object.defineProperty(document, "hidden", {
      configurable: true,
      value: true,
    });
    act(() => {
      document.dispatchEvent(new Event("visibilitychange"));
    });
    expect(wordmark).not.toHaveAttribute("data-scene");
    expect(vi.getTimerCount()).toBe(0);

    // Al volver a hacerse visible la pestaña, sigue con la escena 2 (sequential, con letras apagadas)
    Object.defineProperty(document, "hidden", {
      configurable: true,
      value: false,
    });
    act(() => {
      document.dispatchEvent(new Event("visibilitychange"));
    });
    expect(wordmark).toHaveAttribute("data-scene", "sequential");

    // Al pasar a tema claro se detiene con el cartel entero
    await act(async () => {
      document.documentElement.className = "light";
      await Promise.resolve();
    });
    expect(wordmark).not.toHaveAttribute("data-scene");
    for (const span of wordmark.querySelectorAll("span")) {
      expect(span).not.toHaveAttribute("data-tube");
    }
    expect(vi.getTimerCount()).toBe(0);

    // Volver a oscuro retoma el bucle y al desmontar queda en cero
    await act(async () => {
      document.documentElement.className = "dark";
      await Promise.resolve();
    });
    expect(wordmark).toHaveAttribute("data-scene", "last-o");
    expect(vi.getTimerCount()).toBe(1);

    unmount();
    expect(vi.getTimerCount()).toBe(0);
  });

  it("en modo colapsado muestra solo la 'A' fija sin encendido ni escenas animadas", () => {
    vi.useFakeTimers();
    mockReducedMotion(false);
    document.documentElement.className = "dark";

    const { rerender } = render(<NeonWordmark collapsed />);
    const wordmark = screen.getByRole("img", { name: "AloStudio" });
    expect(wordmark.className).not.toContain("neon-wordmark-ignite");
    expect(wordmark).not.toHaveAttribute("data-scene");
    expect(vi.getTimerCount()).toBe(0);

    const spans = wordmark.querySelectorAll("span");
    expect(spans).toHaveLength(1);
    expect(spans[0]).toHaveTextContent("A");
    expect(spans[0]).toHaveAttribute("aria-hidden", "true");
    expect(spans[0]).not.toHaveAttribute("data-tube");

    rerender(<NeonWordmark href="/accounts/1" collapsed />);
    const link = screen.getByRole("link", { name: "AloStudio" });
    expect(link.querySelectorAll("span")).toHaveLength(1);
    expect(link).toHaveTextContent("A");
  });
});
