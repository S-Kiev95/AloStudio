import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ConfirmDialogProvider, useConfirm } from "./confirm-dialog";

function Demo({ onResult }: { onResult: (v: boolean) => void }) {
  const confirm = useConfirm();
  return (
    <button
      type="button"
      onClick={async () => {
        const ok = await confirm("¿Eliminar este elemento?");
        onResult(ok);
      }}
    >
      Borrar
    </button>
  );
}

describe("ConfirmDialogProvider y useConfirm", () => {
  it("abre el modal neón con foco en Cancelar y resuelve true al confirmar", async () => {
    const onResult = vi.fn();
    render(
      <ConfirmDialogProvider>
        <Demo onResult={onResult} />
      </ConfirmDialogProvider>,
    );

    fireEvent.click(screen.getByRole("button", { name: "Borrar" }));

    const dialog = await screen.findByRole("alertdialog");
    expect(dialog).toBeInTheDocument();
    expect(screen.getByText("¿Eliminar este elemento?")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Cancelar" })).toHaveFocus();

    fireEvent.click(screen.getByRole("button", { name: "Confirmar" }));
    await waitFor(() => expect(onResult).toHaveBeenCalledWith(true));
    expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
  });

  it("resuelve false al cancelar o presionar Escape", async () => {
    const onResult = vi.fn();
    render(
      <ConfirmDialogProvider>
        <Demo onResult={onResult} />
      </ConfirmDialogProvider>,
    );

    fireEvent.click(screen.getByRole("button", { name: "Borrar" }));
    const dialog = await screen.findByRole("alertdialog");

    fireEvent(dialog, new Event("cancel", { cancelable: true }));
    await waitFor(() => expect(onResult).toHaveBeenCalledWith(false));
    expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
  });
});
