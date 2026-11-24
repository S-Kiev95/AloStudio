import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Card } from "./card";

describe("Card", () => {
  it("aplica la clase de vidrio esmerilado .glass-card por defecto", () => {
    const { container } = render(<Card>Contenido</Card>);
    const card = container.firstElementChild;
    expect(card).toHaveClass("glass-card", "rounded-md");
    expect(card).not.toHaveClass("glass-card-interactive");
  });

  it("suma la variante interactiva cuando interactive es true", () => {
    const { container } = render(<Card interactive>Click</Card>);
    const card = container.firstElementChild;
    expect(card).toHaveClass("glass-card", "glass-card-interactive");
  });
});
