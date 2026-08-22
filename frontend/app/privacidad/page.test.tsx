import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { config as middlewareConfig } from "@/middleware";

import PrivacidadPage from "./page";

describe("Política de privacidad", () => {
  it("responde con la política completa, sin sesión", () => {
    render(<PrivacidadPage />);
    expect(
      screen.getByRole("heading", { level: 1, name: /Política de privacidad/ }),
    ).toBeInTheDocument();
    // Meta lee esta página para validarla; las secciones que le importan
    // son qué datos se tratan, con quién se comparten y cómo se borran.
    for (const titulo of [
      /Qué datos se tratan/,
      /Datos obtenidos a través de Meta/,
      /Con quién se comparten/,
      /Cuánto tiempo se conservan/,
      /Tus derechos/,
    ]) {
      expect(
        screen.getByRole("heading", { level: 2, name: titulo }),
      ).toBeInTheDocument();
    }
  });

  it("ofrece un contacto para ejercer derechos", () => {
    render(<PrivacidadPage />);
    const enlace = screen.getByRole("link", { name: /@/ });
    expect(enlace).toHaveAttribute("href", expect.stringMatching(/^mailto:/));
  });

  it("no queda detrás del guard de sesión", () => {
    // Meta hace un GET anónimo a esta URL para validarla: si el middleware
    // llegara a cubrirla, respondería un 307 al login y Meta rechazaría la
    // app sin decir por qué.
    expect(middlewareConfig.matcher).toEqual(["/accounts/:path*"]);
  });
});
