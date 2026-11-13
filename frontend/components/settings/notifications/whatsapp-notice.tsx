"use client";

import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  type NotificationSettings,
  type NotificationType,
  useUpdateNotificationSettings,
} from "@/lib/api/notifications";
import { useT } from "@/lib/i18n/provider";

const HANDOFF: NotificationType = "conversation_bot_handoff";

/**
 * Opt-in WhatsApp notice when the bot hands a conversation to the team.
 * Sent from the account's WhatsApp number with an approved Meta template,
 * so it is off by default and only covers handoffs.
 */
export function WhatsappNotice({
  accountId,
  settings,
}: {
  accountId: string;
  settings: NotificationSettings;
}) {
  const t = useT();
  const update = useUpdateNotificationSettings(accountId);
  const [enabled, setEnabled] = useState(false);
  const [number, setNumber] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    setEnabled((settings.selected_whatsapp_flags ?? []).includes(HANDOFF));
    setNumber(settings.whatsapp_number ?? "");
  }, [settings]);

  async function submit() {
    setError(null);
    setSaved(false);
    if (enabled && number.trim() === "") {
      setError(t("settingsNotif.whatsappNumberRequired"));
      return;
    }
    try {
      await update.mutateAsync({
        selected_whatsapp_flags: enabled ? [HANDOFF] : [],
        whatsapp_number: number.trim(),
      });
      setSaved(true);
    } catch (e) {
      setError(
        (e as { message?: string })?.message ??
          t("settingsNotif.whatsappSaveFailed"),
      );
    }
  }

  return (
    <div className="space-y-4">
      <p className="text-sm text-fg-muted">
        {t("settingsNotif.whatsappIntro")}
      </p>
      {error ? (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      ) : null}
      {saved ? (
        <p className="text-sm text-success">{t("settingsNotif.whatsappSaved")}</p>
      ) : null}
      <label className="flex cursor-pointer items-center gap-2.5 text-sm text-fg">
        <input
          type="checkbox"
          checked={enabled}
          onChange={() => {
            setEnabled(!enabled);
            setSaved(false);
          }}
          className="h-4 w-4 cursor-pointer rounded border-glass accent-neon"
        />
        {t("settingsNotif.whatsappToggle")}
      </label>
      <div className="space-y-1.5">
        <Label htmlFor="whatsapp-notice-number">{t("settingsNotif.whatsappNumber")}</Label>
        <Input
          id="whatsapp-notice-number"
          inputMode="tel"
          autoComplete="tel"
          placeholder="59899123456"
          value={number}
          onChange={(e) => {
            setNumber(e.target.value);
            setSaved(false);
          }}
          className="max-w-xs"
        />
        <p className="text-xs text-fg-muted">
          {t("settingsNotif.whatsappNumberHint")}
        </p>
      </div>
      <Button onClick={submit} loading={update.isPending}>
        {t("settingsNotif.whatsappSave")}
      </Button>
    </div>
  );
}
