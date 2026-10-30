import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import {
  afterAll,
  afterEach,
  beforeAll,
  beforeEach,
  describe,
  expect,
  it,
  vi,
} from "vitest";

import { ConversationList } from "./conversation-list";
import { ConversationView } from "./conversation-view";
import { InboxChannelsView } from "./inbox-channels-view";
import { InboxReportsView } from "./inbox-reports-view";
import { InboxShell } from "./inbox-shell";
import { InboxTabs } from "./inbox-tabs";

let mockPathname = "/accounts/1/conversations";

vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams(),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  usePathname: () => mockPathname,
}));

const conv42 = {
  id: 42,
  status: "open",
  priority: null,
  unread_count: 1,
  inbox_id: 7,
  labels: ["vip"],
  meta: {
    sender: { id: 101, name: "Camila Pérez" },
    channel: "Channel::Instagram",
    assignee: { id: 9, name: "Agente Ana" },
    team: { id: 3, name: "Ventas" },
  },
  messages: [],
  last_non_activity_message: {
    id: 500,
    content: "Hola, ¿tienen stock?",
    message_type: 0,
    content_type: "text",
    status: "sent",
    created_at: 1_700_000_000,
    private: false,
  },
  timestamp: 1_700_000_000,
  last_activity_at: 1_700_000_000,
  created_at: 1_700_000_000,
};

const conv43 = {
  id: 43,
  status: "open",
  priority: null,
  unread_count: 0,
  inbox_id: 7,
  labels: [],
  meta: {
    sender: { id: 102, name: "Martín Gómez" },
    channel: "Channel::Whatsapp",
    assignee: null,
    team: null,
  },
  messages: [],
  last_non_activity_message: {
    id: 501,
    content: "Gracias por la info",
    message_type: 0,
    content_type: "text",
    status: "sent",
    created_at: 1_700_000_100,
    private: false,
  },
  timestamp: 1_700_000_100,
  last_activity_at: 1_700_000_100,
  created_at: 1_700_000_100,
};

let conversationsListHits = 0;
let currentRole = 1; // ROLE_ADMINISTRATOR

