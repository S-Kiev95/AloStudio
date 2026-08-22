import { fireEvent, render, screen } from "@testing-library/react";
import { beforeAll, describe, expect, it, vi } from "vitest";

import { ConnectCapabilitiesDialog } from "./connect-capabilities-dialog";

// jsdom ships <dialog> without showModal/close.
beforeAll(() => {
  HTMLDialogElement.prototype.showModal = function () {
    this.open = true;
  };
  HTMLDialogElement.prototype.close = function () {
    this.open = false;
  };
});

function open(flowId: "facebook" | "instagram", onConfirm = vi.fn()) {
  render(
    <ConnectCapabilitiesDialog
      flowId={flowId}
      open
      onClose={vi.fn()}
      onConfirm={onConfirm}
    />,
  );
  return onConfirm;
}

describe("Qué podés hacer al conectar", () => {
  it("Facebook Login promete mensajes y borrado", () => {
    open("facebook");
    expect(
      screen.getByRole("heading", { name: /Conectar por Facebook Login/ }),
    ).toBeInTheDocument();
    expect(screen.getByText(/Recibir y responder mensajes/)).toBeInTheDocument();
    expect(screen.getByText(/Borrar publicaciones/)).toBeInTheDocument();
    expect(screen.getByText(/Página de Facebook/)).toBeInTheDocument();
  });

  it("Instagram Login dice qué NO va a poder, no sólo qué sí", () => {
    open("instagram");
    // Lo que costó descubrir conectando: los DMs llegan vacíos.
    expect(screen.getByText(/no manda el texto/)).toBeInTheDocument();
    expect(
      screen.getByText(/Meta no ofrece el borrado en esta API/),
    ).toBeInTheDocument();
  });

  it("marca cada punto con una palabra, no sólo con un ícono", () => {
    open("instagram");
    // Un lector de pantalla no ve un check verde.
    expect(screen.getAllByText("Sí:", { exact: false }).length).toBeGreaterThan(0);
    expect(screen.getByText("Limitado:", { exact: false })).toBeInTheDocument();
    expect(screen.getByText("No:", { exact: false })).toBeInTheDocument();
  });

  it("no arranca el OAuth hasta que confirmás", () => {
    const onConfirm = open("facebook");
    expect(onConfirm).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: /Continuar a Meta/ }));
    expect(onConfirm).toHaveBeenCalledWith("facebook");
  });

  it("cancelar no conecta nada", () => {
    const onConfirm = vi.fn();
    const onClose = vi.fn();
    render(
      <ConnectCapabilitiesDialog
        flowId="facebook"
        open
        onClose={onClose}
        onConfirm={onConfirm}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Cancelar" }));
    expect(onClose).toHaveBeenCalled();
    expect(onConfirm).not.toHaveBeenCalled();
  });

  it("sin flujo elegido no renderiza nada", () => {
    const { container } = render(
      <ConnectCapabilitiesDialog
        flowId={null}
        open={false}
        onClose={vi.fn()}
        onConfirm={vi.fn()}
      />,
    );
    expect(container).toBeEmptyDOMElement();
  });
});
