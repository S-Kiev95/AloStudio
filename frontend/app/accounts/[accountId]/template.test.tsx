import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import AccountTemplate from "./template";

describe("AccountTemplate", () => {
  it("renderiza a sus hijos dentro del contenedor con animación de entrada", () => {
    const { container } = render(
      <AccountTemplate>
        <p>Contenido de la página</p>
      </AccountTemplate>,
    );

    expect(screen.getByText("Contenido de la página")).toBeInTheDocument();
    expect(container.firstElementChild).toHaveClass("page-enter");
  });
});
