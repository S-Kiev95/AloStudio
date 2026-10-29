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
  vi,
} from "vitest";

import type { Channel, Publication } from "@/lib/api/publications";

import { PublicationDetailDialog } from "./publication-detail-dialog";

const IG_CHANNEL: Channel = {
  id: 10,
  network: "instagram",
  name: "AloStudio IG",
  username: "alostudio",
  avatar_url: null,
  status: "active",
  status_message: null,
  inbox_id: 3,
};

const THREADS_CHANNEL: Channel = {
  id: 20,
  network: "threads",
  name: "AloStudio Threads",
  username: "alostudio_th",
  avatar_url: null,
  status: "active",
  status_message: null,
  inbox_id: null,
};

const PARTIAL_PUB: Publication = {
  id: 501,
  account_id: 1,
  content: "Colección cápsula disponible en web",
  media: [{ type: "image", url: "https://s3.example/capsula.jpg", media_id: 7 }],
  scheduled_for: "2026-10-28T15:00:00Z",
  state: "partially_published",
  created_by_id: 1,
  published_at: "2026-10-28T15:00:10Z",
  created_at: "2026-10-27T10:00:00Z",
  updated_at: "2026-10-28T15:01:00Z",
  targets: [
    {
      id: 9001,
      channel: IG_CHANNEL,
      settings: { post_type: "feed" },
      content_override: null,
      state: "published",
      external_id: "1790001",
      permalink: "https://instagram.com/p/capsula",
      error_code: null,
      error_message: null,
      attempts: 1,
      published_at: "2026-10-28T15:00:10Z",
      metrics: {
        views: 1840,
        reach: 1210,
        likes: 96,
      },
      metrics_updated_at: new Date(Date.now() - 15 * 60_000).toISOString(),
      metrics_error: null,
    },
    {
      id: 9002,
      channel: THREADS_CHANNEL,
      settings: {},
      content_override: null,
      state: "failed",
      external_id: null,
      permalink: null,
      error_code: "token_expired",
      error_message: "El token de Threads venció; reconectá la cuenta.",
      attempts: 2,
      published_at: null,
      metrics: {},
      metrics_updated_at: null,
      metrics_error: null,
    },
  ],
};

const FAILED_PUB: Publication = {
  ...PARTIAL_PUB,
  id: 502,
  state: "failed",
  targets: [PARTIAL_PUB.targets[1]],
};

const server = setupServer(
  http.get("*/api/v1/accounts/1/publications/501", () =>
    HttpResponse.json(PARTIAL_PUB),
  ),
  http.get("*/api/v1/accounts/1/publications/502", () =>
    HttpResponse.json(FAILED_PUB),
  ),
);

beforeAll(() => {
  server.listen({ onUnhandledRequest: "bypass" });
  HTMLDialogElement.prototype.showModal = function () {
    this.open = true;
  };
  HTMLDialogElement.prototype.close = function () {
    this.open = false;
  };
});

afterEach(() => {
  server.resetHandlers();
  vi.restoreAllMocks();
});
afterAll(() => server.close());

function renderDetail({
  publication = PARTIAL_PUB,
  isAdmin,
  onClose = vi.fn(),
}: {
  publication?: Publication;
  isAdmin: boolean;
  onClose?: () => void;
}) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={qc}>
      <PublicationDetailDialog
        accountId="1"
        publication={publication}
        open={true}
        onClose={onClose}
        isAdmin={isAdmin}
      />
    </QueryClientProvider>,
  );
}

describe("PublicationDetailDialog", () => {
  it("muestra cifras, 'actualizado hace…', error del destino y link, y oculta acciones a un agente", async () => {
    renderDetail({ isAdmin: false });

    expect(
      await screen.findByText("Colección cápsula disponible en web"),
    ).toBeInTheDocument();

    // Permalink
    const link = screen.getByRole("link", { name: /Ver en la red/i });
    expect(link).toHaveAttribute("href", "https://instagram.com/p/capsula");

    // Metrics + "actualizado hace…"
    expect(screen.getByText((1840).toLocaleString())).toBeInTheDocument();
    expect(screen.getByText((1210).toLocaleString())).toBeInTheDocument();
    expect(screen.getByText("96")).toBeInTheDocument();
    expect(screen.getByText(/actualizado hace/i)).toBeInTheDocument();

    // Failed target error message
    expect(
      screen.getByText("El token de Threads venció; reconectá la cuenta."),
    ).toBeInTheDocument();

    // Agent sees NO admin buttons
    expect(screen.queryByRole("button", { name: /Reintentar/i })).toBeNull();
    expect(
      screen.queryByRole("button", { name: /Actualizar estadísticas/i }),
    ).toBeNull();
    expect(screen.queryByRole("button", { name: /Borrar/i })).toBeNull();
    expect(screen.queryByRole("button", { name: /Editar/i })).toBeNull();
  });

  it("habilita Reintentar y Actualizar estadísticas para un administrador en partially_published y Borrar en failed", async () => {
    let retried = false;
    let refreshed = false;
    let deleted = false;
    server.use(
      http.post("*/api/v1/accounts/1/publications/501/retry", () => {
        retried = true;
        return HttpResponse.json(PARTIAL_PUB);
      }),
      http.post("*/api/v1/accounts/1/publications/501/refresh_metrics", () => {
        refreshed = true;
        return HttpResponse.json(PARTIAL_PUB);
      }),
      http.delete("*/api/v1/accounts/1/publications/502", () => {
        deleted = true;
        return HttpResponse.json({});
      }),
    );

    const { unmount } = renderDetail({
      publication: PARTIAL_PUB,
      isAdmin: true,
    });

    fireEvent.click(await screen.findByRole("button", { name: /Reintentar/i }));
    await waitFor(() => expect(retried).toBe(true));

    fireEvent.click(
      screen.getByRole("button", { name: /Actualizar estadísticas/i }),
    );
    await waitFor(() => expect(refreshed).toBe(true));

    // partially_published cannot be deleted according to state rules
    expect(screen.queryByRole("button", { name: /Borrar/i })).toBeNull();
    unmount();

    // Failed publication CAN be deleted (with confirmation)
    vi.spyOn(window, "confirm").mockReturnValue(true);
    const onClose = vi.fn();
    renderDetail({ publication: FAILED_PUB, isAdmin: true, onClose });

    fireEvent.click(await screen.findByRole("button", { name: /Borrar/i }));
    await waitFor(() => expect(deleted).toBe(true));
    expect(onClose).toHaveBeenCalled();
  });
});
