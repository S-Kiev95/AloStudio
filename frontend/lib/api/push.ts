import { useQuery } from "@tanstack/react-query";

import { apiFetch } from "./fetcher";

export type VapidKey = { public_key: string; enabled: boolean };

/** ``GET /notification_subscriptions/vapid_key`` — the server's VAPID public
 * key + whether web-push is configured server-side. */
export function useVapidKey() {
  return useQuery({
    queryKey: ["vapid-key"],
    queryFn: () =>
      apiFetch<VapidKey>("/api/v1/notification_subscriptions/vapid_key"),
    staleTime: Number.POSITIVE_INFINITY,
  });
}

/** True when this browser can do web-push at all. */
export function pushSupported(): boolean {
  return (
    typeof window !== "undefined" &&
    "serviceWorker" in navigator &&
    "PushManager" in window &&
    "Notification" in window
  );
}

function urlBase64ToUint8Array(base64: string): Uint8Array<ArrayBuffer> {
  const padding = "=".repeat((4 - (base64.length % 4)) % 4);
  const b64 = (base64 + padding).replace(/-/g, "+").replace(/_/g, "/");
  const raw = atob(b64);
  const out = new Uint8Array(new ArrayBuffer(raw.length));
  for (let i = 0; i < raw.length; i++) out[i] = raw.charCodeAt(i);
  return out;
}

async function register(): Promise<ServiceWorkerRegistration> {
  return navigator.serviceWorker.register("/sw.js");
}

/** Whether the browser currently holds an active push subscription. */
export async function currentPushSubscription(): Promise<PushSubscription | null> {
  if (!pushSupported()) return null;
  const reg = await navigator.serviceWorker.getRegistration();
  return reg ? reg.pushManager.getSubscription() : null;
}

/** Ask for permission, subscribe the browser, and persist it server-side. */
export async function subscribeToPush(vapidPublicKey: string): Promise<void> {
  const permission = await Notification.requestPermission();
  if (permission !== "granted") {
    throw new Error("Permiso de notificaciones denegado.");
  }
  const reg = await register();
  const sub = await reg.pushManager.subscribe({
    userVisibleOnly: true,
    applicationServerKey: urlBase64ToUint8Array(vapidPublicKey),
  });
  await apiFetch("/api/v1/notification_subscriptions", {
    method: "POST",
    body: JSON.stringify({
      notification_subscription: { subscription_attributes: sub.toJSON() },
    }),
  });
}

/** Remove the server-side subscription and unsubscribe the browser. */
export async function unsubscribeFromPush(): Promise<void> {
  const reg = await navigator.serviceWorker.getRegistration();
  const sub = reg ? await reg.pushManager.getSubscription() : null;
  if (!sub) return;
  await apiFetch("/api/v1/notification_subscriptions", {
    method: "DELETE",
    body: JSON.stringify({ endpoint: sub.endpoint }),
  });
  await sub.unsubscribe();
}
