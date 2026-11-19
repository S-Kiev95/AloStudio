"use client";

import { Sparkles } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { useAiSuggestion, useDiscardAiSuggestion } from "@/lib/api/ai-reply";
import { useT } from "@/lib/i18n/provider";

/** The answer AloStudio's AI proposes in shadow mode (agente-ia, 2b), above
 *  the composer. "Usar" puts it in the box to edit and send; "Descartar"
 *  drops it. Hidden while the one in the box is this suggestion. */
export function AiSuggestion({
  accountId,
  displayId,
  inUseId,
  onUse,
}: {
  accountId: string;
  displayId: number;
  inUseId: number | null;
  onUse: (text: string, id: number) => void;
}) {
  const t = useT();
  const suggestion = useAiSuggestion(accountId, displayId);
  const discard = useDiscardAiSuggestion(accountId, displayId);
  const [failed, setFailed] = useState(false);
  const s = suggestion.data;
  if (!s || s.id === inUseId || (!s.content && !s.summary && !s.actions?.length)) return null;

  return (
    <div
      role="region"
      aria-label={t("aiAgent.suggestion")}
      className="mb-2 space-y-2 rounded-md border border-glass bg-surface-2 p-3"
    >
      <p className="flex items-center gap-1.5 text-xs font-semibold text-lit">
        <Sparkles className="h-3.5 w-3.5" aria-hidden />
        {s.handoff ? t("aiAgent.suggestionHandoff") : t("aiAgent.suggestion")}
      </p>
      {s.content ? <p className="whitespace-pre-wrap text-sm text-fg">{s.content}</p> : null}
      {s.summary ? <p className="whitespace-pre-wrap text-xs text-fg-muted">{s.summary}</p> : null}
      {s.actions?.length ? (
        <div className="text-xs text-fg-muted">
          <p className="font-medium">{t("aiAgent.suggestionActions")}</p>
          <ul className="list-disc pl-4">
            {s.actions.map((a, i) => (
              <li key={i}>{a}</li>
            ))}
          </ul>
        </div>
      ) : null}
      {failed ? (
        <p role="alert" className="text-xs text-danger">
          {t("aiAgent.discardFailed")}
        </p>
      ) : null}
      <div className="flex gap-2">
        {s.content ? (
          <Button size="sm" onClick={() => onUse(s.content ?? "", s.id)}>
            {t("aiAgent.use")}
          </Button>
        ) : null}
        <Button
          size="sm"
          variant="ghost"
          loading={discard.isPending}
          onClick={() => {
            setFailed(false);
            discard.mutate(s.id, { onError: () => setFailed(true) });
          }}
        >
          {t("aiAgent.discard")}
        </Button>
      </div>
    </div>
  );
}
