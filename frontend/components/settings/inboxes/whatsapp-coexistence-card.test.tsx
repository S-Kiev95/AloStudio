import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { WhatsappCoexistence } from "@/lib/api/inboxes";

import { WhatsappCoexistenceCard } from "./whatsapp-coexistence-card";

const BASE: WhatsappCoexistence = {
  contacts: "done",
  history: "importing",
  progress: 40,
  disconnected: null,
};

describe("WhatsappCoexistenceCard", () => {
  it("muestra el avance de la importación mientras llega", () => {
    render(<WhatsappCoexistenceCard state={BASE} />);
    expect(screen.getByText("WhatsApp en el celular y acá")).toBeInTheDocument();
    expect(screen.getByText("Listos")).toBeInTheDocument();
    expect(screen.getByText("Llegando: 40 %")).toBeInTheDocument();
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "40");
    expect(
      screen.getByText("Dejá la app abierta en el celular hasta que terminen de llegar."),
    ).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("avisa que el número se desconectó y por qué", () => {
    render(
      <WhatsappCoexistenceCard
        state={{
          ...BASE,
          history: "done",
          progress: 100,
          disconnected: {
            event: "PARTNER_REMOVED",
            reason: "PRIMARY_INACTIVITY",
            initiated_by: "SYSTEM",
            at: "2026-11-25T10:00:00+00:00",
          },
        }}
      />,
    );
    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent("El número se desconectó de AloStudio");
    expect(alert).toHaveTextContent("La app del celular estuvo unos 14 días sin abrirse.");
    expect(screen.queryByRole("progressbar")).not.toBeInTheDocument();
  });

  it("explica una desconexión hecha desde la app", () => {
    render(
      <WhatsappCoexistenceCard
        state={{
          ...BASE,
          history: "declined",
          disconnected: { event: "PARTNER_REMOVED", reason: null, initiated_by: "USER", at: null },
        }}
      />,
    );
    expect(screen.getByRole("alert")).toHaveTextContent("Se desconectó desde la app");
    expect(
      screen.getByText("No se compartieron (se eligió no compartirlos en el celular)"),
    ).toBeInTheDocument();
  });
});
