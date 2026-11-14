"use client";

import { Phone, PhoneIncoming, PhoneMissed } from "lucide-react";

import type { Message } from "@/lib/api/conversations";
import { useT } from "@/lib/i18n/provider";
import { cn } from "@/lib/utils";

/** The state of a call as the conversation keeps it (Chatwoot's names). */
type CallData = {
  status?: string;
  duration?: number | null;
  answered_by?: { id: number; name: string } | null;
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
    const status = callData(message).status;
    if (status === "no-answer" || status === "failed") return t("calls.bubble.missed");
    return t("calls.bubble.incoming");
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

  const title = missed
    ? t("calls.bubble.missed")
    : live
      ? t("calls.bubble.inProgress")
      : ringing
        ? t("calls.bubble.ringing")
        : t("calls.bubble.incoming");
  let detail: string;
  if (missed) {
    detail = status === "failed" ? t("calls.bubble.failed") : t("calls.bubble.noAnswer");
  } else if (ringing) {
    detail = t("calls.bubble.notAnsweredYet");
  } else if (data.answered_by?.name) {
    detail =
      !live && typeof data.duration === "number"
        ? t("calls.bubble.answeredFor", {
            name: data.answered_by.name,
            length: length(data.duration),
          })
        : t("calls.bubble.answeredBy", { name: data.answered_by.name });
  } else {
    detail = t("calls.bubble.ended");
  }

  const Icon = missed ? PhoneMissed : live ? Phone : PhoneIncoming;
  return (
    <div className="flex min-w-[200px] items-center gap-3" data-testid="voice-call">
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
  );
}
