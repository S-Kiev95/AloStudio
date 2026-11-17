import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";

import { ClosingReportCard } from "./closing-report-card";

const server = setupServer(
  http.get("*/closing_notes/settings", () =>
    HttpResponse.json({ enabled: true, required: false, categories: ["Se inscribió"] }),
  ),
  http.get("*/closing_notes/report", () =>
    HttpResponse.json({
      days: 30,
      total: 4,
      categories: [
        { category: "Se inscribió", count: 2 },
        { category: "Pidió precio", count: 1 },
        { category: null, count: 1 },
      ],
    }),
  ),
);

beforeAll(() => server.listen({ onUnhandledRequest: "bypass" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

function renderCard() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <ClosingReportCard accountId="1" days={30} />
    </QueryClientProvider>,
  );
}

describe("ClosingReportCard", () => {
  it("shows how many closed for each reason", async () => {
    renderCard();
    expect(await screen.findByText("Cierres con motivo o nota: 4")).toBeInTheDocument();
    expect(screen.getByText("Se inscribió")).toBeInTheDocument();
    expect(screen.getByText(/2 · 50\s?%/)).toBeInTheDocument();
    expect(screen.getByText("Solo con nota")).toBeInTheDocument();
  });

  it("points to the settings while closing notes are off", async () => {
    server.use(
      http.get("*/closing_notes/settings", () =>
        HttpResponse.json({ enabled: false, required: false, categories: ["Se inscribió"] }),
      ),
      http.get("*/closing_notes/report", () =>
        HttpResponse.json({ days: 30, total: 0, categories: [] }),
      ),
    );
    renderCard();
    expect(await screen.findByRole("link", { name: "Prenderlas en Ajustes" })).toHaveAttribute(
      "href",
      "/accounts/1/settings/closing_notes",
    );
  });
});
