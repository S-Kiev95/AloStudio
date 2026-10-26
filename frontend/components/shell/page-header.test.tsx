import { render, screen } from "@testing-library/react";
import { useState } from "react";
import { describe, expect, it } from "vitest";

import { PageHeader, PageSignContext } from "./page-header";

describe("PageHeader", () => {
  it("renders a neon-sign h1 inline when outside DashboardShell", () => {
    render(
      <PageHeader
        title="Agenda"
        description="Citas programadas"
        actions={<button type="button">Nueva cita</button>}
      />,
    );

    const heading = screen.getByRole("heading", { level: 1, name: "Agenda" });
    expect(heading.parentElement?.className).toContain("neon-sign");
    expect(screen.getByText("Citas programadas")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Nueva cita" })).toBeInTheDocument();
  });

  it("promotes title to the shell topbar sign without duplicating h1", () => {
    function MockShell() {
      const [sign, setSign] = useState<string | null>(null);
      return (
        <PageSignContext.Provider value={{ setSignTitle: setSign }}>
          <header>
            <div className="neon-sign">
              <h1>{sign ?? "Inicio"}</h1>
            </div>
          </header>
          <main>
            <PageHeader
              title="Agenda"
              description="Citas programadas"
              actions={<button type="button">Nueva cita</button>}
            />
          </main>
        </PageSignContext.Provider>
      );
    }

    render(<MockShell />);
    const headings = screen.getAllByRole("heading", { name: "Agenda" });
    expect(headings).toHaveLength(1);
    expect(screen.getByText("Citas programadas")).toBeInTheDocument();
  });
});
