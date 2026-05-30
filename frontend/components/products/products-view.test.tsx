import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
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

import { ProductsView } from "./products-view";

const products = [
  {
    id: 1,
    account_id: 1,
    name: "Remera básica",
    description: "Algodón",
    sku: "REM-01",
    price: 590,
    currency: "UYU",
    url: null,
    image_url: null,
    enabled: true,
    created_at: 1_700_000_000,
  },
  {
    id: 2,
    account_id: 1,
    name: "Gorra retro",
    description: null,
    sku: null,
    price: null,
    currency: null,
    url: null,
    image_url: null,
    enabled: false,
    created_at: 1_700_000_000,
  },
];

const server = setupServer(
  http.get("*/products", () => HttpResponse.json(products)),
);

beforeAll(() => server.listen({ onUnhandledRequest: "bypass" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

function renderWithQuery(ui: React.ReactElement) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

describe("ProductsView", () => {
  it("lists products with price and status", async () => {
    renderWithQuery(<ProductsView accountId="1" />);
    expect(await screen.findByText("Remera básica")).toBeInTheDocument();
    expect(await screen.findByText("Gorra retro")).toBeInTheDocument();
    expect(screen.getByText(/590 UYU · SKU REM-01/)).toBeInTheDocument();
    expect(screen.getByText("Activo")).toBeInTheDocument();
    expect(screen.getByText("Inactivo")).toBeInTheDocument();
  });
});