const server = setupServer(
  http.get("*/api/v1/profile", () =>
    HttpResponse.json({
      data: {
        id: 1,
        name: "Zeek",
        email: "zeek@alostudio.test",
        accounts: [{ id: 1, name: "AloStudio", role: currentRole }],
      },
    }),
  ),
  http.get("*/api/v1/accounts/:accountId/conversations", () => {
    conversationsListHits += 1;
    return HttpResponse.json({
      data: {
        meta: {
          mine_count: 1,
          assigned_count: 1,
          unassigned_count: 1,
          all_count: 2,
        },
        payload: [conv42, conv43],
      },
    });
  }),
  http.get("*/api/v1/accounts/:accountId/conversations/42", () =>
    HttpResponse.json(conv42),
  ),
  http.get("*/api/v1/accounts/:accountId/conversations/43", () =>
    HttpResponse.json(conv43),
  ),
  http.get("*/api/v1/accounts/:accountId/conversations/42/messages", () =>
    HttpResponse.json({
      meta: {},
      payload: [
        {
          id: 9001,
          content: "Hola, ¿tienen stock en talle M?",
          message_type: 0,
          content_type: "text",
          status: "sent",
          created_at: 1_700_000_000,
          private: false,
          sender: { id: 101, name: "Camila Pérez", type: "contact" },
        },
      ],
    }),
  ),
  http.get("*/api/v1/accounts/:accountId/conversations/43/messages", () =>
    HttpResponse.json({
      meta: {},
      payload: [
        {
          id: 9002,
          content: "Perfecto, paso mañana por el local",
          message_type: 0,
          content_type: "text",
          status: "sent",
          created_at: 1_700_000_100,
          private: false,
          sender: { id: 102, name: "Martín Gómez", type: "contact" },
        },
      ],
    }),
  ),
  http.get(
    "*/api/v1/accounts/:accountId/conversations/:displayId/participants",
    () => HttpResponse.json([]),
  ),
  http.get("*/api/v1/accounts/:accountId/contacts/101", () =>
    HttpResponse.json({
      payload: {
        id: 101,
        name: "Camila Pérez",
        email: "camila@ejemplo.com",
        phone_number: "+5491122334455",
        custom_attributes: { plan: "Mayorista" },
      },
    }),
  ),
  http.get("*/api/v1/accounts/:accountId/contacts/102", () =>
    HttpResponse.json({
      payload: {
        id: 102,
        name: "Martín Gómez",
        email: "martin@ejemplo.com",
        phone_number: "+5491199887766",
        custom_attributes: {},
      },
    }),
  ),
  http.get("*/api/v1/accounts/:accountId/contacts/:contactId/notes", () =>
    HttpResponse.json([]),
  ),
  http.get("*/api/v1/accounts/:accountId/contacts/:contactId", () =>
    HttpResponse.json({
      payload: {
        id: 0,
        name: "",
        email: null,
        phone_number: null,
        custom_attributes: {},
      },
    }),
  ),
  http.get("*/api/v1/accounts/:accountId/contacts", () =>
    HttpResponse.json({ meta: { count: 28, current_page: 1 }, payload: [] }),
  ),
  http.get("*/api/v1/accounts/:accountId/custom_attribute_definitions", () =>
    HttpResponse.json([]),
  ),
  http.get("*/api/v1/accounts/:accountId/custom_filters", () =>
    HttpResponse.json([]),
  ),
  http.get("*/api/v1/accounts/:accountId/agents", () =>
    HttpResponse.json([
      {
        id: 9,
        name: "Agente Ana",
        email: "ana@alostudio.test",
        availability_status: "online",
      },
    ]),
  ),
  http.get("*/api/v1/accounts/:accountId/teams", () =>
    HttpResponse.json([{ id: 3, name: "Ventas" }]),
  ),
  http.get("*/api/v1/accounts/:accountId/labels", () =>
    HttpResponse.json({ payload: [{ id: 1, title: "vip" }] }),
  ),
  http.get("*/api/v1/accounts/:accountId/macros", () =>
    HttpResponse.json({ payload: [] }),
  ),
  http.get("*/api/v1/accounts/:accountId/inboxes", () =>
    HttpResponse.json({
      payload: [
        {
          id: 7,
          name: "Instagram Oficial",
          channel_type: "Channel::Instagram",
        },
      ],
    }),
  ),
  http.get("*/api/v1/accounts/:accountId/canned_responses", () =>
    HttpResponse.json([]),
  ),
  http.get(
    "*/api/v2/accounts/:accountId/live_reports/conversation_metrics",
    () =>
      HttpResponse.json({ open: 4, unattended: 1, unassigned: 2, pending: 3 }),
  ),
  http.get("*/api/v2/accounts/:accountId/reports/summary", () =>
    HttpResponse.json({
      conversations_count: 12,
      incoming_messages_count: 30,
      outgoing_messages_count: 25,
      avg_first_response_time: 120,
      avg_resolution_time: 900,
      resolutions_count: 9,
    }),
  ),
  http.get("*/api/v2/accounts/:accountId/reports", () =>
    HttpResponse.json([
      { timestamp: 1_700_000_000, value: 6 },
      { timestamp: 1_700_086_400, value: 11 },
    ]),
  ),
);

