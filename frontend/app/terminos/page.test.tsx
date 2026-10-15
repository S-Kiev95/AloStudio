import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import TerminosPage from "./page";

describe("Términos del servicio", () => {
  it("responde con los términos completos, sin sesión", () => {
    render(<TerminosPage />);
    expect(
      screen.getByRole("heading", { level: 1, name: /Términos del servicio/ }),
    ).toBeInTheDocument();
    for (const titulo of [/Uso aceptable/, /Ley aplicable/, /Suspensión y baja/]) {
      expect(
        screen.getByRole("heading", { level: 2, name: titulo }),
      ).toBeInTheDocument();
    }
  });

  it("enlaza a la política de privacidad y a la eliminación de datos", () => {
    render(<TerminosPage />);
    expect(
      screen.getByRole("link", { name: /Política de privacidad/ }),
    ).toHaveAttribute("href", "/privacidad");
    expect(
      screen.getByRole("link", { name: /Eliminación de datos/ }),
    ).toHaveAttribute("href", "/eliminacion-de-datos");
  });
});
