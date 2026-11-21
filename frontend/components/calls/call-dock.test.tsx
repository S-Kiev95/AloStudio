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
const ringtone = vi.fn();
const outgoing = {
  offerSdp: "OFFER-FROM-BROWSER",
  applyAnswer: vi.fn(async () => undefined),
  waitConnected: vi.fn(async () => true),
  startSending: vi.fn(),
  setMuted: vi.fn(),
  onLost: vi.fn(),
  close: vi.fn(),
};
const placeCall = vi.fn(async () => outgoing);

vi.mock("./call-audio", () => ({
  answerOffer: (...args: unknown[]) => answerOffer(...(args as [])),
  placeCall: (...args: unknown[]) => placeCall(...(args as [])),
  startRingtone: (...args: unknown[]) => {
    ringtone(...args);
    return stopRing;
  },
  MicrophoneBlocked: class extends Error {},
}));

import { CallDock } from "./call-dock";
import { requestDial } from "./dialer";

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
let placedBody: unknown = null;
// What GET /calls/8 answers while my outgoing call rings: set by each test.
let outboundState: Partial<Call> = { status: "ringing" };
const placed: Call = {
  ...({} as Call),
  id: 8,
  status: "ringing",
  direction: "outbound",
  provider: "whatsapp",
  inbox_id: 3,
  inbox_name: "WhatsApp CTC",
  conversation_id: 40,
  conversation_display_id: 12,
  contact: { id: 9, name: "Lucía Pereira", phone_number: "+59891234567" },
  from_number: "+59899000111",
  answered_by: { id: 5, name: "Sofía" },
  can_answer: false,
  created_at: "2026-11-15T15:00:00Z",
  answered_at: null,
  ended_at: null,
  duration_seconds: null,
};

const server = setupServer(
  http.get("*/api/v1/profile", () => HttpResponse.json({ data: { id: 5, name: "Sofía" } })),
  http.get("*/calls/active", () => HttpResponse.json({ payload: [ringing] })),
  http.post("*/api/v1/accounts/1/calls", async ({ request }) => {
    placedBody = await request.json();
    return HttpResponse.json(placed, { status: 201 });
  }),
  http.get("*/calls/8", () => HttpResponse.json({ ...placed, ...outboundState })),
  http.post("*/calls/8/hangup", () => {
    steps.push({ step: "hangup-8", body: null });
    return HttpResponse.json({ ...placed, status: "missed" });
  }),
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
  placedBody = null;
  outboundState = { status: "ringing" };
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
    // As the backend sends it: the call rings for me (Sofía, id 5).
    server.use(
      http.get("*/calls/active", () =>
        HttpResponse.json({ payload: [{ ...ringing, ring_user_ids: [5] }] }),
      ),
    );
    renderDock();
    expect(await screen.findByText("Lucía Pereira")).toBeInTheDocument();
    expect(screen.getByText("Llamada de WhatsApp · WhatsApp CTC")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Atender" }));

    expect(await screen.findByRole("button", { name: /Colgar/ })).toBeInTheDocument();
    // Never both: the list still says "ringing" until Meta confirms.
    expect(screen.queryByRole("button", { name: "Atender" })).not.toBeInTheDocument();
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

  it("rings only for the people the call rings for", async () => {
    const other: Call = {
      ...ringing,
      id: 9,
      contact: { id: 10, name: "Pedro Gómez", phone_number: "+59891111111" },
      ring_user_ids: [99],
    };
    server.use(
      http.get("*/calls/active", () =>
        HttpResponse.json({ payload: [{ ...ringing, ring_user_ids: [5, 99] }, other] }),
      ),
    );
    renderDock();
    expect(await screen.findByText("Lucía Pereira")).toBeInTheDocument();
    expect(screen.queryByText("Pedro Gómez")).not.toBeInTheDocument();
  });

  it("rings softly while I am on a call and nobody else is free", async () => {
    const qc = renderDock();
    fireEvent.click(await screen.findByRole("button", { name: "Atender" }));
    expect(await screen.findByRole("button", { name: /Colgar/ })).toBeInTheDocument();

    upsertActiveCall(qc, "1", {
      ...ringing,
      id: 9,
      contact: { id: 10, name: "Pedro Gómez", phone_number: "+59891111111" },
      ring_user_ids: [5],
    });

    expect(await screen.findByText("Pedro Gómez")).toBeInTheDocument();
    expect(
      screen.getByText("Estás en otra llamada y no hay nadie más libre: cortá para atender."),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Atender" })).toBeDisabled();
    await waitFor(() => expect(ringtone).toHaveBeenLastCalledWith(true));
  });

  it("stops ringing for me when I ignore it", async () => {
    renderDock();
    fireEvent.click(await screen.findByRole("button", { name: "Ignorar" }));
    await waitFor(() => expect(screen.queryByText("Lucía Pereira")).not.toBeInTheDocument());
    expect(stopRing).toHaveBeenCalled();
  });
});

describe("CallDock — calling a customer", () => {
  it("places the call, applies the answer and goes live when they pick up", async () => {
    renderDock();
    await screen.findByText("Lucía Pereira"); // the incoming one in the list

    requestDial({ conversationId: 12, contactName: "Lucía Pereira" });
    expect(await screen.findByText("Llamando…")).toBeInTheDocument();
    expect(placeCall).toHaveBeenCalled();
    expect(placedBody).toEqual({ conversation_id: 12, sdp: "OFFER-FROM-BROWSER" });

    outboundState = { status: "ringing", sdp_answer: "THEIR-ANSWER" };
    await waitFor(() => expect(outgoing.applyAnswer).toHaveBeenCalledWith("THEIR-ANSWER"), {
      timeout: 4000,
    });
    expect(outgoing.startSending).not.toHaveBeenCalled();

    outboundState = { status: "in_progress", sdp_answer: "THEIR-ANSWER" };
    await waitFor(() => expect(outgoing.startSending).toHaveBeenCalled(), { timeout: 4000 });
    expect(await screen.findByText("0:00")).toBeInTheDocument();
  });

  it("says nobody answered when the call ends while ringing", async () => {
    renderDock();
    requestDial({ conversationId: 12, contactName: "Lucía Pereira" });
    expect(await screen.findByText("Llamando…")).toBeInTheDocument();
    outboundState = { status: "missed" };
    expect(await screen.findByText("No atendió.", {}, { timeout: 4000 })).toBeInTheDocument();
    expect(outgoing.close).toHaveBeenCalled();
  });

  it("hangs up a call that is still ringing", async () => {
    renderDock();
    requestDial({ conversationId: 12, contactName: "Lucía Pereira" });
    expect(await screen.findByText("Llamando…")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Colgar/ }));
    await waitFor(() => expect(steps.map((x) => x.step)).toContain("hangup-8"));
    expect(outgoing.close).toHaveBeenCalled();
  });
});
