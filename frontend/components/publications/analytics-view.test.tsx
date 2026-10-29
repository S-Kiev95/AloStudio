import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";

import type { Analytics, Channel } from "@/lib/api/publications";

import { PublicationsAnalyticsView } from "./analytics-view";

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

const ANALYTICS_DATA: Analytics = {
  from: "2026-09-29",
  to: "2026-10-29",
  totals: {
    posts: 8,
    views: 12500,
    reach: 9400,
    likes: 0,
    comments: 14,
    // interactions, shares, saves intentionally omitted -> must render "—", NOT "0"
  },
  channels: [
    {
      channel: IG_CHANNEL,
      posts: 8,
      followers: 4200,
      followers_change: 135,
      metrics: {
        views: 12500,
        reach: 9400,
        likes: 0,
        comments: 14,
      },
      series: [
        { date: "2026-10-27", followers: 4100, reach: 3100, views: 4000 },
        { date: "2026-10-28", followers: 4200, reach: 6300, views: 8500 },
      ],
    },
  ],
  top_posts: [
    {
      publication_id: 77,
      target_id: 88,
      channel: IG_CHANNEL,
      content: "Lanzamiento de primavera en tienda",
      permalink: "https://instagram.com/p/primavera",
      published_at: "2026-10-25T15:00:00Z",
      metrics: {
        views: 7200,
        reach: 5100,
        likes: 340,
      },
    },
  ],
};

const server = setupServer(
  http.get("*/api/v1/accounts/1/publications/channels", () =>
    HttpResponse.json([IG_CHANNEL]),
  ),
  http.get("*/api/v1/accounts/1/publications/analytics", () =>
    HttpResponse.json(ANALYTICS_DATA),
  ),
);

beforeAll(() => server.listen({ onUnhandledRequest: "bypass" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

function renderAnalytics() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={qc}>
      <PublicationsAnalyticsView accountId="1" />
    </QueryClientProvider>,
  );
}

describe("PublicationsAnalyticsView", () => {
  it("muestra el estado vacío con Instagram y Facebook y botón al calendario cuando no hay canales", async () => {
    let analyticsCalled = false;
    server.use(
      http.get("*/api/v1/accounts/1/publications/channels", () =>
        HttpResponse.json([]),
      ),
      http.get("*/api/v1/accounts/1/publications/analytics", () => {
        analyticsCalled = true;
        return HttpResponse.json(ANALYTICS_DATA);
      }),
    );

    renderAnalytics();

    const empty = await screen.findByTestId("analytics-empty-state");
    expect(empty).toHaveTextContent("Todavía no hay estadísticas para mostrar");
    expect(empty).toHaveTextContent("Instagram");
    expect(empty).toHaveTextContent("Facebook");

    const calLink = within(empty).getByRole("link", {
      name: /Ir al calendario para agregar canales/i,
    });
    expect(calLink).toHaveAttribute("href", "/accounts/1/publications");
    expect(analyticsCalled).toBe(false);
  });

  it("muestra tarjetas de totales, '—' para cifras ausentes (y '0' cuando viene 0), desglose por canal y mejores publicaciones", async () => {
    renderAnalytics();

    const postsCard = await screen.findByTestId("total-card-posts");
    expect(postsCard).toHaveTextContent("8");

    expect(screen.getByTestId("total-card-views")).toHaveTextContent(
      (12500).toLocaleString(),
    );
    expect(screen.getByTestId("total-card-reach")).toHaveTextContent(
      (9400).toLocaleString(),
    );
    // Explicit 0 stays "0"
    expect(screen.getByTestId("total-card-likes")).toHaveTextContent("0");

    // Absent keys render "—", never "0"
    expect(screen.getByTestId("total-card-interactions")).toHaveTextContent("—");
    expect(screen.getByTestId("total-card-shares")).toHaveTextContent("—");
    expect(screen.getByTestId("total-card-saves")).toHaveTextContent("—");

    // Cadence notice required by contract
    expect(
      screen.getByText(/03:47 UTC/),
    ).toBeInTheDocument();

    // Channel followers + variation + daily bars + top post link
    expect(screen.getByText((4200).toLocaleString())).toBeInTheDocument();
    expect(screen.getByText(/\+135/)).toBeInTheDocument();
    expect(
      screen.getByText("Lanzamiento de primavera en tienda"),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /Ver publicación/i }),
    ).toHaveAttribute("href", "https://instagram.com/p/primavera");
  });
});
