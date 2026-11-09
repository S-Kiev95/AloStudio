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
      setError("Poné tu número para recibir el aviso.");
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
          "No se pudo guardar el aviso por WhatsApp.",
      );
    }
  }

  return (
    <div className="space-y-4">
      <p className="text-sm text-fg-muted">
        Cuando el bot derive una conversación a una persona, te llega un
        WhatsApp desde el número de la cuenta. Sirve para enterarte aunque no
        tengas AloStudio abierto.
      </p>
      {error ? (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      ) : null}
      {saved ? (
        <p className="text-sm text-success">Aviso por WhatsApp guardado.</p>
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
        Avisarme por WhatsApp cuando el bot derive una conversación
      </label>
      <div className="space-y-1.5">
        <Label htmlFor="whatsapp-notice-number">Tu número de WhatsApp</Label>
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
          Con el código de país y sin el 0 inicial (Uruguay: 598).
        </p>
      </div>
      <Button onClick={submit} loading={update.isPending}>
        Guardar aviso
      </Button>
    </div>
  );
}
