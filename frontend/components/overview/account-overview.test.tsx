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
        name: "Bienvenido",
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

  it("renderiza las cuatro tarjetas de Ahora mismo con iconos del mismo estilo que la sidebar y sin fondos ni colores sueltos", () => {
    const { container } = renderOverview("42");

    const liveIcons = container.querySelectorAll("[data-live-icon]");
    expect(liveIcons).toHaveLength(4);
    expect(
      Array.from(liveIcons).map((el) => el.getAttribute("data-live-icon")),
    ).toEqual(["open", "unattended", "unassigned", "pending"]);

    for (const iconWrapper of liveIcons) {
      expect(iconWrapper).toHaveClass("neon-nav");
      expect(iconWrapper.className).not.toMatch(
        /text-warning|text-danger|text-info|bg-surface-2/,
      );
      expect(iconWrapper.querySelector("svg")).not.toBeNull();
    }
  });
});
