"use client";

import { useState } from "react";

import { Select } from "@/components/ui/select";
import {
  lifecycleProblemKey,
  useContactStage,
  useLifecycleSettings,
  useSetContactStage,
} from "@/lib/api/lifecycle";
import { useIntlTag, useT } from "@/lib/i18n/provider";
import { translateOr } from "@/lib/i18n/translate";

const NONE = "";

/** The contact's lifecycle stage, changeable in place (F17). Nothing while
 *  the account does not use stages. ``conversationId`` (its number) leaves a
 *  line in that chat. */
export function ContactStage({
  accountId,
  contactId,
  conversationId,
  compact = false,
}: {
  accountId: string;
  contactId: number;
  conversationId?: number;
  compact?: boolean;
}) {
  const t = useT();
  const tag = useIntlTag();
  const settings = useLifecycleSettings(accountId);
  const enabled = settings.data?.enabled === true;
  const current = useContactStage(accountId, contactId, enabled);
  const move = useSetContactStage(accountId, contactId);
  const [problem, setProblem] = useState<string | null>(null);

  if (!enabled || !settings.data) return null;
  const stages = settings.data.stages;
  const now = current.data?.stage?.key ?? NONE;
  const when = current.data?.changed_at
    ? new Intl.DateTimeFormat(tag, { dateStyle: "medium" }).format(new Date(current.data.changed_at))
    : null;
  const id = `contact-stage-${contactId}`;

  async function change(key: string) {
    setProblem(null);
    try {
      await move.mutateAsync({
        stage_key: key || null,
        ...(conversationId !== undefined ? { conversation_id: conversationId } : {}),
      });
    } catch (err) {
      setProblem(lifecycleProblemKey(err));
    }
  }

  return (
    <div className={compact ? "space-y-1.5" : "space-y-1.5 border-t border-glass pt-4"}>
      <label
        htmlFor={id}
        className="block text-[11px] font-medium uppercase tracking-wide text-fg-muted"
      >
        {t("lifecycle.stage")}
      </label>
      <Select
        id={id}
        value={now}
        disabled={move.isPending || current.isLoading}
        onChange={(e) => void change(e.target.value)}
      >
        <option value={NONE}>{t("lifecycle.noStage")}</option>
        <optgroup label={t("lifecycle.stages")}>
          {stages
            .filter((s) => s.kind === "stage")
            .map((s) => (
              <option key={s.key} value={s.key}>
                {`${s.emoji} ${s.name}`.trim()}
              </option>
            ))}
        </optgroup>
        {stages.some((s) => s.kind === "lost") ? (
          <optgroup label={t("lifecycle.lostStages")}>
            {stages
              .filter((s) => s.kind === "lost")
              .map((s) => (
                <option key={s.key} value={s.key}>
                  {`${s.emoji} ${s.name}`.trim()}
                </option>
              ))}
          </optgroup>
        ) : null}
      </Select>
      {when ? (
        <p className="text-xs text-fg-muted">
          {current.data?.changed_by
            ? t("lifecycle.changedBy", { name: current.data.changed_by.name, date: when })
            : t("lifecycle.changedOn", { date: when })}
        </p>
      ) : null}
      {problem ? (
        <p role="alert" className="text-xs text-danger">
          {translateOr(t, problem, t("lifecycle.problems.failed"))}
        </p>
      ) : null}
    </div>
  );
}
