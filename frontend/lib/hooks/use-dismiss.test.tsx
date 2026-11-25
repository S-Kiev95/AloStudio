import { fireEvent, render, screen } from "@testing-library/react";
import { useRef, useState } from "react";
import { describe, expect, it } from "vitest";

import { useDismissOnOutsideAndEscape } from "./use-dismiss";

function DemoMenu() {
  const [open, setOpen] = useState(false);
  const wrapRef = useRef<HTMLDivElement>(null);
  useDismissOnOutsideAndEscape(wrapRef, open, () => setOpen(false));

  return (
    <div>
      <button type="button">Afuera</button>
      <div ref={wrapRef}>
        <button type="button" onClick={() => setOpen((v) => !v)}>
          Abrir menú
        </button>
        {open ? (
          <div role="menu">
            <button type="button" role="menuitem">
              Opción 1
            </button>
          </div>
        ) : null}
      </div>
    </div>
  );
}

describe("useDismissOnOutsideAndEscape", () => {
  it("cierra el menú al hacer clic afuera y no al hacer clic adentro", () => {
    render(<DemoMenu />);
    fireEvent.click(screen.getByRole("button", { name: "Abrir menú" }));
    expect(screen.getByRole("menu")).toBeInTheDocument();

    fireEvent.mouseDown(screen.getByRole("menuitem", { name: "Opción 1" }));
    expect(screen.getByRole("menu")).toBeInTheDocument();

    fireEvent.mouseDown(screen.getByRole("button", { name: "Afuera" }));
    expect(screen.queryByRole("menu")).not.toBeInTheDocument();
  });

  it("cierra el menú al presionar Escape", () => {
    render(<DemoMenu />);
    fireEvent.click(screen.getByRole("button", { name: "Abrir menú" }));
    expect(screen.getByRole("menu")).toBeInTheDocument();

    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("menu")).not.toBeInTheDocument();
  });
});
