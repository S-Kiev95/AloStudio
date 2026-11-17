import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from "vitest";

import type { ClosingSettings } from "@/lib/api/closing";

import { CloseDialog } from "./close-dialog";

let sent: unknown = null;

const server = setupServer(
  http.post("*/closing_notes/12", async ({ request }) => {
    sent = await request.json();
    return HttpResponse.json({ status: "resolved", ...(sent as object) });
  }),
);

beforeAll(() => {
  // jsdom ships <dialog> without showModal/close.
  HTMLDialogElement.prototype.showModal = function () {
    this.open = true;
  };
  HTMLDialogElement.prototype.close = function () {
    this.open = false;
  };
  server.listen({ onUnhandledRequest: "bypass" });
});
afterEach(() => {
  server.resetHandlers();
  sent = null;
});
afterAll(() => server.close());

function renderDialog(settings: ClosingSettings) {
  const onClose = vi.fn();
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <CloseDialog accountId="1" displayId={12} settings={settings} open onClose={onClose} />
    </QueryClientProvider>,
  );
  return onClose;
}

describe("CloseDialog", () => {
  it("needs a reason when the account requires one, then resolves with it", async () => {
    const onClose = renderDialog({
      enabled: true,
      required: true,
      categories: ["Se inscribió", "Pidió precio"],
    });
    const resolve = screen.getByRole("button", { name: "Resolver" });
    expect(resolve).toBeDisabled();

    fireEvent.click(screen.getByRole("radio", { name: "Se inscribió" }));
    fireEvent.change(screen.getByLabelText("Nota (opcional)"), {
      target: { value: "Arranca en marzo" },
    });
    expect(resolve).toBeEnabled();
    fireEvent.click(resolve);

    await waitFor(() => expect(onClose).toHaveBeenCalled());
    expect(sent).toEqual({ category: "Se inscribió", note: "Arranca en marzo" });
  });

  it("lets it close without a reason when it is optional", async () => {
    const onClose = renderDialog({ enabled: true, required: false, categories: ["Se inscribió"] });
    expect(screen.getByText("El motivo es opcional.")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Resolver" }));
    await waitFor(() => expect(onClose).toHaveBeenCalled());
    expect(sent).toEqual({ category: null, note: null });
  });

  it("says why the server refused", async () => {
    server.use(
      http.post("*/closing_notes/12", () =>
        HttpResponse.json(
          { message: "category", code: "closing.category" },
          { status: 422 },
        ),
      ),
    );
    renderDialog({ enabled: true, required: true, categories: ["Se inscribió"] });
    fireEvent.click(screen.getByRole("radio", { name: "Se inscribió" }));
    fireEvent.click(screen.getByRole("button", { name: "Resolver" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Ese motivo ya no está en la lista. Elegí otro.",
    );
  });
});
