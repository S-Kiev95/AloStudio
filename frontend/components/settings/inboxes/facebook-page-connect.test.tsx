import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from "vitest";

import { FacebookPageConnect } from "./facebook-page-connect";

const push = vi.fn();
let search = "";
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
  useSearchParams: () => new URLSearchParams(search),
}));

const BASE = "*/api/v1/accounts/1/facebook_pages";
const server = setupServer();
beforeAll(() => server.listen({ onUnhandledRequest: "bypass" }));
afterEach(() => {
  server.resetHandlers();
  push.mockClear();
  search = "";
});
afterAll(() => server.close());

function renderIt() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <FacebookPageConnect accountId="1" />
    </QueryClientProvider>,
  );
}

describe("FacebookPageConnect", () => {
  it("ofrece conectar y muestra el error de la vuelta de Facebook", async () => {
    search = "fb_error=Se+cancel%C3%B3";
    renderIt();
    expect(await screen.findByRole("alert")).toHaveTextContent("Se canceló");
    expect(screen.getByRole("button", { name: "Conectar con Facebook" })).toBeInTheDocument();
  });

  it("deja elegir entre varias Páginas y abre la bandeja creada", async () => {
    search = "fb_pick=abc";
    server.use(
      http.get(`${BASE}/pending/abc`, () =>
        HttpResponse.json([
          { id: "11", name: "Instituto" },
          { id: "22", name: "Alianza" },
        ]),
      ),
      http.post(`${BASE}/pending/abc/22`, () => HttpResponse.json({ inbox_id: 7 })),
    );
    renderIt();
    fireEvent.click(await screen.findByRole("button", { name: "Alianza" }));
    await waitFor(() =>
      expect(push).toHaveBeenCalledWith("/accounts/1/settings/inboxes/7"),
    );
  });
});
