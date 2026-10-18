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

import { AiHandoff } from "./ai-handoff";

let postBody: unknown = null;

const server = setupServer(
  http.post("*/conversations/7/thread_control", async ({ request }) => {
    postBody = await request.json();
    return HttpResponse.json({ id: 7 });
  }),
);

beforeAll(() => server.listen({ onUnhandledRequest: "bypass" }));
afterEach(() => {
  server.resetHandlers();
  postBody = null;
});
afterAll(() => server.close());

function wrap(ui: React.ReactElement) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

describe("AiHandoff", () => {
  it("renders nothing on conversations Meta's AI never touched", () => {
    const { container } = wrap(
      <AiHandoff accountId="1" displayId={7} control={null} />,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("lets the team take a conversation the AI is answering", async () => {
    wrap(
      <AiHandoff accountId="1" displayId={7} control={{ owner: "ai_agent" }} />,
    );
    expect(screen.getByText("Responde la IA de Meta")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Tomar conversación" }));
    await waitFor(() => expect(postBody).toEqual({ action: "take" }));
  });

  it("shows why the AI handed it off and hands it back", async () => {
    wrap(
      <AiHandoff
        accountId="1"
        displayId={7}
        control={{ owner: "app", metadata: "Consulta por pagos" }}
      />,
    );
    expect(screen.getByText("La IA la derivó: Consulta por pagos")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Devolver a la IA" }));
    await waitFor(() => expect(postBody).toEqual({ action: "release" }));
  });

  it("shows Meta's reason when it refuses", async () => {
    server.use(
      http.post("*/conversations/7/thread_control", () =>
        HttpResponse.json(
          { message: "Meta did not hand over the conversation: Not the escalation partner" },
          { status: 502 },
        ),
      ),
    );
    wrap(
      <AiHandoff accountId="1" displayId={7} control={{ owner: "ai_agent" }} />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Tomar conversación" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Not the escalation partner",
    );
  });
});
