"use client";

import { useState } from "react";

import {
  handoffProblemKey,
  targetFromValue,
  targetValue,
  useContactHandoff,
  useSaveContactHandoff,
} from "@/lib/api/handoff";
import { useIsAccountAdmin } from "@/lib/api/profile";
import { useT } from "@/lib/i18n/provider";
import { translateOr } from "@/lib/i18n/translate";

import { HandoffTargetSelect } from "./target-select";

/** The chat's handoff responsible, in the contact panel: it beats labels,
 *  the inbox and the account for every handoff of this contact. Only
 *  administrators see it (the rules are theirs). */
export function ContactHandoff({ accountId, contactId }: { accountId: string; contactId: number }) {
  const t = useT();
  const isAdmin = useIsAccountAdmin(accountId);
  const rule = useContactHandoff(accountId, contactId, isAdmin);
  const save = useSaveContactHandoff(accountId, contactId);
  const [problem, setProblem] = useState<string | null>(null);

  if (!isAdmin || !rule.data) return null;
  const id = `contact-handoff-${contactId}`;

  async function change(value: string) {
    setProblem(null);
    try {
      await save.mutateAsync(targetFromValue(value));
    } catch (err) {
      setProblem(handoffProblemKey(err));
    }
  }

  return (
    <div className="space-y-1.5 border-t border-glass pt-4">
      <label
        htmlFor={id}
        className="block text-[11px] font-medium uppercase tracking-wide text-fg-muted"
      >
        {t("handoff.contact.title")}
      </label>
      <HandoffTargetSelect
        id={id}
        accountId={accountId}
        aiAvailable={rule.data.ai_available}
        emptyLabel={t("handoff.contact.byRules")}
        value={targetValue(rule.data.contact)}
        disabled={save.isPending}
        onChange={(e) => void change(e.target.value)}
      />
      <p className="text-xs text-fg-muted">{t("handoff.contact.hint")}</p>
      {problem ? (
        <p role="alert" className="text-xs text-danger">
          {translateOr(t, problem, t("handoff.problems.failed"))}
        </p>
      ) : null}
    </div>
  );
}
