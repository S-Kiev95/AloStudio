"use client";

import { PhoneCall } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  type CallSettingsInput,
  useCallSettings,
  useSaveCallSettings,
} from "@/lib/api/calls";
import { useT } from "@/lib/i18n/provider";
import { translateOr } from "@/lib/i18n/translate";

const EMPTY: CallSettingsInput = {
  enabled: false,
  call_icon_visible: true,
  // Asking to be called back needs calling customers, the next step of F7.
  callback_requests: false,
  business_hours: false,
};

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

/** Ajustes → Bandejas → (WhatsApp): let customers call the number (F7). */
export function WhatsappCallsCard({
  accountId,
  inboxId,
}: {
  accountId: string;
  inboxId: number;
}) {
  const t = useT();
  const settings = useCallSettings(accountId, inboxId);
  const save = useSaveCallSettings(accountId, inboxId);
  const [form, setForm] = useState<CallSettingsInput>(EMPTY);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (!settings.data) return;
    const { enabled, call_icon_visible, callback_requests, business_hours } = settings.data;
    setForm({ enabled, call_icon_visible, callback_requests, business_hours });
  }, [settings.data]);

  function toggle(key: keyof CallSettingsInput) {
    setSaved(false);
    setForm((f) => ({ ...f, [key]: !f[key] }));
  }

  async function submit() {
    setSaved(false);
    try {
      await save.mutateAsync(form);
      setSaved(true);
    } catch {
      // shown below from save.error
    }
  }

  const loadError = settings.error;
  const restrictions = settings.data?.restrictions ?? [];

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
