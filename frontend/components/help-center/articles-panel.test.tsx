import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import {
  afterAll,
  afterEach,
  beforeAll,
  describe,
  expect,
  it,
} from "vitest";

import { ArticlesPanel } from "./articles-panel";

const queries: (string | null)[] = [];

const server = setupServer(
  http.get("*/portals/test-portal/articles", ({ request }) => {
    queries.push(new URL(request.url).searchParams.get("query"));
    return HttpResponse.json([]);
  }),
);

beforeAll(() => server.listen({ onUnhandledRequest: "bypass" }));
afterEach(() => {
  server.resetHandlers();
  queries.length = 0;
});
afterAll(() => server.close());

function wrap(ui: React.ReactElement) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

describe("ArticlesPanel search", () => {
  it("sends the debounced query to the articles endpoint", async () => {
    wrap(<ArticlesPanel accountId="1" slug="test-portal" />);

    // Initial load carries no query filter.
    await waitFor(() => expect(queries).toContain(null));

    fireEvent.change(screen.getByLabelText("Buscar artículos"), {
      target: { value: "refund" },
    });

    await waitFor(() => expect(queries).toContain("refund"));
  });

  it("clears the search with the reset button", async () => {
    wrap(<ArticlesPanel accountId="1" slug="test-portal" />);
    const input = screen.getByLabelText("Buscar artículos") as HTMLInputElement;

    fireEvent.change(input, { target: { value: "refund" } });
    await waitFor(() => expect(queries).toContain("refund"));

    fireEvent.click(screen.getByLabelText("Limpiar búsqueda"));
    expect(input.value).toBe("");
  });
});
