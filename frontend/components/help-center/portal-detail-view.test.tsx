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

import { PortalDetailView } from "./portal-detail-view";

const articleLocales: (string | null)[] = [];

function portal(allowedLocales: string[]) {
  return {
    id: 1,
    account_id: 1,
    name: "Test Portal",
    slug: "test-portal",
    custom_domain: null,
    color: "#1f93ff",
    homepage_link: null,
    page_title: null,
    header_text: null,
    config: { allowed_locales: allowedLocales },
    archived: false,
  };
}

let allowed = ["en", "es"];

const server = setupServer(
  http.get("*/portals/test-portal", () => HttpResponse.json(portal(allowed))),
  http.get("*/portals/test-portal/articles", ({ request }) => {
    articleLocales.push(new URL(request.url).searchParams.get("locale"));
    return HttpResponse.json([]);
  }),
  http.get("*/portals/test-portal/categories", () => HttpResponse.json([])),
);

beforeAll(() => server.listen({ onUnhandledRequest: "bypass" }));
afterEach(() => {
  server.resetHandlers();
  articleLocales.length = 0;
  allowed = ["en", "es"];
});
afterAll(() => server.close());

function wrap(ui: React.ReactElement) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

describe("PortalDetailView locale picker", () => {
  it("filters articles by the picked portal locale", async () => {
    wrap(<PortalDetailView accountId="1" slug="test-portal" />);

    await screen.findByText("Test Portal");
    // First articles fetch carries no locale filter.
    await waitFor(() => expect(articleLocales).toContain(null));

    const select = screen.getByLabelText("Idioma");
    fireEvent.change(select, { target: { value: "es" } });

    await waitFor(() => expect(articleLocales).toContain("es"));
  });

  it("hides the picker when the portal has a single locale", async () => {
    allowed = ["en"];
    wrap(<PortalDetailView accountId="1" slug="test-portal" />);

    await screen.findByText("Test Portal");
    expect(screen.queryByLabelText("Idioma")).toBeNull();
  });
});
