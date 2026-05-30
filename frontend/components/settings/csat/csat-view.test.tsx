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

import { CsatView } from "./csat-view";

const metrics = {
  total_count: 8,
  ratings_count: { "5": 5, "4": 2, "3": 0, "2": 0, "1": 1 },
  total_sent_messages_count: 20,
};

const responses = [
  {
    id: 1,
    rating: 5,
    feedback_message: "Excelente atención",
    csat_review_notes: null,
    review_notes_updated_at: null,
    account_id: 1,
    message_id: 100,
    contact: {
      id: 1,
      name: "Carmen",
      email: null,
      phone_number: null,
    },
    conversation_id: 42,
    assigned_agent: { id: 9, name: "Ada" },
    created_at: 1_700_000_000,
  },
  {
    id: 2,
    rating: 1,
    feedback_message: null,
    csat_review_notes: null,
    review_notes_updated_at: null,
    account_id: 1,
    message_id: 101,
    contact: null,
    conversation_id: 43,
    created_at: 1_700_000_000,
  },
];

const server = setupServer(
  http.get("*/csat_survey_responses/metrics", () =>
    HttpResponse.json(metrics),
  ),
  http.get("*/csat_survey_responses", () => HttpResponse.json(responses)),
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

describe("CsatView", () => {
  it("renders metrics cards and responses", async () => {
    renderWithQuery(<CsatView accountId="1" />);
    // Sent / response counts on the cards.
    expect(await screen.findByText("20")).toBeInTheDocument();
    expect(await screen.findByText("8")).toBeInTheDocument();
    // 8/20 = 40%
    expect(screen.getByText("40%")).toBeInTheDocument();
    // Average = (5*5 + 4*2 + 1*1) / 8 = 34/8 = 4.3 (rounded)
    expect(screen.getByText("4.3 / 5")).toBeInTheDocument();
    // Response feedback + fallback anonymous label.
    expect(await screen.findByText("Excelente atención")).toBeInTheDocument();
    expect(screen.getByText("Anónimo")).toBeInTheDocument();
  });
});
