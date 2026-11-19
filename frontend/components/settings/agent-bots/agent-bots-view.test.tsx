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

import { AgentBotsView } from "./agent-bots-view";

const bots = [
  {
    id: 1,
    name: "Captain Hook",
    description: "Saluda y enruta",
    thumbnail: "",
    outgoing_url: "https://bot.example.com",
    bot_type: "webhook",
    bot_config: {},
    account_id: 1,
    secret: "abc",
    system_bot: false,
  },
  {
    id: 2,
    name: "Csat Bot",
    description: null,
    thumbnail: "",
    bot_type: "webhook",
    bot_config: {},
    account_id: null,
    system_bot: true,
  },
];

let created: Record<string, unknown> | null = null;

const server = setupServer(
  http.get("*/agent_bots", () => HttpResponse.json(bots)),
  http.post("*/agent_bots", async ({ request }) => {
    created = (await request.json()) as Record<string, unknown>;
    return HttpResponse.json({ id: 3, ...created });
  }),
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

describe("AgentBotsView", () => {
  it("lists bots and flags system bots", async () => {
    renderWithQuery(<AgentBotsView accountId="1" />);
    expect(await screen.findByText("Captain Hook")).toBeInTheDocument();
    expect(await screen.findByText("Csat Bot")).toBeInTheDocument();
    expect(screen.getByText("Sistema")).toBeInTheDocument();
    expect(screen.getByText("https://bot.example.com")).toBeInTheDocument();
  });

  it("creates AloStudio's AI with its settings", async () => {
    renderWithQuery(<AgentBotsView accountId="1" />);
    fireEvent.click(await screen.findByRole("button", { name: "Nuevo bot" }));
    fireEvent.change(screen.getByLabelText("Tipo"), { target: { value: "ai" } });
    // No outgoing URL for the AI.
    expect(screen.queryByLabelText("URL de salida")).toBeNull();
    fireEvent.change(screen.getByLabelText(/Nombre/), { target: { value: "Sofi" } });
    fireEvent.change(screen.getByLabelText("Instrucciones"), {
      target: { value: "Vendemos cursos." },
    });
    fireEvent.change(screen.getByLabelText("Modo"), { target: { value: "live" } });
    fireEvent.change(screen.getByLabelText("Cuándo atiende"), {
      target: { value: "out_of_hours" },
    });
    fireEvent.click(screen.getByLabelText("Agendar citas en la Agenda"));
    fireEvent.change(screen.getByLabelText("Duración de cada cita"), { target: { value: "30" } });
    fireEvent.click(screen.getByRole("button", { name: "Crear bot" }));

    await waitFor(() => expect(created).not.toBeNull());
    expect(created).toEqual({
      name: "Sofi",
      description: null,
      bot_type: "ai",
      bot_config: {
        instructions: "Vendemos cursos.",
        mode: "live",
        respond_when: "out_of_hours",
        can_book: true,
        slot_minutes: 30,
        can_update_crm: false,
      },
    });
  });
});
