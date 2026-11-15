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
import { useT } from "@/lib/i18n/provider";
import { translateOr } from "@/lib/i18n/translate";
import { cn } from "@/lib/utils";

import { answerOffer, type CallAudio, MicrophoneBlocked, startRingtone } from "./call-audio";

/** How long to wait for the audio path before confirming anyway. */
const CONNECT_WAIT_MS = 5000;

type Session = {
  callId: number;
  /** The call as last seen, so the card keeps its name whatever the list says. */
  call: Call;
  audio: CallAudio | null;
  phase: "connecting" | "live";
  startedAt: number | null;
  muted: boolean;
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
  const api = useRef(callApi(accountId));
  const speaker = useRef<HTMLAudioElement | null>(null);
  const [session, setSession] = useState<Session | null>(null);
  const sessionRef = useRef<Session | null>(null);
  const [ignored, setIgnored] = useState<number[]>([]);
  const [problem, setProblem] = useState<string | null>(null);
  const [ended, setEnded] = useState(false);
  const [, tick] = useState(0);

  useEffect(() => {
    api.current = callApi(accountId);
  }, [accountId]);

  const update = useCallback((next: Session | null) => {
    sessionRef.current = next;
    setSession(next);
  }, []);

  const finish = useCallback(
    (endedNotice: boolean) => {
      sessionRef.current?.audio?.close();
      update(null);
      setEnded(endedNotice);
    },
    [update],
  );

  // My call, watched on its own: the cable writes each change into it and a
  // poll catches an end whose event got lost.
  const { data: watched } = useCall(accountId, session?.phase === "live" ? session.callId : null);
  const mine =
    (watched && watched.id === session?.callId ? watched : undefined) ??
    calls.find((c) => c.id === session?.callId) ??
    session?.call;
  const ringing = calls.filter(
    (c) => c.status === "ringing" && c.can_answer && !ignored.includes(c.id),
  );
  const otherRinging = session ? [] : ringing;

  // Ring while somebody calls and I am free.
  useEffect(() => {
    if (otherRinging.length === 0) return;
    return startRingtone();
  }, [otherRinging.length]);

  // The call ended on the other side (or another tab hung up).
  useEffect(() => {
    if (!session || session.phase !== "live" || !watched) return;
    if (watched.id === session.callId && !ACTIVE_CALL_STATUSES.includes(watched.status)) {
      finish(true);
    }
  }, [session, watched, finish]);

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
      if (current) api.current.hangupOnUnload(current.callId);
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
    if (!problem && !ended) return;
    const timer = setTimeout(() => {
      setProblem(null);
      setEnded(false);
    }, 6000);
    return () => clearTimeout(timer);
  }, [problem, ended]);

  useEffect(() => () => sessionRef.current?.audio?.close(), []);

  async function answer(call: Call) {
    if (sessionRef.current || !speaker.current) return;
    setProblem(null);
    setEnded(false);
    const base = { callId: call.id, call, startedAt: null, muted: false } as const;
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
          finish(true);
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

  async function hangup() {
    const current = sessionRef.current;
    if (!current) return;
    finish(false);
    await api.current.hangup(current.callId).catch(() => undefined);
  }

  function toggleMute() {
    const current = sessionRef.current;
    if (!current?.audio) return;
    const muted = !current.muted;
    current.audio.setMuted(muted);
    update({ ...current, muted });
  }

  const unknown = t("calls.unknownCaller");
  const showPanel = Boolean(session) || otherRinging.length > 0 || problem || ended;

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
          {otherRinging.map((call) => (
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
                  aria-label={t("calls.answer")}
                  className="flex-1 bg-success text-white"
                >
                  <Phone className="h-4 w-4" aria-hidden />
                  {t("calls.answer")}
                </Button>
              </div>
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
          {ended && !session ? (
            <p className="glass-panel rounded-panel border border-glass bg-surface p-3 text-sm text-fg-muted shadow-lg">
              {t("calls.ended")}
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
  const name = call ? callerName(call, unknown) : unknown;
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
        <Avatar name={name} src={call?.contact?.thumbnail} size="lg" />
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium text-fg">{name}</p>
          <p
            className={cn(
              "text-xs",
              session.phase === "live" ? "font-numeric tabular-nums text-success" : "text-fg-muted",
            )}
          >
            {session.phase === "live" ? clock(elapsed) : t("calls.connecting")}
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
