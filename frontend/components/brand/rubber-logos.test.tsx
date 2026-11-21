import { act, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { RubberLogoMargins, RubberLogos } from "./rubber-logos";

class MockResizeObserver {
  static instances: MockResizeObserver[] = [];
  private cb: ResizeObserverCallback;

  constructor(cb: ResizeObserverCallback) {
    this.cb = cb;
    MockResizeObserver.instances.push(this);
  }

  observe() {}
  unobserve() {}
  disconnect() {}

  trigger() {
    this.cb([], this as unknown as ResizeObserver);
  }
}

afterEach(() => {
  MockResizeObserver.instances = [];
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("RubberLogoMargins", () => {
  it("keeps content untouched and does not mount canvases when side margins are below 180px", () => {
    vi.stubGlobal("ResizeObserver", MockResizeObserver);
    vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockImplementation(
      function (this: HTMLElement) {
        // Outer width 1100, centered content 896 -> 94 px per side (< 180 px).
        const isContent = this.className.includes("max-w-4xl");
        const w = isContent ? 896 : 1100;
        return {
          width: w,
          height: 600,
          top: 0,
          left: 0,
          right: w,
          bottom: 600,
          x: 0,
          y: 0,
          toJSON: () => ({}),
        };
      },
    );

    const { container } = render(
      <RubberLogoMargins
        leftLogos={["facebook", "instagram"]}
        rightLogos={["whatsapp", "telegram"]}
        contentClassName="mx-auto max-w-4xl"
      >
        <p>Lista de contactos</p>
      </RubberLogoMargins>,
    );

    expect(screen.getByText("Lista de contactos")).toBeInTheDocument();
    expect(container.querySelectorAll("canvas")).toHaveLength(0);
  });

  it("mounts two decorative aria-hidden strips once each side has at least 180px and removes them when shrunk", () => {
    vi.stubGlobal("ResizeObserver", MockResizeObserver);
    let outerWidth = 1400; // (1400 - 896) / 2 - 8 = 244 px >= 180 px

    vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockImplementation(
      function (this: HTMLElement) {
        const isContent = this.className.includes("max-w-4xl");
        const w = isContent ? 896 : outerWidth;
        return {
          width: w,
          height: 640,
          top: 0,
          left: 0,
          right: w,
          bottom: 640,
          x: 0,
          y: 0,
          toJSON: () => ({}),
        };
      },
    );

    const { container } = render(
      <RubberLogoMargins
        leftLogos={["facebook", "instagram", "whatsapp"]}
        rightLogos={["tiktok", "telegram"]}
        contentClassName="mx-auto max-w-4xl"
      >
        <p>Contenido principal</p>
      </RubberLogoMargins>,
    );

    const canvases = container.querySelectorAll("canvas");
    expect(canvases).toHaveLength(2);
    for (const canvas of canvases) {
      expect(canvas).toHaveAttribute("aria-hidden", "true");
      expect(canvas).toHaveAttribute("tabindex", "-1");
    }

    // Shrink viewport below threshold -> strips unmount cleanly.
    outerWidth = 1120; // (1120 - 896) / 2 - 8 = 104 px < 180 px
    act(() => {
      for (const ro of MockResizeObserver.instances) {
        ro.trigger();
      }
    });

    expect(container.querySelectorAll("canvas")).toHaveLength(0);
    expect(screen.getByText("Contenido principal")).toBeInTheDocument();
  });
});

describe("RubberLogos", () => {
  it("renders a purely decorative canvas outside the focus order", () => {
    const { container } = render(
      <RubberLogos logos={["facebook", "whatsapp"]} side="left" />,
    );
    const canvas = container.querySelector("canvas");
    expect(canvas).not.toBeNull();
    expect(canvas).toHaveAttribute("aria-hidden", "true");
    expect(canvas).toHaveAttribute("tabindex", "-1");
    expect(canvas).toHaveAttribute("data-rubber-strip", "left");
  });
});
