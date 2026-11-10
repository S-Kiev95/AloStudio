"use client";

import { Meta } from "@/components/ui/brand-icons";
import { Button } from "@/components/ui/button";
import { type ThreadControl, useThreadControl } from "@/lib/api/conversations";

/** A person at the desk: headset and collar, a rounded line over a soft fill. */
function SecretaryIcon({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.7}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden
    >
      <g fill="currentColor" fillOpacity={0.2} stroke="none">
        <circle cx="12" cy="9" r="3.5" />
        <path d="M4.5 21a7.5 7.5 0 0 1 15 0z" />
      </g>
      <circle cx="12" cy="9" r="3.5" />
      <path d="M4.5 21a7.5 7.5 0 0 1 15 0" />
      <path d="M9.5 14.2 12 17l2.5-2.8" />
      <path d="M6.5 10V8.5a5.5 5.5 0 0 1 11 0V10" />
      <path d="M17.5 10a2.5 2.5 0 0 1-2.5 2.5" />
    </svg>
  );
}

export type ThreadControlDescription = {
  aiAnswering: boolean;
  title: string;
  detail: string;
  summary: string;
  actionLabel: string;
  action: "take" | "release";
};

export function describeThreadControl(
  control?: ThreadControl | null,
): ThreadControlDescription | null {
  if (!control) return null;
  const aiAnswering = control.owner === "ai_agent";
  const handoff =
    !aiAnswering && control.metadata
      ? `La IA la derivó: ${control.metadata}`
      : null;
  const title = aiAnswering ? "Responde la IA de Meta" : "Atiende el equipo";
  return {
    aiAnswering,
    title,
    detail: aiAnswering
      ? "Si respondés, la conversación pasa al equipo."
      : (handoff ?? "Podés devolverla a la IA cuando termines."),
    summary: aiAnswering ? title : (handoff ?? title),
    actionLabel: aiAnswering ? "Tomar conversación" : "Devolver a la IA",
    action: aiAnswering ? "take" : "release",
  };
}

/** Who is answering a WhatsApp chat on a number run by Meta Business Agent.
 *
 *  Only rendered once the conversation has a thread owner, so inboxes
 *  without Meta's AI never see it. While the AI answers, the team can
 *  read along and take over; once the team owns it, they can hand it back
 *  (resolving usually does that too). Replying while the AI owns the
 *  chat also takes it over, which the hint says before anyone types.
 *  The button shows who has it now: the Meta logo or the person at the desk. */
export function AiHandoff({
  accountId,
  displayId,
  control,
}: {
  accountId: string;
  displayId: number;
  control?: ThreadControl | null;
}) {
  const mutation = useThreadControl(accountId, displayId);
  const info = describeThreadControl(control);
  if (!info) return null;

  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-2 border-b border-glass px-4 py-2">
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium text-fg">{info.title}</p>
        <p className="text-xs text-fg-muted">{info.detail}</p>
        {mutation.isError ? (
          <p role="alert" className="mt-1 text-xs text-danger">
            {mutation.error.message}
          </p>
        ) : null}
      </div>
      <Button
        variant="secondary"
        size="icon"
        loading={mutation.isPending}
        aria-label={info.actionLabel}
        title={info.actionLabel}
        onClick={() => mutation.mutate(info.action)}
      >
        {mutation.isPending ? null : info.aiAnswering ? (
          <Meta className="h-5 w-5" aria-hidden />
        ) : (
          <SecretaryIcon className="h-5 w-5" />
        )}
      </Button>
    </div>
  );
}
