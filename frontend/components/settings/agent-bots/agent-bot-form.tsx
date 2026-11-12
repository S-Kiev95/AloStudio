"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import type { AgentBot, AgentBotInput } from "@/lib/api/agent-bots";
import { useT } from "@/lib/i18n/provider";

export function AgentBotForm({
  initial,
  submitting,
  onSubmit,
  onCancel,
}: {
  initial?: AgentBot;
  submitting?: boolean;
  onSubmit: (input: AgentBotInput) => Promise<void> | void;
  onCancel: () => void;
}) {
  const t = useT();
  const [name, setName] = useState(initial?.name ?? "");
  const [description, setDescription] = useState(initial?.description ?? "");
  const [outgoingUrl, setOutgoingUrl] = useState(initial?.outgoing_url ?? "");
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    setError(null);
    if (!name.trim()) return setError(t("profile.nameRequired"));
    try {
      await onSubmit({
        name: name.trim(),
        description: description.trim() || null,
        outgoing_url: outgoingUrl.trim() || null,
      });
    } catch (e) {
      setError(
        (e as { message?: string })?.message ?? t("settingsBots.saveFailed"),
      );
    }
  }

  return (
    <div className="space-y-4">
      {error ? (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      ) : null}

      <div className="space-y-1.5">
        <Label htmlFor="ab-name" required>
          {t("profile.name")}
        </Label>
        <Input
          id="ab-name"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="ab-desc">{t("products.description")}</Label>
        <Textarea
          id="ab-desc"
          rows={2}
          value={description ?? ""}
          onChange={(e) => setDescription(e.target.value)}
        />
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="ab-url">{t("settingsBots.outgoingUrl")}</Label>
        <Input
          id="ab-url"
          type="url"
          value={outgoingUrl ?? ""}
          onChange={(e) => setOutgoingUrl(e.target.value)}
          placeholder="https://…"
        />
        <p className="text-xs text-fg-muted">
          {t("settingsBots.outgoingUrlHint")}
        </p>
      </div>

      <div className="flex gap-2">
        <Button onClick={submit} loading={submitting}>
          {initial ? t("common.saveChanges") : t("settingsBots.create")}
        </Button>
        <Button variant="ghost" onClick={onCancel} disabled={submitting}>
          {t("actions.cancel")}
        </Button>
      </div>
    </div>
  );
}
