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

import { ConversationParticipants } from "./conversation-participants";

let postBody: unknown = null;
let deleteBody: unknown = null;

const server = setupServer(
  http.get("*/agents", () =>
    HttpResponse.json([
      { id: 1, name: "Ana" },
      { id: 2, name: "Beto" },
    ]),
  ),
  http.get("*/participants", () => HttpResponse.json([{ id: 1, name: "Ana" }])),
  http.post("*/participants", async ({ request }) => {
    postBody = await request.json();
    return HttpResponse.json([
      { id: 1, name: "Ana" },
      { id: 2, name: "Beto" },
    ]);
  }),
  http.delete("*/participants", async ({ request }) => {
    deleteBody = await request.json();
    return HttpResponse.json({});
  }),
);

beforeAll(() => server.listen({ onUnhandledRequest: "bypass" }));
afterEach(() => {
  server.resetHandlers();
  postBody = null;
  deleteBody = null;
});
afterAll(() => server.close());

function wrap(ui: React.ReactElement) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

describe("ConversationParticipants", () => {
  it("shows current participants and only offers non-participants to add", async () => {
    wrap(<ConversationParticipants accountId="1" displayId={7} />);

    // Current watcher renders as a chip.
    expect(await screen.findByText("Ana")).toBeInTheDocument();

    // The add picker excludes Ana (already a participant) but offers Beto.
    const select = await screen.findByLabelText("Agregar participante");
    const options = [...select.querySelectorAll("option")].map((o) => o.textContent);
    expect(options).toContain("Beto");
    expect(options).not.toContain("Ana");
  });

  it("adds the picked agent as a participant", async () => {
    wrap(<ConversationParticipants accountId="1" displayId={7} />);

    const select = await screen.findByLabelText("Agregar participante");
    fireEvent.change(select, { target: { value: "2" } });

    await waitFor(() => expect(postBody).toEqual({ user_ids: [2] }));
  });

  it("removes a participant via the chip", async () => {
    wrap(<ConversationParticipants accountId="1" displayId={7} />);

    fireEvent.click(await screen.findByLabelText("Quitar Ana"));

    await waitFor(() => expect(deleteBody).toEqual({ user_ids: [1] }));
  });
});
