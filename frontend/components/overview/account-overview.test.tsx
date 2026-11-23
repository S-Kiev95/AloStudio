import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
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

import { AccountOverview } from "./account-overview";

const server = setupServer(
  http.get("*/live_reports/conversation_metrics", () =>
    HttpResponse.json({ open: 3, unattended: 0, unassigned: 0, pending: 0 }),
  ),
  http.get("*/reports/summary", () =>
    HttpResponse.json({
      conversations_count: 12,
      incoming_messages_count: 40,
      outgoing_messages_count: 35,
      avg_first_response_time: 60,
      avg_resolution_time: 3600,
      resolutions_count: 10,
      reply_time: 120,
      previous: {
        conversations_count: 10,
        incoming_messages_count: 30,
        outgoing_messages_count: 28,
        avg_first_response_time: 75,
        avg_resolution_time: 4000,
        resolutions_count: 8,
        reply_time: 150,
      },
    }),
  ),
  http.get("*/reports", () => HttpResponse.json([])),
);

beforeAll(() => server.listen({ onUnhandledRequest: "bypass" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

function renderOverview(accountId = "42") {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <AccountOverview accountId={accountId} />
    </QueryClientProvider>,
  );
}

describe("AccountOverview — encabezado con órbita de redes", () => {
  it("muestra el saludo, la bajada y los botones hacia bandeja y calendario", () => {
    renderOverview("42");

    expect(
      screen.getByRole("heading", {
        name: "Hola",
      }),
    ).toBeInTheDocument();

    expect(
      screen.getByText(
        "Todos tus canales, conversaciones y turnos en un solo lugar. Así están las cosas ahora y en los últimos 7 días.",
      ),
    ).toBeInTheDocument();

    expect(
      screen.getByRole("link", { name: "Abrir bandeja" }),
    ).toHaveAttribute("href", "/accounts/42/conversations");

    expect(
      screen.getByRole("link", { name: "Ir al calendario" }),
    ).toHaveAttribute("href", "/accounts/42/publications");
  });

  it("marca la órbita como decorativa con aria-hidden y renderiza las diez redes", () => {
    const { container } = renderOverview("42");

    const networkBubbles = container.querySelectorAll("[data-network]");
    expect(networkBubbles).toHaveLength(10);
    expect(
      Array.from(networkBubbles)
        .map((el) => el.getAttribute("data-network"))
        .sort(),
    ).toEqual([
      "facebook",
      "gmail",
      "instagram",
      "messenger",
      "telegram",
      "threads",
      "tiktok",
      "whatsapp",
      "x",
      "youtube",
    ]);

    const orbit = networkBubbles[0]?.closest("[aria-hidden='true']");
    expect(orbit).not.toBeNull();
    expect(
      orbit?.querySelectorAll("a, button, input, [tabindex]"),
    ).toHaveLength(0);
  });

  it("respeta DESIGN.md: sin doble neon-sign ni neon-nav fuera del sidebar y tarjetas clickeables a la bandeja", () => {
    const { container } = renderOverview("42");

    const heading = screen.getByRole("heading", { name: "Hola" });
    expect(heading).not.toHaveClass("neon-sign");

    const liveIcons = container.querySelectorAll("[data-live-icon]");
    expect(liveIcons).toHaveLength(4);
    expect(
      Array.from(liveIcons).map((el) => el.getAttribute("data-live-icon")),
    ).toEqual(["open", "unattended", "unassigned", "pending"]);

    for (const iconWrapper of liveIcons) {
      expect(iconWrapper).not.toHaveClass("neon-nav");
      expect(iconWrapper.className).not.toMatch(
        /text-warning|text-danger|text-info|bg-surface-2/,
      );
      const svg = iconWrapper.querySelector("svg");
      expect(svg).not.toBeNull();
      expect(svg).toHaveClass("h-8", "w-8");
      const link = iconWrapper.closest("a");
      expect(link).not.toBeNull();
      expect(link?.getAttribute("href")).toMatch(/^\/accounts\/42\/conversations\?/);
    }

    expect(container.querySelectorAll(".neon-nav")).toHaveLength(0);
  });

  it("muestra ErrorState con Reintentar y sin ceros falsos cuando fallan las métricas", async () => {
    let fail = true;
    server.use(
      http.get("*/live_reports/conversation_metrics", () =>
        fail
          ? HttpResponse.json({ message: "error" }, { status: 500 })
          : HttpResponse.json({ open: 7, unattended: 1, unassigned: 2, pending: 0 }),
      ),
      http.get("*/reports/summary", () =>
        HttpResponse.json({ message: "error" }, { status: 500 }),
      ),
      http.get("*/reports", () =>
        HttpResponse.json({ message: "error" }, { status: 500 }),
      ),
    );

    const { container } = renderOverview("42");

    expect(await screen.findByText("No pudimos cargar el estado actual.")).toBeInTheDocument();
    expect(screen.getByText("No pudimos cargar las métricas del período.")).toBeInTheDocument();
    expect(screen.getByText("No pudimos cargar el gráfico de conversaciones.")).toBeInTheDocument();
    expect(container.querySelectorAll("[data-live-icon]")).toHaveLength(0);

    const retryButtons = screen.getAllByRole("button", { name: "Reintentar" });
    expect(retryButtons).toHaveLength(3);

    fail = false;
    fireEvent.click(retryButtons[0]);
    expect(await screen.findByText("7")).toBeInTheDocument();
  });

  it("saluda por el primer nombre cuando el perfil está disponible y enlaza cada tarjeta Ahora mismo al filtro correcto", async () => {
    server.use(
      http.get("*/api/v1/profile", () =>
        HttpResponse.json({
          data: {
            id: 1,
            name: "Sofía Castro",
            available_name: "Sofía Castro",
            email: "sofia@ctc.edu.uy",
          },
        }),
      ),
    );

    const { container } = renderOverview("42");

    expect(
      await screen.findByRole("heading", { name: "Hola, Sofía" }),
    ).toBeInTheDocument();

    const hrefs = Array.from(container.querySelectorAll("[data-live-icon]")).map(
      (el) => el.closest("a")?.getAttribute("href"),
    );
    expect(hrefs).toEqual([
      "/accounts/42/conversations?status=open",
      "/accounts/42/conversations?status=open",
      "/accounts/42/conversations?assignee=unassigned",
      "/accounts/42/conversations?status=pending",
    ]);

    expect(
      screen.getByRole("link", { name: /Bandeja/ }),
    ).toHaveAttribute("href", "/accounts/42/conversations");
  });
});
