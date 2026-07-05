"use client";

import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  currentPushSubscription,
  pushSupported,
  subscribeToPush,
  unsubscribeFromPush,
  useVapidKey,
} from "@/lib/api/push";

/**
 * Enable / disable browser web-push for the current device. Registers the
 * service worker + PushManager subscription on enable and posts it to the
 * backend; hides itself when the browser or the server can't do push.
 */
export function PushToggle() {
  const vapid = useVapidKey();
  const [subscribed, setSubscribed] = useState<boolean | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const supported = pushSupported();

  useEffect(() => {
    if (!supported) {
      setSubscribed(false);
      return;
    }
    currentPushSubscription()
      .then((s) => setSubscribed(Boolean(s)))
      .catch(() => setSubscribed(false));
  }, [supported]);

  if (!supported) {
    return (
      <p className="text-sm text-fg-muted">
        Este navegador no admite notificaciones push.
      </p>
    );
  }
  if (vapid.data && !vapid.data.enabled) {
    return (
      <p className="text-sm text-fg-muted">
        Las notificaciones push no están configuradas en el servidor.
      </p>
    );
  }

  async function toggle() {
    setError(null);
    setBusy(true);
    try {
      if (subscribed) {
        await unsubscribeFromPush();
        setSubscribed(false);
      } else if (vapid.data?.public_key) {
        await subscribeToPush(vapid.data.public_key);
        setSubscribed(true);
      }
    } catch (e) {
      setError(
        (e as { message?: string })?.message ??
          "No se pudo cambiar la suscripción.",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between gap-4">
        <div className="min-w-0">
          <p className="text-sm font-medium text-fg">
            Notificaciones push del navegador
          </p>
          <p className="text-xs text-fg-muted">
            Recibí avisos en este dispositivo aunque no tengas la pestaña
            abierta.
          </p>
        </div>
        <Button
          size="sm"
          variant={subscribed ? "secondary" : "primary"}
          onClick={toggle}
          loading={busy}
          disabled={subscribed === null}
        >
          {subscribed ? "Desactivar" : "Activar"}
        </Button>
      </div>
      {error ? (
        <p role="alert" className="text-xs text-danger">
          {error}
        </p>
      ) : null}
    </div>
  );
}
