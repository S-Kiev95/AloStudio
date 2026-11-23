import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from "vitest";

import { GoogleCalendarCard } from "./google-calendar-card";

let status: Record<string, unknown> = {};
let deleted = false;

const server = setupServer(
  http.get("*/profile/google_calendar", () => HttpResponse.json(status)),
  http.get("*/profile/google_calendar/authorize_url", () =>
    HttpResponse.json({ url: "https://accounts.google.com/o/oauth2/v2/auth?x=1" }),
  ),
  http.delete("*/profile/google_calendar", () => {
    deleted = true;
    return HttpResponse.json({ ...status, connected: false, email: null });
  }),
);

beforeAll(() => server.listen({ onUnhandledRequest: "bypass" }));
afterEach(() => {
  server.resetHandlers();
  deleted = false;
  vi.restoreAllMocks();
});
afterAll(() => server.close());

function renderCard() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <GoogleCalendarCard />
    </QueryClientProvider>,
  );
}

const base = { available: true, connected: false, email: null, last_synced_at: null, problem: null };

describe("GoogleCalendarCard", () => {
  it("is hidden while the installation has no Google", async () => {
    status = { ...base, available: false };
    renderCard();
    await new Promise((r) => setTimeout(r, 50));
    expect(screen.queryByText("Google Calendar")).not.toBeInTheDocument();
  });

  it("sends the user to Google's consent screen", async () => {
    status = base;
    const assign = vi.fn();
    vi.spyOn(window, "location", "get").mockReturnValue({
      ...window.location,
      pathname: "/accounts/1/settings/profile",
      assign,
    } as Location);
    renderCard();
    fireEvent.click(await screen.findByRole("button", { name: "Conectar Google Calendar" }));
    await waitFor(() =>
      expect(assign).toHaveBeenCalledWith("https://accounts.google.com/o/oauth2/v2/auth?x=1"),
    );
  });

  it("shows who is connected, says when Google took the access back, and disconnects", async () => {
    status = { ...base, connected: true, email: "sofia@gmail.com", problem: "revoked" };
    renderCard();
    expect(await screen.findByText(/Conectado como sofia@gmail\.com/)).toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent("Google ya no da acceso");
    expect(screen.getByRole("button", { name: "Conectar de nuevo" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Desconectar" }));
    await waitFor(() => expect(deleted).toBe(true));
    expect(await screen.findByRole("button", { name: "Conectar Google Calendar" })).toBeInTheDocument();
  });
});
