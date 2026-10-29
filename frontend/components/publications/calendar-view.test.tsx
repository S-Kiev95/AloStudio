import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
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

import type {
  Channel,
  NetworkOption,
  Publication,
  PublicationState,
} from "@/lib/api/publications";

import { CalendarView } from "./calendar-view";

let searchParams = new URLSearchParams();
const replace = vi.fn();

vi.mock("next/navigation", () => ({
  useSearchParams: () => searchParams,
  useRouter: () => ({ push: vi.fn(), replace }),
  usePathname: () => "/accounts/1/publications",
}));

const ADMIN_PROFILE = {
  data: {
    id: 1,
    name: "Admin",
    email: "admin@alostudio.test",
    accounts: [{ id: 1, name: "Demo", role: 1 }],
  },
};

const IG_CHANNEL: Channel = {
  id: 7,
  network: "instagram",
  name: "Tienda Oficial",
  username: "tienda_oficial",
  avatar_url: null,
  status: "active",
  status_message: null,
  inbox_id: 2,
};

const THREADS_CHANNEL: Channel = {
  id: 8,
  network: "threads",
  name: "Tienda Threads",
  username: "tienda_th",
  avatar_url: null,
  status: "active",
  status_message: null,
  inbox_id: null,
};

const NETWORKS: NetworkOption[] = [
  {
    network: "threads",
    label: "Threads",
    configured: true,
    kind: "authorize",
    fields: [],
  },
  {
    network: "telegram",
    label: "Telegram",
    configured: true,
    kind: "form",
    fields: [
      {
        name: "bot_token",
        label: "Token del bot",
        help: "Crealo con @BotFather.",
        secret: true,
      },
      {
        name: "chat_id",
        label: "Canal o chat",
        help: "Ej: @micanal",
        secret: false,
      },
    ],
  },
  {
    network: "discord",
    label: "Discord",
    configured: false,
    kind: "form",
    fields: [],
  },
];

function makePublication({
  id,
  content,
  localDate,
  state,
}: {
  id: number;
  content: string;
  localDate: Date;
  state: PublicationState;
}): Publication {
  const iso = localDate.toISOString();
  return {
    id,
    account_id: 1,
    content,
    media: [],
    scheduled_for: state === "draft" ? null : iso,
    state,
    created_by_id: 1,
    published_at: state === "published" ? iso : null,
    created_at: iso,
    updated_at: iso,
    targets: [
      {
        id: id * 10,
        channel: IG_CHANNEL,
        settings: { post_type: "feed" },
        content_override: null,
        state: state === "published" ? "published" : "pending",
        external_id: null,
        permalink: null,
        error_code: null,
        error_message: null,
        attempts: 0,
        published_at: null,
        metrics: {},
        metrics_updated_at: null,
        metrics_error: null,
      },
    ],
  };
}

const server = setupServer(
  http.get("*/api/v1/profile", () => HttpResponse.json(ADMIN_PROFILE)),
  http.get("*/api/v1/accounts/1/publications/channels", () =>
    HttpResponse.json([IG_CHANNEL, THREADS_CHANNEL]),
  ),
  http.get("*/api/v1/accounts/1/publications/networks", () =>
    HttpResponse.json(NETWORKS),
  ),
  http.get("*/api/v1/accounts/1/publications", () => HttpResponse.json([])),
);

const originalLocation = window.location;

beforeAll(() => {
  server.listen({ onUnhandledRequest: "bypass" });
  HTMLDialogElement.prototype.showModal = function () {
    this.open = true;
  };
  HTMLDialogElement.prototype.close = function () {
    this.open = false;
  };
});

beforeEach(() => {
  searchParams = new URLSearchParams();
  replace.mockClear();
  Object.defineProperty(window, "location", {
    configurable: true,
    writable: true,
    value: {
      ...originalLocation,
      origin: originalLocation.origin || "http://localhost:3000",
      href: "http://localhost:3000/accounts/1/publications",
    },
  });
});

afterEach(() => {
  server.resetHandlers();
  vi.restoreAllMocks();
});

afterAll(() => {
  Object.defineProperty(window, "location", {
    configurable: true,
    writable: true,
    value: originalLocation,
  });
  server.close();
});

const FIXED_NOW = new Date(2026, 9, 28, 14, 30, 0, 0); // Wed Oct 28, 2026 local

function renderCalendar() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={qc}>
      <CalendarView accountId="1" now={FIXED_NOW} />
    </QueryClientProvider>,
  );
}

