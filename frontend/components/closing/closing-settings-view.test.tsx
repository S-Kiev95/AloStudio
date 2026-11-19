import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";

import { ClosingSettingsView } from "./closing-settings-view";

let saved: unknown = null;

const server = setupServer(
  http.get("*/closing_notes/settings", () =>
    HttpResponse.json({
      enabled: false,
      required: false,
      categories: ["Consulta respondida", "Se inscribió"],
    }),
  ),
  http.put("*/closing_notes/settings", async ({ request }) => {
    saved = await request.json();
    return HttpResponse.json(saved as Record<string, unknown>);
  }),
);

beforeAll(() => server.listen({ onUnhandledRequest: "bypass" }));
afterEach(() => {
  server.resetHandlers();
  saved = null;
});
afterAll(() => server.close());

function renderView() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <ClosingSettingsView accountId="1" />
    </QueryClientProvider>,
  );
}

describe("ClosingSettingsView", () => {
  it("turns closing notes on, edits the reasons and saves", async () => {
    renderView();
    const enabled = await screen.findByRole("checkbox", { name: /Pedir el motivo al resolver/ });
    const required = screen.getByRole("checkbox", { name: /Que el motivo sea obligatorio/ });
    expect(required).toBeDisabled();
    fireEvent.click(enabled);
    fireEvent.click(required);

    fireEvent.change(screen.getByLabelText("Motivo 2"), {
      target: { value: "Se inscribió al curso" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Agregar motivo/ }));
    fireEvent.change(screen.getByLabelText("Motivo 3"), { target: { value: "Pidió precio" } });
    fireEvent.click(screen.getByRole("button", { name: "Quitar Consulta respondida" }));
    fireEvent.click(screen.getByRole("button", { name: "Guardar" }));

    expect(await screen.findByText("Guardado.")).toBeInTheDocument();
    expect(saved).toEqual({
      enabled: true,
      required: true,
      categories: ["Se inscribió al curso", "Pidió precio"],
    });
  });

  it("explains a refusal", async () => {
    server.use(
      http.put("*/closing_notes/settings", () =>
        HttpResponse.json(
          { message: "duplicate_category", code: "closing.duplicate_category" },
          { status: 422 },
        ),
      ),
    );
    renderView();
    await screen.findByRole("checkbox", { name: /Pedir el motivo al resolver/ });
    fireEvent.click(screen.getByRole("button", { name: "Guardar" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Hay dos motivos iguales.");
  });
});
