import { cleanup, render } from "@testing-library/react";
import { useRef } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import {
  animateCounter,
  animateDialogIn,
  animateElectrodeDots,
  animateMessageIn,
  animateMobileDrawerIn,
  animatePopoverIn,
  animateRowIgnite,
  animateStaggerIn,
  animateTabTube,
  prefersReducedMotion,
  useNeonScope,
} from "./neon-motion";

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
  vi.restoreAllMocks();
});

describe("neon-motion helpers (Anime.js v4)", () => {
  it("detecta prefers-reduced-motion y evita animaciones cuando está activo", () => {
    mockReducedMotion(true);
    expect(prefersReducedMotion()).toBe(true);

    const el = document.createElement("div");
    const stopDialog = animateDialogIn(el);
    const stopPopover = animatePopoverIn(el);
    const stopStagger = animateStaggerIn([el]);
    const stopIgnite = animateRowIgnite(el);
    const stopMsg = animateMessageIn(el);
    const stopDots = animateElectrodeDots([el]);
    const stopDrawer = animateMobileDrawerIn(el, el);

    // En modo reducido el contador escribe el valor final de inmediato.
    const counter = document.createElement("span");
    const stopCounter = animateCounter(counter, 42, (n) => String(n));
    expect(counter.textContent).toBe("42");

    // En modo reducido el tubo del tab invoca onComplete inmediatamente.
    const onDone = vi.fn();
    const stopTube = animateTabTube(
      el,
      { left: 0, width: 60 },
      { left: 80, width: 70 },
      onDone,
    );
    expect(onDone).toHaveBeenCalledTimes(1);

    // Limpiar todos los canceladores no arroja errores.
    for (const stop of [
      stopDialog,
      stopPopover,
      stopStagger,
      stopIgnite,
      stopMsg,
      stopDots,
      stopDrawer,
      stopCounter,
      stopTube,
    ]) {
      expect(() => stop()).not.toThrow();
    }
  });

  it("crea y cancela animaciones limpiamente cuando el movimiento está habilitado", () => {
    mockReducedMotion(false);
    expect(prefersReducedMotion()).toBe(false);

    const container = document.createElement("div");
    const child1 = document.createElement("div");
    const child2 = document.createElement("div");
    container.append(child1, child2);
    document.body.appendChild(container);

    const stops = [
      animateDialogIn(child1),
      animatePopoverIn(child1, "up"),
      animateStaggerIn([child1, child2]),
      animateCounter(child1, 15, (n) => `${n}`),
      animateRowIgnite(child1),
      animateMessageIn(child2),
      animateElectrodeDots([child1, child2]),
      animateMobileDrawerIn(child1, child2),
      animateTabTube(
        child1,
        { left: 10, width: 50 },
        { left: 80, width: 60 },
      ),
    ];

    for (const stop of stops) {
      expect(() => stop()).not.toThrow();
    }
    container.remove();
  });

  it("useNeonScope salta setup con prefers-reduced-motion y revierte al desmontar", () => {
    const spy = vi.fn();

    function Demo() {
      const ref = useRef<HTMLDivElement>(null);
      useNeonScope(ref, spy, []);
      return <div ref={ref} />;
    }

    mockReducedMotion(true);
    const reduced = render(<Demo />);
    expect(spy).not.toHaveBeenCalled();
    reduced.unmount();

    mockReducedMotion(false);
    const normal = render(<Demo />);
    expect(spy).toHaveBeenCalledTimes(1);
    expect(() => normal.unmount()).not.toThrow();
  });
});
