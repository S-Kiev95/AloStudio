import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Button } from "./button";

describe("Button", () => {
  it("renders its children", () => {
    render(<Button>Entrar</Button>);
    expect(
      screen.getByRole("button", { name: "Entrar" }),
    ).toBeInTheDocument();
  });

  it("is disabled + busy while loading", () => {
    render(<Button loading>Entrar</Button>);
    const btn = screen.getByRole("button", { name: "Entrar" });
    expect(btn).toBeDisabled();
    expect(btn).toHaveAttribute("aria-busy", "true");
  });
});
