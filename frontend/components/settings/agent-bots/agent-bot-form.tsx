"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import {
  type AgentBot,
  type AgentBotInput,
  type AiBotMode,
  type AiBotRespondWhen,
  aiBotConfig,
} from "@/lib/api/agent-bots";
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
  // The type is chosen on create; AloStudio's AI has its own settings.
  const [kind, setKind] = useState<"webhook" | "ai">(initial?.bot_type ?? "webhook");
  const startConfig = aiBotConfig(initial);
  const [instructions, setInstructions] = useState(startConfig.instructions);
  const [mode, setMode] = useState<AiBotMode>(startConfig.mode);
  const [respondWhen, setRespondWhen] = useState<AiBotRespondWhen>(startConfig.respond_when);
  const [error, setError] = useState<string | null>(null);
  const ai = kind === "ai";

  async function submit() {
    setError(null);
    if (!name.trim()) return setError(t("profile.nameRequired"));
    try {
      await onSubmit({
        name: name.trim(),
        description: description.trim() || null,
        ...(ai
          ? {
              bot_config: {
                instructions: instructions.trim(),
                mode,
                respond_when: respondWhen,
              },
            }
          : { outgoing_url: outgoingUrl.trim() || null }),
        ...(initial ? {} : { bot_type: kind }),
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

      {!initial ? (
        <div className="space-y-1.5">
          <Label htmlFor="ab-type">{t("aiAgent.typeLabel")}</Label>
          <Select
            id="ab-type"
            value={kind}
            onChange={(e) => setKind(e.target.value as "webhook" | "ai")}
            className="max-w-xs"
          >
            <option value="webhook">{t("aiAgent.typeWebhook")}</option>
            <option value="ai">{t("aiAgent.typeAi")}</option>
          </Select>
        </div>
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

      {ai ? (
        <>
          <div className="space-y-1.5">
            <Label htmlFor="ab-instructions">{t("aiAgent.instructions")}</Label>
            <Textarea
              id="ab-instructions"
              rows={6}
              maxLength={4000}
              value={instructions}
              onChange={(e) => setInstructions(e.target.value)}
            />
            <p className="text-xs text-fg-muted">{t("aiAgent.instructionsHint")}</p>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="ab-mode">{t("aiAgent.mode")}</Label>
            <Select
              id="ab-mode"
              value={mode}
              onChange={(e) => setMode(e.target.value as AiBotMode)}
              className="max-w-xs"
            >
              <option value="shadow">{t("aiAgent.modeShadow")}</option>
              <option value="live">{t("aiAgent.modeLive")}</option>
            </Select>
            <p className="text-xs text-fg-muted">
              {mode === "shadow" ? t("aiAgent.modeShadowHint") : t("aiAgent.modeLiveHint")}
            </p>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="ab-when">{t("aiAgent.respondWhen")}</Label>
            <Select
              id="ab-when"
              value={respondWhen}
              onChange={(e) => setRespondWhen(e.target.value as AiBotRespondWhen)}
              className="max-w-sm"
            >
              <option value="always">{t("aiAgent.always")}</option>
              <option value="out_of_hours">{t("aiAgent.outOfHours")}</option>
              <option value="nobody_available">{t("aiAgent.nobodyAvailable")}</option>
            </Select>
            <p className="text-xs text-fg-muted">{t("aiAgent.respondWhenHint")}</p>
          </div>

          <p className="text-xs text-fg-muted">{t("aiAgent.attachHint")}</p>
        </>
      ) : (
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
      )}

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
