import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Button } from "./button";

describe("Button", () => {
  it("renders primary as a lit cobalt tube by default", () => {
    render(<Button>Entrar</Button>);
    const btn = screen.getByRole("button", { name: "Entrar" });
    expect(btn).toBeInTheDocument();
    expect(btn.className).toContain("lit-tube-solid");
    expect(btn.className).toContain("h-10");
    expect(btn.className).toContain("rounded-control");
  });

  it("drops the lit tube on secondary, simple, ghost, destructive and ai variants", () => {
    const { rerender } = render(<Button variant="secondary">Cancelar</Button>);
    expect(screen.getByRole("button").className).not.toContain("lit-tube-solid");

    rerender(<Button variant="simple">Utilidad</Button>);
    expect(screen.getByRole("button").className).toContain("bg-btn-simple");

    rerender(<Button variant="destructive">Eliminar</Button>);
    expect(screen.getByRole("button").className).not.toContain("lit-tube-solid");

    rerender(<Button variant="ai">Acción IA</Button>);
    expect(screen.getByRole("button").className).toContain("bg-electrode");
  });

  it("is disabled + busy while loading", () => {
    render(<Button loading>Entrar</Button>);
    const btn = screen.getByRole("button", { name: "Entrar" });
    expect(btn).toBeDisabled();
    expect(btn).toHaveAttribute("aria-busy", "true");
  });
});
