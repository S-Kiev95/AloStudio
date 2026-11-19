import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from "vitest";

import { HelpButton } from "./help-button";

const push = vi.fn();
let pathname = "/accounts/1/settings/lifecycle";

vi.mock("next/navigation", () => ({
  usePathname: () => pathname,
  useRouter: () => ({ push, replace: vi.fn() }),
}));

let modes: string[] = ["fast", "free"];
let created: Record<string, unknown> | null = null;
let fastAllowed = true;
let allowed: unknown = null;
let isAdmin = true;

const server = setupServer(
  http.get("*/api/v1/accounts/1/agent", () =>
    HttpResponse.json({
      enabled: modes.length > 0,
      modes,
      fast_possible: true,
      fast_allowed: fastAllowed,
      model: "m",
      can_write: true,
      is_administrator: isAdmin,
    }),
  ),
  http.put("*/help_assistant/settings", async ({ request }) => {
    allowed = await request.json();
    fastAllowed = (allowed as { fast: boolean }).fast;
    modes = fastAllowed ? ["fast"] : [];
    return HttpResponse.json({});
  }),
  http.post("*/api/v1/accounts/1/agent/threads", async ({ request }) => {
    created = (await request.json()) as Record<string, unknown>;
    return HttpResponse.json({
      id: 12,
      title: "¿Cómo creo una etapa?",
      created_at: "2026-11-19T10:00:00Z",
      updated_at: "2026-11-19T10:00:00Z",
      items: [
        { id: 1, kind: "user", content: "¿Cómo creo una etapa?", created_at: "2026-11-19T10:00:00Z" },
        {
          id: 2,
          kind: "assistant",
          content: "Tocá \"Nueva etapa\". [[pantalla:ajustes_etapas]]",
          created_at: "2026-11-19T10:00:01Z",
          screens: [{ key: "ajustes_etapas", label: "Ajustes → Etapas", path: "settings/lifecycle" }],
        },
      ],
      pending_action: null,
    });
  }),
);

beforeAll(() => server.listen({ onUnhandledRequest: "bypass" }));
afterEach(() => {
  server.resetHandlers();
  modes = ["fast", "free"];
  created = null;
  fastAllowed = true;
  allowed = null;
  isAdmin = true;
  pathname = "/accounts/1/settings/lifecycle";
  push.mockReset();
  window.localStorage.clear();
});
afterAll(() => server.close());

function renderButton() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <HelpButton accountId="1" />
    </QueryClientProvider>,
  );
}

describe("HelpButton", () => {
  it("is hidden while no mode is set up, except to an administrator", async () => {
    modes = [];
    fastAllowed = false;
    isAdmin = false;
    renderButton();
    await new Promise((r) => setTimeout(r, 50));
    expect(screen.queryByRole("button", { name: "Ayuda" })).toBeNull();
  });

  it("opens the Agent over the screen, in the chosen mode, with links to screens", async () => {
    renderButton();
    fireEvent.click(await screen.findByRole("button", { name: "Ayuda" }));
    // Free by default in the «?» (no cost) when nothing was picked.
    expect(await screen.findByRole("radio", { name: "Free" })).toHaveAttribute("aria-checked", "true");
    fireEvent.change(screen.getByLabelText("Mensaje para el agente"), {
      target: { value: "¿Cómo creo una etapa?" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Enviar mensaje" }));

    await waitFor(() => expect(created).not.toBeNull());
    expect(created).toMatchObject({
      content: "¿Cómo creo una etapa?",
      mode: "free",
      page: "/accounts/1/settings/lifecycle",
    });
    const link = await screen.findByRole("link", { name: "Ir a Ajustes → Etapas" });
    expect(link).toHaveAttribute("href", "/accounts/1/settings/lifecycle");
    // The chat stays in the panel.
    expect(push).not.toHaveBeenCalled();
    const panel = screen.getByRole("dialog", { name: "Ayuda" });
    expect(panel).toHaveClass("flex");
    // Following the link closes it.
    fireEvent.click(link);
    expect(panel).toHaveClass("hidden");
  });

  it("closes with the X and keeps the chosen mode", async () => {
    window.localStorage.setItem("alostudio:help-mode", "fast");
    renderButton();
    fireEvent.click(await screen.findByRole("button", { name: "Ayuda" }));
    expect(await screen.findByRole("radio", { name: "Fast" })).toHaveAttribute("aria-checked", "true");
    fireEvent.click(screen.getByRole("button", { name: "Cerrar" }));
    expect(document.querySelector('[role="dialog"]')).toHaveClass("hidden");
  });

  it("lets an administrator allow Fast when nothing answers yet", async () => {
    modes = [];
    fastAllowed = false;
    renderButton();
    fireEvent.click(await screen.findByRole("button", { name: "Ayuda" }));
    fireEvent.click(await screen.findByLabelText("Permitir el modo Fast en esta cuenta (gasta en OpenAI)"));
    await waitFor(() => expect(allowed).toEqual({ fast: true }));
  });

  it("is off on the Agente screen, where the chat already is", async () => {
    pathname = "/accounts/1/agent/3";
    renderButton();
    expect(await screen.findByRole("button", { name: "Ayuda" })).toBeDisabled();
  });
});
