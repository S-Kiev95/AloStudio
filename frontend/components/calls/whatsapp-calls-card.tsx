"use client";

import { PhoneCall } from "lucide-react";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import {
  ANNOUNCEMENT_LANGUAGES,
  type CallSettingsInput,
  PURPOSE_MAX,
  useCallSettings,
  useSaveCallSettings,
} from "@/lib/api/calls";
import { useIntlTag, useT } from "@/lib/i18n/provider";
import { translateOr } from "@/lib/i18n/translate";

type Form = Required<CallSettingsInput>;

const EMPTY: Form = {
  enabled: false,
  call_icon_visible: true,
  // Asking to be called back needs calling customers, the next step of F7.
  callback_requests: false,
  business_hours: false,
  record: false,
  transcribe: false,
  purpose: "",
  announcement_language: "es",
};

type Flag = "enabled" | "call_icon_visible" | "business_hours" | "record" | "transcribe";

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
    });
  }, [settings.data]);

  function toggle(key: Flag) {
    setSaved(false);
    setForm((f) => ({ ...f, [key]: !f[key] }));
  }

  function change(key: "purpose" | "announcement_language", value: string) {
    setSaved(false);
    setForm((f) => ({ ...f, [key]: value }));
  }

  const loadError = settings.error;
  const restrictions = settings.data?.restrictions ?? [];
  const recordingAllowed = settings.data?.recording_allowed === true;
  const capturing = form.record || form.transcribe;

  async function submit() {
    setSaved(false);
    const { record, transcribe, purpose, announcement_language, ...number } = form;
    try {
      await save.mutateAsync(
        recordingAllowed
          ? { ...number, record, transcribe, purpose, announcement_language }
          : number,
      );
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
                hint={t("calls.settings.enabledHint")}
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
