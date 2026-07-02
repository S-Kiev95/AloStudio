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

import { CannedResponsesView } from "./canned-responses-view";

const responses = [
  { id: 1, short_code: "saludo", content: "Hola, ¿cómo estás?", account_id: 1 },
  { id: 2, short_code: "despedida", content: "¡Buen día!", account_id: 1 },
];

const searches: (string | null)[] = [];

const server = setupServer(
  http.get("*/canned_responses", ({ request }) => {
    searches.push(new URL(request.url).searchParams.get("search"));
    return HttpResponse.json(responses);
  }),
);

beforeAll(() => server.listen({ onUnhandledRequest: "bypass" }));
afterEach(() => {
  server.resetHandlers();
  searches.length = 0;
});
afterAll(() => server.close());

function wrap(ui: React.ReactElement) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

describe("CannedResponsesView", () => {
  it("lists responses with their short codes and content", async () => {
    wrap(<CannedResponsesView accountId="1" />);
    expect(await screen.findByText("/saludo")).toBeInTheDocument();
    expect(screen.getByText("Hola, ¿cómo estás?")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /Nueva respuesta/i }),
    ).toBeInTheDocument();
  });

  it("sends the debounced search term to the backend", async () => {
    wrap(<CannedResponsesView accountId="1" />);
    await waitFor(() => expect(searches).toContain(null));

    fireEvent.change(screen.getByLabelText("Buscar respuestas"), {
      target: { value: "salu" },
    });

    await waitFor(() => expect(searches).toContain("salu"));
  });
});
