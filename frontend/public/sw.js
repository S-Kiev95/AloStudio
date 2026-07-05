/* AloStudio web-push service worker.
 * Shows a notification for each push (payload {title, body, url}) and
 * focuses / opens the linked conversation on click. */

self.addEventListener("push", (event) => {
  let data = {};
  try {
    data = event.data ? event.data.json() : {};
  } catch (_e) {
    data = {};
  }
  const title = data.title || "AloStudio";
  const options = {
    body: data.body || "",
    tag: data.url || undefined,
    data: { url: data.url || "/" },
  };
  event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const url = (event.notification.data && event.notification.data.url) || "/";
  event.waitUntil(
    self.clients
      .matchAll({ type: "window", includeUncontrolled: true })
      .then((wins) => {
        for (const w of wins) {
          if (w.url === url && "focus" in w) return w.focus();
        }
        return self.clients.openWindow(url);
      }),
  );
});
