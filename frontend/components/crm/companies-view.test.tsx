import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from "vitest";

import { CompaniesView } from "./companies-view";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));

const company = (id: number, name: string, contacts_count: number, website: string | null) => ({
  id,
  name,
  website,
  email: null,
  phone: null,
  address: null,
  tax_id: null,
  notes: null,
  contacts_count,
  created_at: 1_700_000_000,
});

const server = setupServer(
  http.get("*/crm/companies", () =>
    HttpResponse.json([
      company(1, "Colegio Norte", 2, "colegionorte.edu.uy"),
      company(2, "Estudio Sur", 1, null),
    ]),
  ),
);

beforeAll(() => server.listen({ onUnhandledRequest: "bypass" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe("CompaniesView", () => {
  it("lists companies with their people and links to each", async () => {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={qc}>
        <CompaniesView accountId="1" />
      </QueryClientProvider>,
    );
    const link = await screen.findByRole("link", { name: /Colegio Norte/ });
    expect(link).toHaveAttribute("href", "/accounts/1/companies/1");
    expect(screen.getByText("colegionorte.edu.uy")).toBeInTheDocument();
    expect(screen.getByText("2 personas")).toBeInTheDocument();
    expect(screen.getByText("1 persona")).toBeInTheDocument();
  });
});
