import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";

import { BusinessProfileView } from "./business-profile-view";

let sent: unknown = null;
let role = 1;

const server = setupServer(
  http.get("*/api/v1/profile", () =>
    HttpResponse.json({ data: { id: 9, accounts: [{ id: 1, role }] } }),
  ),
  http.get("*/accounts/1/business_profile", () =>
    HttpResponse.json({ text: "CTC Salto: cursos.", max: 8000 }),
  ),
  http.put("*/accounts/1/business_profile", async ({ request }) => {
    sent = await request.json();
    return HttpResponse.json({ ...(sent as object), max: 8000 });
  }),
);

beforeAll(() => server.listen({ onUnhandledRequest: "bypass" }));
afterEach(() => {
  server.resetHandlers();
  sent = null;
  role = 1;
});
afterAll(() => server.close());

function renderView() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <BusinessProfileView accountId="1" />
    </QueryClientProvider>,
  );
}

describe("BusinessProfileView", () => {
  it("lets an administrator describe the business once for every AI", async () => {
    renderView();
    const field = await screen.findByDisplayValue("CTC Salto: cursos.");
    fireEvent.change(field, { target: { value: "CTC Salto: cursos de inglés y Excel." } });
    fireEvent.click(await screen.findByRole("button", { name: "Guardar" }));
    expect(await screen.findByText("Guardado.")).toBeInTheDocument();
    expect(sent).toEqual({ text: "CTC Salto: cursos de inglés y Excel." });
  });

  it("is read-only for agents", async () => {
    role = 0;
    renderView();
    const field = await screen.findByDisplayValue("CTC Salto: cursos.");
    expect(field).toHaveAttribute("readonly");
    expect(screen.queryByRole("button", { name: "Guardar" })).not.toBeInTheDocument();
    expect(screen.getByText("Lo edita un administrador de la cuenta.")).toBeInTheDocument();
  });
});
