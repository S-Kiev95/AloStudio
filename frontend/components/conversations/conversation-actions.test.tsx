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

import { ConversationActions } from "./conversation-actions";

let executeBody: unknown = null;

const server = setupServer(
  http.get("*/agents", () => HttpResponse.json([])),
  http.get("*/labels", () => HttpResponse.json({ payload: [] })),
  http.get("*/macros", () =>
    HttpResponse.json({
      payload: [
        { id: 5, name: "Cerrar y saludar", visibility: "global", actions: [] },
      ],
    }),
  ),
  http.post("*/macros/5/execute", async ({ request }) => {
    executeBody = await request.json();
    return HttpResponse.json({});
  }),
);

beforeAll(() => server.listen({ onUnhandledRequest: "bypass" }));
afterEach(() => {
  server.resetHandlers();
  executeBody = null;
});
afterAll(() => server.close());

function wrap(ui: React.ReactElement) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

describe("ConversationActions macros", () => {
  it("runs the picked macro on the current conversation", async () => {
    wrap(
      <ConversationActions
        accountId="1"
        displayId={42}
        priority={null}
        assigneeId={null}
        labels={[]}
      />,
    );

    const select = await screen.findByLabelText("Correr macro");
    fireEvent.change(select, { target: { value: "5" } });

    await waitFor(() => expect(executeBody).not.toBeNull());
    expect(executeBody).toEqual({ conversation_ids: [42] });
  });
});
