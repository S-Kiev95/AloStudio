import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import type { ReactNode } from "react";
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";

import { ROLE_ADMINISTRATOR } from "@/lib/api/account";

import { BroadcastsPanel } from "./broadcasts-panel";
import { BusinessProfilePanel } from "./business-profile-panel";
import { LinkQrPanel, waMeLink } from "./link-qr-panel";
import { messagingLimitLabel, NumberStatusPanel } from "./number-status-panel";

const WA = "*/api/v1/accounts/1/inboxes/7/whatsapp";
let lastCampaign: Record<string, unknown> | null = null;
let lastProfile: Record<string, unknown> | null = null;
let lastQr: Record<string, unknown> | null = null;

const server = setupServer(
  http.get("*/api/v1/profile", () =>
    HttpResponse.json({
      data: {
        id: 1,
        name: "Admin",
        email: "admin@alostudio.test",
        accounts: [{ id: 1, name: "AloStudio", role: ROLE_ADMINISTRATOR }],
      },
    }),
  ),
  http.get(`${WA}/phone`, () =>
    HttpResponse.json({
      phone_number: "+59899000000",
      display_phone_number: "+598 99 000 000",
      verified_name: "CTC Salto",
      name_status: "APPROVED",
      quality_rating: "RED",
      messaging_limit: "TIER_1K",
      status: "CONNECTED",
      code_verification_status: null,
      throughput: "STANDARD",
      platform_type: "CLOUD_API",
    }),
  ),
  http.get(`${WA}/profile`, () =>
    HttpResponse.json({
      about: "Cursos",
      address: null,
      description: "Centro de formación",
      email: null,
      websites: ["https://ctc.edu.uy"],
      vertical: "EDU",
      profile_picture_url: null,
    }),
  ),
  http.post(`${WA}/profile`, async ({ request }) => {
    lastProfile = (await request.json()) as Record<string, unknown>;
    return HttpResponse.json({ ...lastProfile, profile_picture_url: null });
  }),
  http.get(`${WA}/qr`, () =>
    HttpResponse.json({
      qr_codes: [
        {
          code: "ABC",
          prefilled_message: "Hola, vi el cartel",
          deep_link_url: "https://wa.me/message/ABC",
          qr_image_url: "https://cdn.example/qr.png",
        },
      ],
    }),
  ),
  http.post(`${WA}/qr`, async ({ request }) => {
    lastQr = (await request.json()) as Record<string, unknown>;
    return HttpResponse.json({ qr_codes: [] });
  }),
  http.get(`${WA}/templates`, () =>
    HttpResponse.json({
      templates: [
        {
          name: "inscripciones",
          language: "es",
          status: "APPROVED",
          category: "MARKETING",
          body_text: "Hola {{1}}, abrimos inscripciones.",
          variables: [1],
        },
      ],
      last_updated: null,
    }),
  ),
  http.get("*/api/v1/accounts/1/labels", () =>
    HttpResponse.json({ payload: [{ id: 3, title: "alumnos" }] }),
  ),
  http.get("*/api/v1/accounts/1/campaigns", () =>
    HttpResponse.json([
      {
        id: 5,
        display_id: 5,
        title: "Marzo",
        message: "Hola",
        inbox_id: 7,
        campaign_type: "one_off",
        campaign_status: "completed",
        audience: [{ type: "Inbox" }],
        scheduled_at: "2026-11-10T12:00:00Z",
        template_params: { name: "inscripciones" },
      },
      {
        id: 6,
        display_id: 6,
        title: "De otro número",
        inbox_id: 99,
        campaign_type: "one_off",
        campaign_status: "active",
        audience: [],
        scheduled_at: null,
        template_params: null,
      },
    ]),
  ),
  http.post("*/api/v1/accounts/1/campaigns", async ({ request }) => {
    lastCampaign = ((await request.json()) as { campaign: Record<string, unknown> }).campaign;
    return HttpResponse.json({ id: 7, display_id: 7, ...lastCampaign });
  }),
  http.get("*/api/v1/accounts/1/campaigns/5/analytics", () =>
    HttpResponse.json({
      campaign_id: 5,
      audience_count: 1,
      conversations_count: 2,
      messages_count: 2,
      delivery: { sent: 0, delivered: 0, read: 1, failed: 1 },
    }),
  ),
  http.get("*/api/v1/accounts/1/campaigns/5/recipients", () =>
    HttpResponse.json({
      recipients: [
        {
          contact_id: 1,
          name: "Ana",
          phone_number: "+59899111222",
          conversation_id: 40,
          status: "read",
          error: null,
          sent_at: 1,
        },
        {
          contact_id: 2,
          name: "Beto",
          phone_number: "+59899333444",
          conversation_id: 41,
          status: "failed",
          error: "Número sin WhatsApp",
          sent_at: 1,
        },
      ],
    }),
  ),
);

