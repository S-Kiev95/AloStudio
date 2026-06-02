"use client";

import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  NOTIFICATION_TYPE_LABELS,
  NOTIFICATION_TYPES,
  type NotificationType,
  useNotificationSettings,
  useUpdateNotificationSettings,
} from "@/lib/api/notifications";
import { cn } from "@/lib/utils";

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
          "No se pudieron guardar las preferencias.",
      );
    }
  }

  return (
    <div className="mx-auto max-w-2xl space-y-4 p-4 md:p-6">
      <h2 className="text-xl font-semibold text-fg">Notificaciones</h2>
      <p className="text-sm text-fg-muted">
        Elegí qué eventos te van a llegar por email o como notificación en la
        app. La campanita del topbar muestra todas, independiente de esto.
      </p>

      <Card>
        <CardHeader>
          <CardTitle>Preferencias</CardTitle>
        </CardHeader>
        <CardContent>
          {settings.isLoading ? (
            <p className="text-sm text-fg-muted">Cargando…</p>
          ) : settings.isError ? (
            <p role="alert" className="text-sm text-danger">
              No se pudieron cargar las preferencias.
            </p>
          ) : (
            <div className="space-y-4">
              {error ? (
                <p role="alert" className="text-sm text-danger">
                  {error}
                </p>
              ) : null}
              {saved ? (
                <p className="text-sm text-success">Preferencias guardadas.</p>
              ) : null}

              <div className="overflow-hidden rounded-md border border-border">
                <table className="w-full text-sm">
                  <thead className="bg-surface-2 text-xs uppercase text-fg-muted">
                    <tr>
                      <th className="px-3 py-2 text-left font-medium">
                        Evento
                      </th>
                      <th className="w-20 px-3 py-2 text-center font-medium">
                        Email
                      </th>
                      <th className="w-20 px-3 py-2 text-center font-medium">
                        En la app
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {NOTIFICATION_TYPES.map((t) => (
                      <tr
                        key={t}
                        className={cn(
                          "border-t border-border",
                          "hover:bg-surface-2/40",
                        )}
                      >
                        <td className="px-3 py-2 text-fg">
                          {NOTIFICATION_TYPE_LABELS[t]}
                        </td>
                        <td className="px-3 py-2 text-center">
                          <label className="inline-flex cursor-pointer items-center">
                            <input
                              type="checkbox"
                              aria-label={`Email — ${NOTIFICATION_TYPE_LABELS[t]}`}
                              checked={email.has(t)}
                              onChange={() => toggle(email, setEmail, t)}
                              className="h-4 w-4 cursor-pointer rounded border-border accent-primary"
                            />
                          </label>
                        </td>
                        <td className="px-3 py-2 text-center">
                          <label className="inline-flex cursor-pointer items-center">
                            <input
                              type="checkbox"
                              aria-label={`En la app — ${NOTIFICATION_TYPE_LABELS[t]}`}
                              checked={push.has(t)}
                              onChange={() => toggle(push, setPush, t)}
                              className="h-4 w-4 cursor-pointer rounded border-border accent-primary"
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
                  Guardar cambios
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
