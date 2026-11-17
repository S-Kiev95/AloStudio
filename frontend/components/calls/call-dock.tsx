"use client";

import { Mic, MicOff, Phone, PhoneOff } from "lucide-react";
import Link from "next/link";
import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useRef, useState } from "react";

import { Avatar } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import {
  ACTIVE_CALL_STATUSES,
  type Call,
  callApi,
  callKey,
  useActiveCalls,
  useCall,
} from "@/lib/api/calls";
import { useProfile } from "@/lib/api/profile";
import { useT } from "@/lib/i18n/provider";
import { translateOr } from "@/lib/i18n/translate";
import { cn } from "@/lib/utils";

import {
  answerOffer,
  type CallAudio,
  MicrophoneBlocked,
  type OutgoingAudio,
  placeCall,
  startRingtone,
} from "./call-audio";
import { type DialRequest, onDialRequest } from "./dialer";

/** How long to wait for the audio path before confirming anyway. */
const CONNECT_WAIT_MS = 5000;

type Session = {
  /** Unknown while a call we place is still being set up. */
  callId: number | null;
  /** The call as last seen, so the card keeps its name whatever the list says. */
  call: Call | null;
  direction: "inbound" | "outbound";
  /** Who we are calling, before the call exists. */
  label?: { name: string; thumbnail?: string | null };
  audio: Omit<CallAudio, "answerSdp"> | null;
  /** inbound: connecting → live. outbound: dialing → calling → live. */
  phase: "connecting" | "dialing" | "calling" | "live";
  startedAt: number | null;
  muted: boolean;
  /** The customer's answer is in the browser (outbound). */
  answerApplied?: boolean;
};

function callerName(call: Call, fallback: string): string {
  return (
    call.contact?.name?.trim() ||
    call.contact?.phone_number ||
    call.from_number ||
    fallback
  );
}

function clock(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}

/** Whether a ringing call sounds for me. The backend says who: the people
 *  free, or everybody when nobody is. Without its word (an older backend,
 *  my profile still loading), as before: when I am not on a call. */
function ringsForMe(call: Call, me: number | undefined, busy: boolean): boolean {
  if (call.ring_user_ids === undefined || me === undefined) return !busy;
  return call.ring_user_ids.includes(me);
}

/** Our wording for what went wrong, by the code the backend sends. */
function problemKey(err: unknown): string {
  if (err instanceof MicrophoneBlocked) return "calls.problems.microphone";
  const code = (err as { body?: { code?: unknown } })?.body?.code;
  if (typeof code === "string" && code.startsWith("calls.")) {
    return `calls.problems.${code.slice(6)}`;
  }
  return "calls.problems.refused";
}

/**
 * Calls ringing in my inboxes and the call I am on, in a corner of every
 * page (F7). The audio lives here, so moving around the panel does not cut
 * the call; closing the tab hangs up.
 */