beforeAll(() => server.listen({ onUnhandledRequest: "bypass" }));
afterEach(() => {
  server.resetHandlers();
  lastCampaign = null;
  lastProfile = null;
  lastQr = null;
});
afterAll(() => server.close());

function wrap(ui: ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

describe("WhatsApp section panels", () => {
  it("explains the number's state and warns on low quality", async () => {
    expect(messagingLimitLabel("TIER_1K")).toBe("1.000 contactos nuevos por día");
    expect(messagingLimitLabel("TIER_UNLIMITED")).toBe("Sin límite");
    wrap(<NumberStatusPanel accountId="1" inboxId={7} />);
    expect(await screen.findByText("CTC Salto")).toBeInTheDocument();
    expect(screen.getByText("Conectado")).toBeInTheDocument();
    expect(screen.getByText("Baja")).toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent(/Meta marcó un problema/);
  });

  it("edits the business profile with a live preview", async () => {
    wrap(<BusinessProfilePanel accountId="1" inboxId={7} inboxName="WA CTC" />);
    const about = await screen.findByLabelText(/Info/);
    await waitFor(() => expect(about).toHaveValue("Cursos"));
    fireEvent.change(about, { target: { value: "Cursos y talleres" } });
    const preview = screen.getByTestId("whatsapp-profile-preview");
    expect(within(preview).getByText("Cursos y talleres")).toBeInTheDocument();
    expect(within(preview).getByText("Educación")).toBeInTheDocument();
    fireEvent.click(await screen.findByRole("button", { name: "Guardar perfil" }));
    await waitFor(() => expect(lastProfile).not.toBeNull());
    expect(lastProfile).toMatchObject({
      about: "Cursos y talleres",
      websites: ["https://ctc.edu.uy"],
      vertical: "EDU",
    });
  });

  it("builds wa.me links and creates QR codes", async () => {
    expect(waMeLink("+598 99 000 000", "Hola, info")).toBe(
      "https://wa.me/59899000000?text=Hola%2C%20info",
    );
    wrap(<LinkQrPanel accountId="1" inboxId={7} phoneNumber="+59899000000" />);
    expect(await screen.findByText("“Hola, vi el cartel”")).toBeInTheDocument();
    fireEvent.change(await screen.findByLabelText("Mensaje del QR nuevo"), {
      target: { value: "Hola, quiero info" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Crear QR/ }));
    await waitFor(() => expect(lastQr).toEqual({ prefilled_message: "Hola, quiero info" }));
  });

  it("lists this number's sends with per-contact results", async () => {
    wrap(<BroadcastsPanel accountId="1" inboxId={7} inboxName="WA CTC" />);
    expect(await screen.findByText("Marzo")).toBeInTheDocument();
    expect(screen.queryByText("De otro número")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: /Marzo/ }));
    expect(await screen.findByText("Beto")).toBeInTheDocument();
    expect(screen.getByText("Número sin WhatsApp")).toBeInTheDocument();
    expect(screen.getByText("Leído")).toBeInTheDocument();
  });

  it("creates a mass send with a template, labels and personalized variables", async () => {
    wrap(<BroadcastsPanel accountId="1" inboxId={7} inboxName="WA CTC" />);
    fireEvent.click(await screen.findByRole("button", { name: /Nuevo envío/ }));
    fireEvent.change(await screen.findByLabelText("Plantilla aprobada"), {
      target: { value: "inscripciones" },
    });
    fireEvent.change(screen.getByLabelText("Variable {{1}}"), {
      target: { value: "{primer_nombre}" },
    });
    expect(
      within(screen.getByTestId("whatsapp-template-preview")).getByText(
        "Hola Ana, abrimos inscripciones.",
      ),
    ).toBeInTheDocument();
    const send = screen.getByRole("button", { name: "Enviar" });
    expect(send).toBeDisabled(); // no label picked yet
    fireEvent.click(await screen.findByRole("button", { name: "alumnos" }));
    fireEvent.click(send);
    await waitFor(() => expect(lastCampaign).not.toBeNull());
    expect(lastCampaign).toMatchObject({
      campaign_type: "one_off",
      inbox_id: 7,
      audience: [{ type: "Label", id: 3 }],
      template_params: {
        name: "inscripciones",
        language: "es",
        processed_params: { body: { "1": "{primer_nombre}" } },
      },
    });
  });
});
