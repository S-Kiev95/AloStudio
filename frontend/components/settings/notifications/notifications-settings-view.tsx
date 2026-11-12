"use client";

import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  NOTIFICATION_TYPES,
  type NotificationType,
  useNotificationSettings,
  useUpdateNotificationSettings,
} from "@/lib/api/notifications";
import { cn } from "@/lib/utils";

import { PushToggle } from "./push-toggle";
import { SoundToggle } from "./sound-toggle";
import { WhatsappNotice } from "./whatsapp-notice";
import { useT } from "@/lib/i18n/provider";

/**
 * Per-user notification preferences. Two checkbox columns (email / push)
 * × N notification types; toggling persists on save via
 * ``PATCH /notification_settings``.
 */
export function NotificationsSettingsView({
  accountId,
}: {
  accountId: string;
}) {
  const t = useT();
  const settings = useNotificationSettings(accountId);
  const update = useUpdateNotificationSettings(accountId);

  const [email, setEmail] = useState<Set<NotificationType>>(new Set());
  const [push, setPush] = useState<Set<NotificationType>>(new Set());
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (!settings.data) return;
    setEmail(new Set(settings.data.selected_email_flags));
    setPush(new Set(settings.data.selected_push_flags));
  }, [settings.data]);

  function toggle(
    set: Set<NotificationType>,
    setSet: (next: Set<NotificationType>) => void,
    type: NotificationType,
  ) {
    const next = new Set(set);
    if (next.has(type)) next.delete(type);
    else next.add(type);
    setSet(next);
    setSaved(false);
  }

  async function submit() {
    setError(null);
    setSaved(false);
    try {
      await update.mutateAsync({
        selected_email_flags: Array.from(email),
        selected_push_flags: Array.from(push),
      });
      setSaved(true);
    } catch (e) {
      setError(
        (e as { message?: string })?.message ??
          t("settingsNotif.saveFailed"),
      );
    }
  }

  return (
    <div className="max-w-2xl space-y-4">
      <h2 className="text-xl font-medium text-fg">{t("settings.items.notifications")}</h2>
      <p className="text-sm text-fg-muted">
        {t("settingsNotif.intro")}
      </p>
      <p className="rounded-md border border-glass bg-surface-2 px-3 py-2 text-xs text-fg-muted">
        {t("settingsNotif.channelsNote")}
      </p>

      <Card>
        <CardHeader>
          <CardTitle>{t("settingsNotif.thisDevice")}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <PushToggle />
          <SoundToggle />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{t("settingsNotif.preferences")}</CardTitle>
        </CardHeader>
        <CardContent>
          {settings.isLoading ? (
            <p className="text-sm text-fg-muted">{t("common.loading")}</p>
          ) : settings.isError ? (
            <p role="alert" className="text-sm text-danger">
              {t("settingsNotif.loadFailed")}
            </p>
          ) : (
            <div className="space-y-4">
              {error ? (
                <p role="alert" className="text-sm text-danger">
                  {error}
                </p>
              ) : null}
              {saved ? (
                <p className="text-sm text-success">{t("settingsNotif.saved")}</p>
              ) : null}

              <div className="overflow-hidden rounded-md border border-glass">
                <table className="w-full text-sm">
                  <thead className="bg-surface-2 text-[11px] uppercase tracking-[0.08em] text-fg-muted">
                    <tr>
                      <th className="px-3 py-2.5 text-left font-medium">
                        {t("settingsNotif.event")}
                      </th>
                      <th className="w-20 px-3 py-2.5 text-center font-medium">
                        {t("common.email")}
                      </th>
                      <th className="w-20 px-3 py-2.5 text-center font-medium">
                        {t("settingsNotif.inApp")}
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {NOTIFICATION_TYPES.map((type) => (
                      <tr
                        key={type}
                        className={cn(
                          "border-t border-glass transition-colors",
                          "hover:bg-hover-glass",
                        )}
                      >
                        <td className="px-3 py-2.5 text-fg">
                          {t(`notifications.types.${type}`)}
                        </td>
                        <td className="px-3 py-2.5 text-center">
                          <label className="inline-flex cursor-pointer items-center">
                            <input
                              type="checkbox"
                              aria-label={t("settingsNotif.emailFor", { type: t(`notifications.types.${type}`) })}
                              checked={email.has(type)}
                              onChange={() => toggle(email, setEmail, type)}
                              className="h-4 w-4 cursor-pointer rounded border-glass accent-neon"
                            />
                          </label>
                        </td>
                        <td className="px-3 py-2.5 text-center">
                          <label className="inline-flex cursor-pointer items-center">
                            <input
                              type="checkbox"
                              aria-label={t("settingsNotif.inAppFor", { type: t(`notifications.types.${type}`) })}
                              checked={push.has(type)}
                              onChange={() => toggle(push, setPush, type)}
                              className="h-4 w-4 cursor-pointer rounded border-glass accent-neon"
                            />
                          </label>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <div>
                <Button onClick={submit} loading={update.isPending}>
                  {t("common.saveChanges")}
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {settings.data ? (
        <Card>
          <CardHeader>
            <CardTitle>{t("settingsNotif.whatsappTitle")}</CardTitle>
          </CardHeader>
          <CardContent>
            <WhatsappNotice accountId={accountId} settings={settings.data} />
          </CardContent>
        </Card>
      ) : null}
    </div>
  );
}
