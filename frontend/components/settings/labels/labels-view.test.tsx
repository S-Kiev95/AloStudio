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

import { LabelsView } from "./labels-view";

const labels = [
  {
    id: 1,
    title: "vip",
    description: "Clientes VIP",
    color: "#1f93ff",
    show_on_sidebar: true,
  },
  {
    id: 2,
    title: "spam",
    description: null,
    color: "#e74c3c",
    show_on_sidebar: false,
  },
];

const server = setupServer(
  http.get("*/labels", () => HttpResponse.json({ payload: labels })),
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

describe("LabelsView", () => {
  it("lists labels with description and shows the new-label button", async () => {
    renderWithQuery(<LabelsView accountId="1" />);
    expect(await screen.findByText("vip")).toBeInTheDocument();
    expect(await screen.findByText("spam")).toBeInTheDocument();
    expect(screen.getByText("Clientes VIP")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /Nueva etiqueta/i }),
    ).toBeInTheDocument();
  });
});
