"use client";

import { PhoneCall } from "lucide-react";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { usePlanAllows } from "@/lib/api/billing";
import {
  AI_GREETING_MAX,
  AI_INSTRUCTIONS_MAX,
  ANNOUNCEMENT_LANGUAGES,
  CALL_AI_MODES,
  type CallAiMode,
  type CallSettingsInput,
  MISSED_TEXT_MAX,
  PURPOSE_MAX,
  useCallSettings,
  useSaveCallSettings,
} from "@/lib/api/calls";
import { useIntlTag, useT } from "@/lib/i18n/provider";
import { type MessageKey, translateOr } from "@/lib/i18n/translate";

type Form = Required<CallSettingsInput>;

const EMPTY: Form = {
  enabled: false,
  call_icon_visible: true,
  callback_requests: false,
  business_hours: false,
  record: false,
  transcribe: false,
  purpose: "",
  announcement_language: "es",
  missed_call_reply: true,
  missed_call_text: "",
  ai_mode: "off",
  ai_greeting: "",
  ai_instructions: "",
  ai_voice: "",
};

const AI_MODE_LABEL: Record<CallAiMode, MessageKey> = {
  off: "calls.settings.aiModeOff",
  always: "calls.settings.aiModeAlways",
  after_hours: "calls.settings.aiModeAfterHours",
  no_answer: "calls.settings.aiModeNoAnswer",
};

type Flag =
  | "enabled"
  | "call_icon_visible"
  | "business_hours"
  | "callback_requests"
  | "record"
  | "transcribe"
  | "missed_call_reply";

function problemKey(err: unknown): string {
  const code = (err as { body?: { code?: unknown } })?.body?.code;
  if (typeof code === "string" && code.startsWith("calls.")) {
    return `calls.problems.${code.slice(6)}`;
  }
  return "calls.problems.refused";
}

/** Meta's reason, when it gave one beyond our code. */
function metaReason(err: unknown): string | null {
  const body = (err as { body?: { code?: unknown; message?: unknown } })?.body;
  if (typeof body?.message === "string" && body.message !== body.code) {
    return body.message;
  }
  return null;
}

/** "es_ES" → "español (España)", in the reader's language. */
function useLanguageName(): (code: string) => string {
  const tag = useIntlTag();
  return useMemo(() => {
    let names: Intl.DisplayNames | null = null;
    try {
      names = new Intl.DisplayNames([tag], { type: "language" });
    } catch {
      names = null;
    }
    return (code: string) => names?.of(code.replace("_", "-")) ?? code;
  }, [tag]);
}