describe("CalendarView — grilla, paginación y estados", () => {
  it("ubica cada publicación en su día y hora local, pide todas las páginas del rango y pinta el estado", async () => {
    const requestedPages: number[] = [];

    // Page 1 returns 50 items (full page -> triggers page 2)
    const page1: Publication[] = Array.from({ length: 50 }, (_, idx) =>
      makePublication({
        id: idx + 1,
        content: idx === 0 ? "Post lunes nueve AM" : `Relleno #${idx + 1}`,
        localDate:
          idx === 0
            ? new Date(2026, 9, 26, 9, 15, 0) // Mon Oct 26, 09:15 local
            : new Date(2026, 9, 27, 11, 0, 0),
        state: idx === 0 ? "scheduled" : "published",
      }),
    );

    // Page 2 returns 2 items (< 50 -> stops pagination)
    const page2: Publication[] = [
      makePublication({
        id: 51,
        content: "Borrador jueves tarde",
        localDate: new Date(2026, 9, 29, 16, 40, 0), // Thu Oct 29, 16:40 local
        state: "draft",
      }),
      makePublication({
        id: 52,
        content: "Post viernes fallido",
        localDate: new Date(2026, 9, 30, 19, 5, 0), // Fri Oct 30, 19:05 local
        state: "failed",
      }),
    ];

    server.use(
      http.get("*/api/v1/accounts/1/publications", ({ request }) => {
        const url = new URL(request.url);
        const page = Number(url.searchParams.get("page") ?? "1");
        requestedPages.push(page);
        return HttpResponse.json(page === 1 ? page1 : page2);
      }),
    );

    renderCalendar();

    // Wait for items from both page 1 and page 2 to appear
    expect(await screen.findByText("Post lunes nueve AM")).toBeInTheDocument();
    expect(screen.getByText("Borrador jueves tarde")).toBeInTheDocument();
    expect(screen.getByText("Post viernes fallido")).toBeInTheDocument();

    // Requested page 1 and page 2, then stopped
    expect(requestedPages).toEqual([1, 2]);

    // Check exact local day + hour slots and state badges
    const monday9Slot = screen.getByTestId("slot-2026-10-26-9");
    expect(
      within(monday9Slot).getByText("Post lunes nueve AM"),
    ).toBeInTheDocument();
    expect(within(monday9Slot).getByText("Programada")).toBeInTheDocument();

    const thursday16Slot = screen.getByTestId("slot-2026-10-29-16");
    expect(
      within(thursday16Slot).getByText("Borrador jueves tarde"),
    ).toBeInTheDocument();
    expect(within(thursday16Slot).getByText("Borrador")).toBeInTheDocument();

    const friday19Slot = screen.getByTestId("slot-2026-10-30-19");
    expect(
      within(friday19Slot).getByText("Post viernes fallido"),
    ).toBeInTheDocument();
    expect(within(friday19Slot).getByText("Falló")).toBeInTheDocument();
  });
});

describe("CalendarView — conexión de canales y avisos de query", () => {
  it("'Agregar canal' con una red authorize pide authorize_url sin cuerpo y navega a ella", async () => {
    let rawBody = "unset";
    server.use(
      http.post(
        "*/api/v1/accounts/1/publications/channels/connect/threads",
        async ({ request }) => {
          rawBody = await request.text();
          return HttpResponse.json({
            authorize_url: "https://threads.net/oauth/authorize?state=xyz",
          });
        },
      ),
    );

    renderCalendar();

    const addBtn = await screen.findByRole("button", { name: /Agregar canal/i });
    fireEvent.click(addBtn);

    // Unconfigured network is disabled with installation notice
    const discordItem = await screen.findByRole("menuitem", {
      name: /Discord/i,
    });
    expect(discordItem).toBeDisabled();
    expect(discordItem).toHaveTextContent(
      /Falta configurar en Ajustes → Instalación/,
    );

    // Click Threads (kind: "authorize")
    fireEvent.click(screen.getByRole("menuitem", { name: /Threads/i }));

    await waitFor(() =>
      expect(window.location.href).toBe(
        "https://threads.net/oauth/authorize?state=xyz",
      ),
    );
    expect(rawBody).toBe("");
  });

  it("'Agregar canal' con una red form abre el diálogo, envía { fields } y muestra el 422 sin cerrarlo", async () => {
    let receivedPayload: unknown = null;
    server.use(
      http.post(
        "*/api/v1/accounts/1/publications/channels/connect/telegram",
        async ({ request }) => {
          receivedPayload = await request.json();
          return HttpResponse.json(
            { message: "El bot no tiene permisos de publicación en ese canal." },
            { status: 422 },
          );
        },
      ),
    );

    renderCalendar();

    fireEvent.click(
      await screen.findByRole("button", { name: /Agregar canal/i }),
    );
    fireEvent.click(
      await screen.findByRole("menuitem", { name: /Telegram/i }),
    );

    const dialog = await screen.findByRole("dialog", {
      name: /Conectar Telegram/i,
    });

    const tokenInput = within(dialog).getByLabelText(/Token del bot/i);
    expect(tokenInput).toHaveAttribute("type", "password");
    fireEvent.change(tokenInput, { target: { value: "999:SECRET_TOKEN" } });
    fireEvent.change(within(dialog).getByLabelText(/Canal o chat/i), {
      target: { value: "@alostudio_news" },
    });

    fireEvent.click(within(dialog).getByRole("button", { name: "Conectar" }));

    await waitFor(() =>
      expect(receivedPayload).toEqual({
        fields: {
          bot_token: "999:SECRET_TOKEN",
          chat_id: "@alostudio_news",
        },
      }),
    );

    // 422 message appears inside the dialog and the dialog stays open
    expect(await within(dialog).findByRole("alert")).toHaveTextContent(
      "El bot no tiene permisos de publicación en ese canal.",
    );
    expect(dialog).toHaveAttribute("open");
  });

  it("muestra el aviso de ?connected y limpia la query con router.replace", async () => {
    searchParams = new URLSearchParams({
      connected: "threads",
      channel: "8",
    });

    renderCalendar();

    const statusBanner = await screen.findByRole("status");
    await waitFor(() =>
      expect(statusBanner).toHaveTextContent(
        /Tienda Threads.*Threads.*conectado/i,
      ),
    );

    await waitFor(() =>
      expect(replace).toHaveBeenCalledWith("/accounts/1/publications", {
        scroll: false,
      }),
    );
    // Banner survives query cleanup
    expect(screen.getByRole("status")).toBeInTheDocument();
  });

  it("muestra el aviso de ?connect_error y limpia la query con router.replace", async () => {
    searchParams = new URLSearchParams({
      connect_error: "El usuario canceló el permiso en Threads.",
    });

    renderCalendar();

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "El usuario canceló el permiso en Threads.",
    );
    await waitFor(() =>
      expect(replace).toHaveBeenCalledWith("/accounts/1/publications", {
        scroll: false,
      }),
    );
  });
});
