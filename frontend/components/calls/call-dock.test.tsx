import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

import { type Call, upsertActiveCall } from "@/lib/api/calls";

const audio = {
  answerSdp: "ANSWER-SDP",
  waitConnected: vi.fn(async () => true),
  startSending: vi.fn(),
  setMuted: vi.fn(),
  onLost: vi.fn(),
  close: vi.fn(),
};
const answerOffer = vi.fn(async () => audio);
const stopRing = vi.fn();

vi.mock("./call-audio", () => ({
  answerOffer: (...args: unknown[]) => answerOffer(...(args as [])),
  startRingtone: () => stopRing,
  MicrophoneBlocked: class extends Error {},
}));

import { CallDock } from "./call-dock";

const ringing: Call = {
  id: 7,
  status: "ringing",
  direction: "inbound",
  provider: "whatsapp",
  inbox_id: 3,
  inbox_name: "WhatsApp CTC",
  conversation_id: 40,
  conversation_display_id: 12,
  contact: { id: 9, name: "Lucía Pereira", phone_number: "+59891234567" },
  from_number: "+59891234567",
  answered_by: null,
  can_answer: true,
  created_at: "2026-11-14T15:00:00Z",
  answered_at: null,
  ended_at: null,
  duration_seconds: null,
};

const steps: Array<{ step: string; body: unknown }> = [];
let preAcceptStatus = 200;

const server = setupServer(
  http.get("*/calls/active", () => HttpResponse.json({ payload: [ringing] })),
  http.get("*/calls/7", () => HttpResponse.json({ ...ringing, sdp_offer: "OFFER-SDP" })),
  http.post("*/calls/7/:step", async ({ request, params }) => {
    const text = await request.text();
    steps.push({ step: String(params.step), body: text ? JSON.parse(text) : null });
    if (params.step === "pre_accept" && preAcceptStatus !== 200) {
      return HttpResponse.json(
        { message: "calls.taken", code: "calls.taken" },
        { status: preAcceptStatus },
      );
    }
    const status =
      params.step === "pre_accept" ? "connecting" : params.step === "accept" ? "in_progress" : "completed";
    return HttpResponse.json({ ...ringing, status, can_answer: false });
  }),
);

beforeAll(() => server.listen({ onUnhandledRequest: "bypass" }));
beforeEach(() => {
  steps.length = 0;
  preAcceptStatus = 200;
  vi.clearAllMocks();
});
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

function renderDock() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <CallDock accountId="1" />
    </QueryClientProvider>,
  );
  return qc;
}

describe("CallDock", () => {
  it("rings, answers from the browser and hangs up", async () => {
    renderDock();
    expect(await screen.findByText("Lucía Pereira")).toBeInTheDocument();
    expect(screen.getByText("Llamada de WhatsApp · WhatsApp CTC")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Atender" }));

    expect(await screen.findByRole("button", { name: /Colgar/ })).toBeInTheDocument();
    await waitFor(() => expect(audio.startSending).toHaveBeenCalled());
    expect(answerOffer).toHaveBeenCalledWith("OFFER-SDP", expect.anything());
    expect(steps.map((s) => s.step)).toEqual(["pre_accept", "accept"]);
    expect(steps[0].body).toEqual({ sdp: "ANSWER-SDP" });
    expect(steps[1].body).toEqual({ sdp: "ANSWER-SDP" });
    expect(await screen.findByText("0:00")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Abrir conversación" })).toHaveAttribute(
      "href",
      "/accounts/1/conversations/12",
    );

    fireEvent.click(screen.getByRole("button", { name: /Silenciar/ }));
    expect(audio.setMuted).toHaveBeenCalledWith(true);

    fireEvent.click(screen.getByRole("button", { name: /Colgar/ }));
    await waitFor(() => expect(steps.map((s) => s.step)).toContain("hangup"));
    expect(audio.close).toHaveBeenCalled();
  });

  it("closes the audio when the customer hangs up first", async () => {
    const qc = renderDock();
    fireEvent.click(await screen.findByRole("button", { name: "Atender" }));
    expect(await screen.findByRole("button", { name: /Colgar/ })).toBeInTheDocument();

    // What the cable delivers when Meta reports the end.
    upsertActiveCall(qc, "1", { ...ringing, status: "completed", duration_seconds: 42 });

    expect(await screen.findByText("La llamada terminó.")).toBeInTheDocument();
    expect(audio.close).toHaveBeenCalled();
    expect(steps.map((s) => s.step)).not.toContain("hangup");
  });

  it("says so when someone else took the call first", async () => {
    preAcceptStatus = 409;
    renderDock();
    fireEvent.click(await screen.findByRole("button", { name: "Atender" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Otra persona del equipo ya atendió esta llamada.",
    );
    expect(audio.close).toHaveBeenCalled();
    expect(steps.map((s) => s.step)).toEqual(["pre_accept"]);
  });

  it("stops ringing for me when I ignore it", async () => {
    renderDock();
    fireEvent.click(await screen.findByRole("button", { name: "Ignorar" }));
    await waitFor(() => expect(screen.queryByText("Lucía Pereira")).not.toBeInTheDocument());
    expect(stopRing).toHaveBeenCalled();
  });
});
