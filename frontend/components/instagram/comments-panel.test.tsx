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

import { CommentsPanel } from "./comments-panel";

const comments = [
  {
    id: 1,
    ig_comment_id: "ig_1",
    parent_comment_id: null,
    from_username: "ana",
    text: "Me encanta este producto",
    hidden: false,
    ig_created_at: "2026-05-01T10:00:00Z",
  },
  {
    id: 2,
    ig_comment_id: "ig_2",
    parent_comment_id: "ig_1",
    from_username: "tienda",
    text: "¡Gracias Ana!",
    hidden: false,
    ig_created_at: "2026-05-01T10:05:00Z",
  },
  {
    id: 3,
    ig_comment_id: "ig_3",
    parent_comment_id: null,
    from_username: "spammer",
    text: "comentario oculto",
    hidden: true,
    ig_created_at: "2026-05-01T11:00:00Z",
  },
];

const server = setupServer(
  http.get("*/comments", () => HttpResponse.json(comments)),
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

describe("CommentsPanel", () => {
  it("renders comments and marks hidden ones", async () => {
    renderWithQuery(
      <CommentsPanel accountId="1" postId={5} enabled={true} />,
    );
    expect(
      await screen.findByText("Me encanta este producto"),
    ).toBeInTheDocument();
    expect(await screen.findByText("¡Gracias Ana!")).toBeInTheDocument();
    expect(await screen.findByText("comentario oculto")).toBeInTheDocument();
    // the hidden comment shows an "Oculto" tag
    expect(screen.getByText("Oculto")).toBeInTheDocument();
  });

  it("does not fetch when disabled (post not published)", () => {
    renderWithQuery(
      <CommentsPanel accountId="1" postId={5} enabled={false} />,
    );
    expect(
      screen.getByText(/estarán disponibles cuando la publicación/i),
    ).toBeInTheDocument();
  });
});
