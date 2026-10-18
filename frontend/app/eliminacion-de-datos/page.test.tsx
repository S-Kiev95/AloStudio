import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import EliminacionDeDatosPage from "./page";

describe("Eliminación de datos", () => {
  it("explica cómo pedir el borrado, sin sesión", () => {
    render(<EliminacionDeDatosPage />);
    expect(
      screen.getByRole("heading", { level: 1, name: /Eliminación de datos/ }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { level: 2, name: /Qué se elimina/ }),
    ).toBeInTheDocument();
  });

  it("ofrece un correo al que enviar la solicitud", () => {
    render(<EliminacionDeDatosPage />);
    const enlace = screen.getByRole("link", { name: /@/ });
    expect(enlace).toHaveAttribute("href", expect.stringMatching(/^mailto:/));
  });
});
