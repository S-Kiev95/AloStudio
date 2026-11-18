"use client";

import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/select";
import { useAgentBots, useInboxAgentBot, useSetAgentBot } from "@/lib/api/agent-bots";
import { ApiError } from "@/lib/api/errors";
import { useT } from "@/lib/i18n/provider";

/** Which bot answers this inbox's customers: AloStudio's AI (agente-ia,
 *  2b) or a webhook bot. One per inbox; "Ninguno" detaches it. */
export function InboxBotPanel({ accountId, inboxId }: { accountId: string; inboxId: number }) {
  const t = useT();
  const bots = useAgentBots(accountId);
  const current = useInboxAgentBot(accountId, inboxId);
  const save = useSetAgentBot(accountId);
  const [value, setValue] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  const currentId = current.data?.agent_bot?.id;
  useEffect(() => {
    setValue(currentId ? String(currentId) : "");
  }, [currentId]);

  async function submit() {
    setError(null);
    setSaved(false);
    try {
      await save.mutateAsync({ inbox_id: inboxId, agent_bot: value ? Number(value) : null });
      setSaved(true);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : t("aiAgent.saveFailed"));
    }
  }

  return (
    <div className="space-y-3">
      <p className="text-sm text-fg-muted">{t("aiAgent.inboxBotIntro")}</p>
      <label className="block space-y-1">
        <span className="text-sm font-medium text-fg">{t("aiAgent.inboxBotLabel")}</span>
        <Select
          value={value}
          disabled={bots.isLoading || current.isLoading}
          onChange={(e) => {
            setValue(e.target.value);
            setSaved(false);
          }}
          className="max-w-xs"
        >
          <option value="">{t("aiAgent.none")}</option>
          {(bots.data ?? []).map((b) => (
            <option key={b.id} value={String(b.id)}>
              {b.bot_type === "ai" ? `${b.name} (${t("aiAgent.tag")})` : b.name}
            </option>
          ))}
        </Select>
      </label>
      {error ? (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      ) : null}
      <div className="flex items-center gap-2">
        <Button size="sm" onClick={submit} loading={save.isPending}>
          {t("actions.save")}
        </Button>
        {saved ? <span className="text-xs text-success">{t("aiAgent.saved")}</span> : null}
      </div>
    </div>
  );
}