export function CallDock({ accountId }: { accountId: string }) {
  const t = useT();
  const qc = useQueryClient();
  const { data: calls = [] } = useActiveCalls(accountId);
  const me = useProfile().data?.id;
  const api = useRef(callApi(accountId));
  const speaker = useRef<HTMLAudioElement | null>(null);
  const [session, setSession] = useState<Session | null>(null);
  const sessionRef = useRef<Session | null>(null);
  const [ignored, setIgnored] = useState<number[]>([]);
  const [problem, setProblem] = useState<string | null>(null);
  // "calls.ended" / "calls.notAnswered": a call just closed.
  const [notice, setNotice] = useState<string | null>(null);
  const [, tick] = useState(0);

  useEffect(() => {
    api.current = callApi(accountId);
  }, [accountId]);

  const update = useCallback((next: Session | null) => {
    sessionRef.current = next;
    setSession(next);
  }, []);

  const finish = useCallback(
    (closing: string | null) => {
      sessionRef.current?.audio?.close();
      update(null);
      setNotice(closing);
    },
    [update],
  );

  // My call, watched on its own: the cable writes each change into it and a
  // poll catches an end whose event got lost (fast while it rings out).
  const watching = session && (session.phase === "live" || session.phase === "calling");
  const { data: watched } = useCall(
    accountId,
    watching ? session.callId : null,
    session?.phase === "calling",
  );
  const mine =
    (watched && watched.id === session?.callId ? watched : undefined) ??
    calls.find((c) => c.id === session?.callId) ??
    session?.call ??
    undefined;
  const busy = session !== null;
  const ringing = calls.filter(
    (c) =>
      c.status === "ringing" &&
      c.can_answer &&
      !ignored.includes(c.id) &&
      ringsForMe(c, me, busy),
  );

  // Ring while somebody calls me; softly while I am on another call (it only
  // rings for me then because nobody else is free).
  useEffect(() => {
    if (ringing.length === 0) return;
    return startRingtone(busy);
  }, [ringing.length, busy]);

  // The call ended on the other side (or another tab hung up).
  useEffect(() => {
    if (!session || !watched || watched.id !== session.callId) return;
    if (session.phase !== "live" && session.phase !== "calling") return;
    if (!ACTIVE_CALL_STATUSES.includes(watched.status)) {
      finish(session.phase === "calling" ? "calls.notAnswered" : "calls.ended");
    }
  }, [session, watched, finish]);

  // A call we placed: the customer's answer, then the pickup.
  useEffect(() => {
    const current = sessionRef.current;
    if (!current || current.direction !== "outbound" || !watched) return;
    if (watched.id !== current.callId) return;
    const audio = current.audio as OutgoingAudio | null;
    if (!audio) return;
    let next = current;
    if (watched.sdp_answer && !current.answerApplied) {
      next = { ...next, answerApplied: true };
      void audio.applyAnswer(watched.sdp_answer).catch(() => undefined);
    }
    if (current.phase === "calling" && watched.status === "in_progress") {
      audio.startSending();
      next = { ...next, phase: "live", startedAt: Date.now(), call: watched };
    }
    if (next !== current) update(next);
  }, [watched, update]);

  // The clock of the call.
  useEffect(() => {
    if (!session?.startedAt) return;
    const timer = setInterval(() => tick((n) => n + 1), 1000);
    return () => clearInterval(timer);
  }, [session?.startedAt]);

  // Leaving the page with a call on: warn, and hang up if they go.
  useEffect(() => {
    if (!session) return;
    const warn = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = "";
    };
    const leave = () => {
      const current = sessionRef.current;
      if (current?.callId) api.current.hangupOnUnload(current.callId);
    };
    window.addEventListener("beforeunload", warn);
    window.addEventListener("pagehide", leave);
    return () => {
      window.removeEventListener("beforeunload", warn);
      window.removeEventListener("pagehide", leave);
    };
  }, [session]);

  // Notices go away on their own.
  useEffect(() => {
    if (!problem && !notice) return;
    const timer = setTimeout(() => {
      setProblem(null);
      setNotice(null);
    }, 6000);
    return () => clearTimeout(timer);
  }, [problem, notice]);

  useEffect(() => () => sessionRef.current?.audio?.close(), []);

  async function answer(call: Call) {
    if (sessionRef.current || !speaker.current) return;
    setProblem(null);
    setNotice(null);
    const base = {
      callId: call.id,
      call,
      direction: "inbound",
      startedAt: null,
      muted: false,
    } as const;
    update({ ...base, audio: null, phase: "connecting" });
    let audio: CallAudio | null = null;
    try {
      const detail = await api.current.get(call.id);
      if (!detail.sdp_offer || detail.status !== "ringing") {
        throw { body: { code: "calls.over" } };
      }
      audio = await answerOffer(detail.sdp_offer, speaker.current);
      update({ ...base, call: detail, audio, phase: "connecting" });
      audio.onLost(() => {
        const current = sessionRef.current;
        if (current?.callId === call.id) {
          void api.current.hangup(call.id).catch(() => undefined);
          finish("calls.ended");
        }
      });
      await api.current.preAccept(call.id, audio.answerSdp);
      await audio.waitConnected(CONNECT_WAIT_MS);
      const live = await api.current.accept(call.id, audio.answerSdp);
      audio.startSending();
      qc.setQueryData(callKey(accountId, call.id), live);
      update({ ...base, call: live, audio, phase: "live", startedAt: Date.now() });
    } catch (err) {
      audio?.close();
      update(null);
      setProblem(problemKey(err));
    }
  }

  // Calling a customer, asked from anywhere (the conversation header).
  const dial = useCallback(
    async (request: DialRequest) => {
      if (!speaker.current) return;
      if (sessionRef.current) {
        setProblem("calls.problems.busy");
        return;
      }
      setProblem(null);
      setNotice(null);
      const start: Session = {
        callId: null,
        call: null,
        direction: "outbound",
        label: { name: request.contactName, thumbnail: request.thumbnail },
        audio: null,
        phase: "dialing",
        startedAt: null,
        muted: false,
      };
      update(start);
      // Read through a function: the ref changes under us (hang-up), which
      // TypeScript's narrowing cannot see.
      const now = () => sessionRef.current;
      let audio: OutgoingAudio | null = null;
      try {
        audio = await placeCall(speaker.current);
        if (now() !== start) {
          audio.close(); // hung up while the microphone was asked for
          return;
        }
        const ready: Session = { ...start, audio };
        update(ready);
        const placed = await api.current.place(request.conversationId, audio.offerSdp);
        if (now() !== ready) {
          // Hung up before Meta answered: end the call it just placed.
          void api.current.hangup(placed.id).catch(() => undefined);
          return;
        }
        qc.setQueryData(callKey(accountId, placed.id), placed);
        audio.onLost(() => {
          const current = sessionRef.current;
          if (current?.callId === placed.id) {
            void api.current.hangup(placed.id).catch(() => undefined);
            finish("calls.ended");
          }
        });
        update({ ...ready, callId: placed.id, call: placed, phase: "calling" });
      } catch (err) {
        audio?.close();
        const current = now();
        if (current?.direction === "outbound" && !current.callId) {
          update(null);
        }
        setProblem(problemKey(err));
      }
    },
    [accountId, finish, qc, update],
  );
  const dialRef = useRef(dial);
  dialRef.current = dial;
  useEffect(() => onDialRequest((request) => void dialRef.current(request)), []);

  async function hangup() {
    const current = sessionRef.current;
    if (!current) return;
    finish(null);
    if (current.callId) await api.current.hangup(current.callId).catch(() => undefined);
  }

  function toggleMute() {
    const current = sessionRef.current;
    if (!current?.audio) return;
    const muted = !current.muted;
    current.audio.setMuted(muted);
    update({ ...current, muted });
  }

  const unknown = t("calls.unknownCaller");
  const showPanel = Boolean(session) || ringing.length > 0 || problem || notice;

  return (
    <>
      {/* The other side's voice. Always mounted, so it can play at once. */}
      <audio ref={speaker} autoPlay className="hidden" />
      {showPanel ? (
        <div
          className="fixed bottom-4 right-4 z-50 flex w-[min(340px,calc(100vw-32px))] flex-col gap-2"
          aria-live="polite"
        >
          {session ? (
            <ActiveCallCard
              accountId={accountId}
              call={mine}
              session={session}
              unknown={unknown}
              onHangup={hangup}
              onToggleMute={toggleMute}
            />
          ) : null}
          {ringing.map((call) => (
            <div
              key={call.id}
              role="dialog"
              aria-label={t("calls.incoming")}
              className="glass-panel flex flex-col gap-3 rounded-panel border border-glass bg-surface p-3 shadow-lg"
            >
              <div className="flex items-center gap-3">
                <span className="relative shrink-0">
                  <Avatar
                    name={callerName(call, unknown)}
                    src={call.contact?.thumbnail}
                    size="lg"
                  />
                  <span className="absolute -inset-1 animate-ping rounded-full border-2 border-success opacity-40 motion-reduce:hidden" />
                </span>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium text-fg">
                    {callerName(call, unknown)}
                  </p>
                  <p className="truncate text-xs text-fg-muted">
                    {t("calls.incomingFrom", { inbox: call.inbox_name ?? "WhatsApp" })}
                  </p>
                </div>
              </div>
              <div className="flex gap-2">
                <Button
                  variant="secondary"
                  size="sm"
                  className="flex-1"
                  onClick={() => setIgnored((ids) => [...ids, call.id])}
                  title={t("calls.ignoreHint")}
                >
                  {t("calls.ignore")}
                </Button>
                <Button
                  size="sm"
                  onClick={() => void answer(call)}
                  disabled={busy}
                  aria-label={t("calls.answer")}
                  className="flex-1 bg-success text-white"
                >
                  <Phone className="h-4 w-4" aria-hidden />
                  {t("calls.answer")}
                </Button>
              </div>
              {busy ? <p className="text-xs text-fg-muted">{t("calls.waiting")}</p> : null}
            </div>
          ))}
          {problem ? (
            <p
              role="alert"
              className="glass-panel rounded-panel border border-glass bg-surface p-3 text-sm text-danger shadow-lg"
            >
              {translateOr(t, problem, t("calls.problems.refused"))}
            </p>
          ) : null}
          {notice && !session ? (
            <p className="glass-panel rounded-panel border border-glass bg-surface p-3 text-sm text-fg-muted shadow-lg">
              {translateOr(t, notice, t("calls.ended"))}
            </p>
          ) : null}
        </div>
      ) : null}
    </>
  );
}