/** Ajustes → Bandejas → (WhatsApp): let customers call the number (F7). */
export function WhatsappCallsCard({
  accountId,
  inboxId,
}: {
  accountId: string;
  inboxId: number;
}) {
  const t = useT();
  const languageName = useLanguageName();
  const settings = useCallSettings(accountId, inboxId);
  const plan = usePlanAllows(accountId);
  const save = useSaveCallSettings(accountId, inboxId);
  const [form, setForm] = useState<Form>(EMPTY);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    const data = settings.data;
    if (!data) return;
    setForm({
      enabled: data.enabled,
      call_icon_visible: data.call_icon_visible,
      callback_requests: data.callback_requests,
      business_hours: data.business_hours,
      record: data.record,
      transcribe: data.transcribe,
      purpose: data.purpose ?? "",
      announcement_language: data.announcement_language || "es",
      missed_call_reply: data.missed_call_reply ?? true,
      missed_call_text: data.missed_call_text ?? "",
      ai_mode: data.ai_mode ?? "off",
      ai_greeting: data.ai_greeting ?? "",
      ai_instructions: data.ai_instructions ?? "",
      ai_voice: data.ai_voice ?? "",
    });
  }, [settings.data]);

  function toggle(key: Flag) {
    setSaved(false);
    setForm((f) => ({ ...f, [key]: !f[key] }));
  }

  function change(
    key:
      | "purpose"
      | "announcement_language"
      | "missed_call_text"
      | "ai_greeting"
      | "ai_instructions"
      | "ai_voice",
    value: string,
  ) {
    setSaved(false);
    setForm((f) => ({ ...f, [key]: value }));
  }

  const loadError = settings.error;
  const restrictions = settings.data?.restrictions ?? [];
  const recordingAllowed = settings.data?.recording_allowed === true;
  const capturing = form.record || form.transcribe;
  const aiAvailable = settings.data?.ai_available === true;
  const aiOn = form.ai_mode !== "off";
  const voices = settings.data?.ai_voices ?? [];

  async function submit() {
    setSaved(false);
    const {
      record,
      transcribe,
      purpose,
      announcement_language,
      ai_mode,
      ai_greeting,
      ai_instructions,
      ai_voice,
      ...number
    } = form;
    // Without the voice AI set up only "off" is accepted: anything else is left as it is.
    const ai = aiAvailable
      ? { ai_mode, ai_greeting, ai_instructions, ai_voice }
      : ai_mode === "off"
        ? { ai_mode }
        : {};
    try {
      await save.mutateAsync({
        ...number,
        ...ai,
        ...(recordingAllowed ? { record, transcribe, purpose, announcement_language } : {}),
      });
      setSaved(true);
    } catch {
      // shown below from save.error
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <PhoneCall className="h-4 w-4 text-fg-muted" aria-hidden />
          {t("calls.settings.title")}
        </CardTitle>
        <p className="mt-1 text-sm text-fg-muted">{t("calls.settings.intro")}</p>
      </CardHeader>
      <CardContent className="space-y-4">
        {settings.isLoading ? (
          <p className="text-sm text-fg-muted">{t("calls.settings.loading")}</p>
        ) : loadError ? (
          <p role="alert" className="text-sm text-danger">
            {translateOr(t, problemKey(loadError), t("calls.problems.refused"))}
            {metaReason(loadError) ? ` (${metaReason(loadError)})` : ""}
          </p>
        ) : (
          <>
            <fieldset className="space-y-3">
              <legend className="sr-only">{t("calls.settings.title")}</legend>
              <Toggle
                checked={form.enabled}
                onChange={() => toggle("enabled")}
                label={t("calls.settings.enabled")}
                hint={plan.calls ? t("calls.settings.enabledHint") : t("billing.notInPlan")}
                // Not in the plan (F2): they can be turned off, not on.
                disabled={!plan.calls && !form.enabled}
              />
              <Toggle
                checked={form.call_icon_visible}
                onChange={() => toggle("call_icon_visible")}
                disabled={!form.enabled}
                label={t("calls.settings.icon")}
                hint={t("calls.settings.iconHint")}
              />
              <Toggle
                checked={form.business_hours}
                onChange={() => toggle("business_hours")}
                disabled={!form.enabled}
                label={t("calls.settings.hours")}
                hint={
                  <>
                    {t("calls.settings.hoursHint")}{" "}
                    <Link
                      href={`/accounts/${accountId}/settings/working_hours`}
                      className="text-lit underline-offset-2 hover:underline"
                    >
                      {t("calls.settings.hoursLink")}
                    </Link>
                  </>
                }
              />
              <Toggle
                checked={form.callback_requests}
                onChange={() => toggle("callback_requests")}
                disabled={!form.enabled}
                label={t("calls.settings.callback")}
                hint={t("calls.settings.callbackHint")}
              />
            </fieldset>

            <fieldset className="space-y-3 border-t border-glass pt-4">
              <legend className="text-sm font-medium text-fg">{t("calls.settings.aiTitle")}</legend>
              {!aiAvailable ? (
                <p className="text-xs text-fg-muted">{t("calls.settings.aiUnavailable")}</p>
              ) : null}
              <div className="space-y-1.5">
                <Label htmlFor={`call-ai-mode-${inboxId}`}>{t("calls.settings.aiMode")}</Label>
                <Select
                  id={`call-ai-mode-${inboxId}`}
                  value={form.ai_mode}
                  disabled={!form.enabled || (!aiAvailable && !aiOn)}
                  onChange={(e) => {
                    setSaved(false);
                    const mode = e.target.value as CallAiMode;
                    setForm((f) => ({ ...f, ai_mode: mode }));
                  }}
                >
                  {CALL_AI_MODES.filter(
                    (mode) => aiAvailable || mode === "off" || mode === form.ai_mode,
                  ).map((mode) => (
                    <option key={mode} value={mode}>
                      {t(AI_MODE_LABEL[mode])}
                    </option>
                  ))}
                </Select>
                <p className="text-xs text-fg-muted">{t("calls.settings.aiModeHint")}</p>
                {form.ai_mode === "after_hours" && form.business_hours ? (
                  <p role="status" className="text-xs text-warning">
                    {t("calls.settings.aiHoursHint")}
                  </p>
                ) : null}
              </div>
              {aiAvailable && aiOn ? (
                <>
                  <div className="space-y-1.5">
                    <Label htmlFor={`call-ai-greeting-${inboxId}`}>
                      {t("calls.settings.aiGreeting")}
                    </Label>
                    <Input
                      id={`call-ai-greeting-${inboxId}`}
                      value={form.ai_greeting}
                      maxLength={AI_GREETING_MAX}
                      disabled={!form.enabled}
                      onChange={(e) => change("ai_greeting", e.target.value)}
                    />
                    <p className="text-xs text-fg-muted">{t("calls.settings.aiGreetingHint")}</p>
                  </div>
                  <div className="space-y-1.5">
                    <Label htmlFor={`call-ai-instructions-${inboxId}`}>
                      {t("calls.settings.aiInstructions")}
                    </Label>
                    <Textarea
                      id={`call-ai-instructions-${inboxId}`}
                      rows={4}
                      value={form.ai_instructions}
                      maxLength={AI_INSTRUCTIONS_MAX}
                      disabled={!form.enabled}
                      onChange={(e) => change("ai_instructions", e.target.value)}
                    />
                    <p className="text-xs text-fg-muted">
                      {t("calls.settings.aiInstructionsHint")}
                    </p>
                  </div>
                  <div className="space-y-1.5">
                    <Label htmlFor={`call-ai-voice-${inboxId}`}>{t("calls.settings.aiVoice")}</Label>
                    <Select
                      id={`call-ai-voice-${inboxId}`}
                      value={form.ai_voice}
                      disabled={!form.enabled}
                      onChange={(e) => change("ai_voice", e.target.value)}
                    >
                      {voices.map((name) => (
                        <option key={name} value={name}>
                          {name}
                        </option>
                      ))}
                    </Select>
                  </div>
                  <p className="text-xs text-fg-muted">{t("calls.settings.aiCostHint")}</p>
                </>
              ) : null}
            </fieldset>

            <fieldset className="space-y-3 border-t border-glass pt-4">
              <legend className="text-sm font-medium text-fg">
                {t("calls.settings.recordingTitle")}
              </legend>
              {!recordingAllowed ? (
                <p className="text-xs text-fg-muted">{t("calls.settings.recordingOff")}</p>
              ) : (
                <>
                  <Toggle
                    checked={form.record}
                    onChange={() => toggle("record")}
                    disabled={!form.enabled}
                    label={t("calls.settings.record")}
                    hint={t("calls.settings.recordHint")}
                  />
                  <Toggle
                    checked={form.transcribe}
                    onChange={() => toggle("transcribe")}
                    disabled={!form.enabled}
                    label={t("calls.settings.transcribe")}
                    hint={t("calls.settings.transcribeHint")}
                  />
                  <div className="space-y-1.5">
                    <Label htmlFor={`call-purpose-${inboxId}`}>{t("calls.settings.purpose")}</Label>
                    <Input
                      id={`call-purpose-${inboxId}`}
                      value={form.purpose}
                      maxLength={PURPOSE_MAX}
                      disabled={!form.enabled || !capturing}
                      onChange={(e) => change("purpose", e.target.value)}
                    />
                    <p className="text-xs text-fg-muted">
                      {t("calls.settings.purposeHint", {
                        purpose: form.purpose || "…",
                      })}
                    </p>
                  </div>
                  <div className="space-y-1.5">
                    <Label htmlFor={`call-language-${inboxId}`}>{t("calls.settings.language")}</Label>
                    <Select
                      id={`call-language-${inboxId}`}
                      value={form.announcement_language}
                      disabled={!form.enabled || !capturing}
                      onChange={(e) => change("announcement_language", e.target.value)}
                    >
                      {ANNOUNCEMENT_LANGUAGES.map((code) => (
                        <option key={code} value={code}>
                          {languageName(code)}
                        </option>
                      ))}
                    </Select>
                  </div>
                  <p className="text-xs text-fg-muted">{t("calls.settings.recordingLegal")}</p>
                </>
              )}
            </fieldset>

            <fieldset className="space-y-3 border-t border-glass pt-4">
              <legend className="text-sm font-medium text-fg">
                {t("calls.settings.missedTitle")}
              </legend>
              <Toggle
                checked={form.missed_call_reply}
                onChange={() => toggle("missed_call_reply")}
                disabled={!form.enabled}
                label={t("calls.settings.missedReply")}
                hint={t("calls.settings.missedReplyHint")}
              />
              <div className="space-y-1.5">
                <Label htmlFor={`call-missed-${inboxId}`}>{t("calls.settings.missedText")}</Label>
                <Textarea
                  id={`call-missed-${inboxId}`}
                  rows={2}
                  value={form.missed_call_text}
                  maxLength={MISSED_TEXT_MAX}
                  disabled={!form.enabled || !form.missed_call_reply}
                  onChange={(e) => change("missed_call_text", e.target.value)}
                />
              </div>
              <p className="text-xs text-fg-muted">{t("calls.settings.missedMarkHint")}</p>
            </fieldset>

            {restrictions.length > 0 ? (
              <p role="status" className="text-sm text-warning">
                {t("calls.settings.restricted")}
              </p>
            ) : null}
            <div className="flex flex-wrap items-center gap-3">
              <Button size="sm" onClick={() => void submit()} loading={save.isPending}>
                {t("calls.settings.save")}
              </Button>
              {saved ? (
                <span role="status" className="text-sm text-success">
                  {t("calls.settings.saved")}
                </span>
              ) : null}
              {save.error ? (
                <span role="alert" className="text-sm text-danger">
                  {translateOr(t, problemKey(save.error), t("calls.problems.refused"))}
                  {metaReason(save.error) ? ` (${metaReason(save.error)})` : ""}
                </span>
              ) : null}
            </div>
            <p className="text-xs text-fg-muted">{t("calls.settings.webhookNote")}</p>
          </>
        )}
      </CardContent>
    </Card>
  );
}

function Toggle({
  checked,
  onChange,
  disabled,
  label,
  hint,
}: {
  checked: boolean;
  onChange: () => void;
  disabled?: boolean;
  label: string;
  hint: React.ReactNode;
}) {
  return (
    <label className="flex cursor-pointer items-start gap-3 aria-disabled:cursor-not-allowed aria-disabled:opacity-60" aria-disabled={disabled}>
      <input
        type="checkbox"
        className="mt-0.5 h-4 w-4 accent-neon"
        checked={checked}
        onChange={onChange}
        disabled={disabled}
      />
      <span>
        <span className="block text-sm font-medium text-fg">{label}</span>
        <span className="block text-xs text-fg-muted">{hint}</span>
      </span>
    </label>
  );
}