beforeAll(() => server.listen({ onUnhandledRequest: "bypass" }));
beforeEach(() => {
  conversationsListHits = 0;
  currentRole = 1;
  mockPathname = "/accounts/1/conversations";
});
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe("Bandeja en tres columnas y pestañas", () => {
  it("muestra lista y estado vacío juntos, y cambia entre conversaciones sin recargar la lista", async () => {
    const qc = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });

    mockPathname = "/accounts/1/conversations";
    const { rerender } = render(
      <QueryClientProvider client={qc}>
        <InboxShell list={<ConversationList accountId="1" />}>
          <div className="flex flex-1 items-center justify-center">
            <p>Elegí una conversación para empezar</p>
          </div>
        </InboxShell>
      </QueryClientProvider>,
    );

    expect(
      screen.getByText("Elegí una conversación para empezar"),
    ).toBeInTheDocument();
    expect(await screen.findByText("Camila Pérez")).toBeInTheDocument();
    expect(screen.getByText("Martín Gómez")).toBeInTheDocument();
    // Prove the search input keeps its DOM state across conversation switches (never unmounted!)
    const searchInput = screen.getByPlaceholderText("Buscar conversaciones…");
    expect(conversationsListHits).toBe(1);

    // Open conversation #42: list + conversation + contact panel all render together.
    mockPathname = "/accounts/1/conversations/42";
    rerender(
      <QueryClientProvider client={qc}>
        <InboxShell list={<ConversationList accountId="1" />}>
          <ConversationView accountId="1" displayId={42} />
        </InboxShell>
      </QueryClientProvider>,
    );

    expect(
      await screen.findByText("Hola, ¿tienen stock en talle M?"),
    ).toBeInTheDocument();
    expect(await screen.findByText("camila@ejemplo.com")).toBeInTheDocument();
    expect(screen.getByText("+5491122334455")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Buscar conversaciones…")).toBe(searchInput);

    const activeLink42 = screen
      .getAllByRole("link")
      .find((el) => el.getAttribute("href") === "/accounts/1/conversations/42");
    expect(activeLink42).toHaveAttribute("aria-current", "page");
    expect(conversationsListHits).toBe(1);

    // Switch to conversation #43: updates center + contact panel without reloading the list!
    mockPathname = "/accounts/1/conversations/43";
    rerender(
      <QueryClientProvider client={qc}>
        <InboxShell list={<ConversationList accountId="1" />}>
          <ConversationView accountId="1" displayId={43} />
        </InboxShell>
      </QueryClientProvider>,
    );

    expect(
      await screen.findByText("Perfecto, paso mañana por el local"),
    ).toBeInTheDocument();
    expect(await screen.findByText("martin@ejemplo.com")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Buscar conversaciones…")).toBe(searchInput);

    const activeLink43 = screen
      .getAllByRole("link")
      .find((el) => el.getAttribute("href") === "/accounts/1/conversations/43");
    expect(activeLink43).toHaveAttribute("aria-current", "page");

    // Crucial invariant: the conversation list endpoint was fetched only once!
    expect(conversationsListHits).toBe(1);
  });

  it("renderiza las pestañas Conversaciones, Reportes y Canales sin duplicar Contactos", () => {
    mockPathname = "/accounts/1/conversations/42";
    render(<InboxTabs accountId="1" />);

    expect(
      screen.getByRole("link", { name: "Conversaciones" }),
    ).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: "Reportes" })).toHaveAttribute(
      "href",
      "/accounts/1/conversations/reports",
    );
    expect(screen.getByRole("link", { name: "Canales" })).toHaveAttribute(
      "href",
      "/accounts/1/conversations/channels",
    );
    expect(
      screen.queryByRole("link", { name: /contactos/i }),
    ).not.toBeInTheDocument();
  });

  it("muestra el resumen de reportes de la bandeja y la lista de canales conectados", async () => {
    const qc = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });

    const { unmount } = render(
      <QueryClientProvider client={qc}>
        <InboxReportsView accountId="1" />
      </QueryClientProvider>,
    );

    expect(await screen.findByText("Agente Ana")).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /ver reportes completos/i }),
    ).toHaveAttribute("href", "/accounts/1/reports");
    await waitFor(() => {
      expect(screen.getByText("1/1")).toBeInTheDocument();
    });

    unmount();

    let deletedInboxId: number | null = null;
    server.use(
      http.delete(
        "*/api/v1/accounts/:accountId/inboxes/:inboxId",
        ({ params }) => {
          deletedInboxId = Number(params.inboxId);
          return new HttpResponse(null, { status: 204 });
        },
      ),
    );
    vi.spyOn(window, "confirm").mockReturnValueOnce(true);

    render(
      <QueryClientProvider client={qc}>
        <InboxChannelsView accountId="1" />
      </QueryClientProvider>,
    );

    expect(await screen.findByText("Instagram Oficial")).toBeInTheDocument();
    // Admin-only: shows once the profile says so.
    expect(
      await screen.findByRole("link", { name: /conectar canal/i }),
    ).toHaveAttribute("href", "/accounts/1/settings/inboxes/new");
    expect(
      screen.getByRole("link", { name: /detalles de conexión/i }),
    ).toHaveAttribute("href", "/accounts/1/settings/inboxes/7");

    fireEvent.click(await screen.findByRole("button", { name: "Desconectar" }));
    await waitFor(() => {
      expect(deletedInboxId).toBe(7);
    });
  });

  it("a un agente le muestra los canales sin Conectar ni Desconectar", async () => {
    currentRole = 0; // ROLE_AGENT
    const qc = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });

    render(
      <QueryClientProvider client={qc}>
        <InboxChannelsView accountId="1" />
      </QueryClientProvider>,
    );

    expect(await screen.findByText("Instagram Oficial")).toBeInTheDocument();
    await waitFor(() => {
      expect(qc.getQueryData(["profile"])).toBeTruthy();
    });
    expect(
      screen.getByRole("link", { name: /detalles de conexión/i }),
    ).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /conectar canal/i })).toBeNull();
    expect(screen.queryByRole("button", { name: "Desconectar" })).toBeNull();
  });
});