function ActiveCallCard({
  accountId,
  call,
  session,
  unknown,
  onHangup,
  onToggleMute,
}: {
  accountId: string;
  call: Call | undefined;
  session: Session;
  unknown: string;
  onHangup: () => void;
  onToggleMute: () => void;
}) {
  const t = useT();
  const name = call ? callerName(call, unknown) : (session.label?.name ?? unknown);
  const elapsed = session.startedAt
    ? Math.max(0, Math.floor((Date.now() - session.startedAt) / 1000))
    : 0;
  const href =
    call?.conversation_display_id != null
      ? `/accounts/${accountId}/conversations/${call.conversation_display_id}`
      : null;
  return (
    <div
      role="region"
      aria-label={t("calls.onCall")}
      className="glass-panel flex flex-col gap-3 rounded-panel border border-glass bg-surface p-3 shadow-lg"
    >
      <div className="flex items-center gap-3">
        <Avatar
          name={name}
          src={call?.contact?.thumbnail ?? session.label?.thumbnail ?? undefined}
          size="lg"
        />
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium text-fg">{name}</p>
          <p
            className={cn(
              "text-xs",
              session.phase === "live" ? "font-numeric tabular-nums text-success" : "text-fg-muted",
            )}
          >
            {session.phase === "live"
              ? clock(elapsed)
              : session.phase === "dialing"
                ? t("calls.preparing")
                : session.phase === "calling"
                  ? t("calls.calling")
                  : t("calls.connecting")}
          </p>
        </div>
        {href ? (
          <Link
            href={href}
            className="text-xs text-lit underline-offset-2 hover:underline"
          >
            {t("calls.openConversation")}
          </Link>
        ) : null}
      </div>
      <div className="flex gap-2">
        <Button
          variant="secondary"
          size="sm"
          className="flex-1"
          onClick={onToggleMute}
          disabled={session.phase !== "live"}
          aria-pressed={session.muted}
        >
          {session.muted ? (
            <MicOff className="h-4 w-4" aria-hidden />
          ) : (
            <Mic className="h-4 w-4" aria-hidden />
          )}
          {session.muted ? t("calls.unmute") : t("calls.mute")}
        </Button>
        <Button variant="destructive" size="sm" className="flex-1" onClick={onHangup}>
          <PhoneOff className="h-4 w-4" aria-hidden />
          {t("calls.hangup")}
        </Button>
      </div>
    </div>
  );
}
