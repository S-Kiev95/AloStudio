"use client";

import { Bot, Users } from "lucide-react";

import { Button } from "@/components/ui/button";
import { type ThreadControl, useThreadControl } from "@/lib/api/conversations";
import { cn } from "@/lib/utils";

/** Who is answering a WhatsApp chat on a number run by Meta Business Agent.
 *
 *  Only rendered once the conversation has a thread owner, so inboxes
 *  without Meta's AI never see it. While the AI answers, the team can
 *  read along and take over; once the team owns it, they can hand it back
 *  (resolving usually does that too). Replying while the AI owns the
 *  chat also takes it over, which the hint says before anyone types. */
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
  if (!control) return null;
  const aiAnswering = control.owner === "ai_agent";

  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-2 border-b border-glass py-2">
      <span
        className={cn(
          "flex h-8 w-8 shrink-0 items-center justify-center rounded-full",
          aiAnswering
            ? "bg-electrode/15 text-electrode"
            : "bg-success/10 text-success",
        )}
        aria-hidden
      >
        {aiAnswering ? <Bot className="h-4 w-4" /> : <Users className="h-4 w-4" />}
      </span>
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium text-fg">
          {aiAnswering ? "Responde la IA de Meta" : "Atiende el equipo"}
        </p>
        <p className="text-xs text-fg-muted">
          {aiAnswering
            ? "Si respondés, la conversación pasa al equipo."
            : control.metadata
              ? `La IA la derivó: ${control.metadata}`
              : "Podés devolverla a la IA cuando termines."}
        </p>
        {mutation.isError ? (
          <p role="alert" className="mt-1 text-xs text-danger">
            {mutation.error.message}
          </p>
        ) : null}
      </div>
      <Button
        variant={aiAnswering ? "primary" : "ai"}
        size="sm"
        loading={mutation.isPending}
        onClick={() => mutation.mutate(aiAnswering ? "take" : "release")}
      >
        {aiAnswering ? "Tomar conversación" : "Devolver a la IA"}
      </Button>
    </div>
  );
}
