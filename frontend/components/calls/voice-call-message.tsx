"use client";

import {
  ChevronDown,
  Phone,
  PhoneCall,
  PhoneIncoming,
  PhoneMissed,
  PhoneOff,
  PhoneOutgoing,
} from "lucide-react";
import { useState } from "react";

import type { Message } from "@/lib/api/conversations";
import { useT } from "@/lib/i18n/provider";
import { cn } from "@/lib/utils";

/** The state of a call as the conversation keeps it (Chatwoot's names). */
type CallData = {
  status?: string;
  call_direction?: "inbound" | "outbound";
  duration?: number | null;
  answered_by?: { id: number; name: string } | null;
  /** "pending" while Meta prepares it, "ready" once it is in AloStudio. */
  recording?: "pending" | "ready" | null;
  transcription?: "pending" | "ready" | null;
  transcript?: Array<{ speaker: "business" | "customer"; text: string }> | null;
};

export function isVoiceCallMessage(message: Pick<Message, "content_type">): boolean {
  return message.content_type === "voice_call";
}

function callData(message: Message): CallData {
  const data = message.content_attributes?.data;
  return data && typeof data === "object" ? (data as CallData) : {};
}

function length(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}

/** What a call says in the conversation list. */
export function useVoiceCallPreview(): (message: Message) => string {
  const t = useT();
  return (message) => {
    const data = callData(message);
    const missed = data.status === "no-answer" || data.status === "failed";
    if (data.call_direction === "outbound") {
      return missed ? t("calls.bubble.notAnswered") : t("calls.bubble.outgoing");
    }
    return missed ? t("calls.bubble.missed") : t("calls.bubble.incoming");
  };
}

/** A WhatsApp call inside the conversation: ringing, on, over or missed. */
export function VoiceCallMessage({ message }: { message: Message }) {
  const t = useT();
  const data = callData(message);
  const status = data.status ?? "ringing";
  const missed = status === "no-answer" || status === "failed";
  const ringing = status === "ringing";
  const live = status === "in-progress";
  const outbound = data.call_direction === "outbound";
  const agent = data.answered_by?.name;

  let title: string;
  let detail: string;
  if (outbound) {
    // A call an agent made: answered_by is who called.
    title = missed
      ? t("calls.bubble.notAnswered")
      : live
        ? t("calls.bubble.inProgress")
        : ringing
          ? t("calls.bubble.calling")
          : t("calls.bubble.outgoing");
    if (missed && status === "failed") detail = t("calls.bubble.failed");
    else if (agent && !live && !ringing && !missed && typeof data.duration === "number") {
      detail = t("calls.bubble.calledFor", { name: agent, length: length(data.duration) });
    } else detail = agent ? t("calls.bubble.calledBy", { name: agent }) : t("calls.bubble.ended");
  } else {
    title = missed
      ? t("calls.bubble.missed")
      : live
        ? t("calls.bubble.inProgress")
        : ringing
          ? t("calls.bubble.ringing")
          : t("calls.bubble.incoming");
    if (missed) {
      detail = status === "failed" ? t("calls.bubble.failed") : t("calls.bubble.noAnswer");
    } else if (ringing) {
      detail = t("calls.bubble.notAnsweredYet");
    } else if (agent) {
      detail =
        !live && typeof data.duration === "number"
          ? t("calls.bubble.answeredFor", { name: agent, length: length(data.duration) })
          : t("calls.bubble.answeredBy", { name: agent });
    } else {
      detail = t("calls.bubble.ended");
    }
  }

  const Icon = missed
    ? outbound
      ? PhoneOff
      : PhoneMissed
    : live
      ? Phone
      : outbound
        ? PhoneOutgoing
        : PhoneIncoming;
  const pending =
    data.recording === "pending" || data.transcription === "pending"
      ? t("calls.bubble.processing")
      : null;
  return (
    <div className="flex min-w-[200px] flex-col gap-2" data-testid="voice-call">
    <div className="flex items-center gap-3">
      <span
        className={cn(
          "flex h-9 w-9 shrink-0 items-center justify-center rounded-full",
          missed
            ? "bg-danger-solid text-white"
            : live || ringing
              ? "bg-success text-white"
              : "bg-surface text-fg-muted",
          ringing && "motion-safe:animate-pulse",
        )}
      >
        <Icon className="h-4 w-4" aria-hidden />
      </span>
      <span className="min-w-0">
        <span className="block truncate text-sm font-medium">{title}</span>
        <span className="block text-xs opacity-80">{detail}</span>
      </span>
    </div>
      {pending ? <span className="text-xs opacity-80">{pending}</span> : null}
      {data.transcript?.length ? <Transcript lines={data.transcript} /> : null}
    </div>
  );
}

/** What was said, folded until asked for. */
function Transcript({
  lines,
}: {
  lines: Array<{ speaker: "business" | "customer"; text: string }>;
}) {
  const t = useT();
  const [open, setOpen] = useState(false);
  return (
    <div className="text-xs">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="inline-flex items-center gap-1 font-medium underline-offset-2 hover:underline"
      >
        <ChevronDown
          className={cn("h-3.5 w-3.5 transition-transform", open && "rotate-180")}
          aria-hidden
        />
        {open ? t("calls.bubble.hideTranscript") : t("calls.bubble.showTranscript")}
      </button>
      {open ? (
        <dl className="mt-2 max-h-72 space-y-1.5 overflow-y-auto pr-1">
          {lines.map((line, i) => (
            <div key={i}>
              <dt className="inline font-medium">
                {line.speaker === "business"
                  ? t("calls.bubble.speakerBusiness")
                  : t("calls.bubble.speakerCustomer")}
                :{" "}
              </dt>
              <dd className="inline whitespace-pre-wrap break-words">{line.text}</dd>
            </div>
          ))}
        </dl>
      ) : null}
    </div>
  );
}

/** The permission to call: the business asking, or the customer's answer. */
type PermissionData = {
  response?: "accept" | "reject";
  permanent?: boolean;
  automatic?: boolean;
};

export function isCallPermissionMessage(message: Message): boolean {
  const attrs = message.content_attributes ?? {};
  return attrs.call_permission_request === true || typeof attrs.call_permission === "object";
}

/** Shown in the chat in the reader's language, whatever text was stored. */
export function CallPermissionNote({ message }: { message: Message }) {
  const t = useT();
  const attrs = message.content_attributes ?? {};
  if (attrs.call_permission_request === true) {
    return (
      <span className="flex flex-col gap-1">
        <span className="flex items-center gap-1.5 text-xs font-medium opacity-85">
          <PhoneCall className="h-3.5 w-3.5" aria-hidden />
          {t("calls.bubble.permissionRequest")}
        </span>
        {message.content ? (
          <span className="whitespace-pre-wrap break-words">{message.content}</span>
        ) : null}
      </span>
    );
  }
  const data = (attrs.call_permission ?? {}) as PermissionData;
  const text =
    data.response !== "accept"
      ? t("calls.bubble.permissionRejected")
      : data.permanent
        ? t("calls.bubble.permissionAlways")
        : data.automatic
          ? t("calls.bubble.permissionByCalling")
          : t("calls.bubble.permissionAccepted");
  return (
    <span className="flex items-center gap-1.5">
      {data.response === "accept" ? (
        <PhoneCall className="h-4 w-4 shrink-0 text-success" aria-hidden />
      ) : (
        <PhoneOff className="h-4 w-4 shrink-0 text-danger" aria-hidden />
      )}
      <span>{text}</span>
    </span>
  );
}
