import type { settingsWebhooks as es } from "../es/settingsWebhooks";
import type { Strings } from "../types";

export const settingsWebhooks: Strings<typeof es> = {
  urlRequired: "Die URL ist ein Pflichtfeld.",
  eventsRequired: "Wähle mindestens ein Ereignis zum Abonnieren.",
  saveFailed: "Der Webhook konnte nicht gespeichert werden.",
  url: "URL",
  inboxOptional: "Posteingang (optional)",
  events: "Abonnierte Ereignisse",
  create: "Webhook erstellen",
  new: "Neuer Webhook",
  edit: "Webhook bearbeiten",
  loadFailed: "Die Webhooks konnten nicht geladen werden.",
  empty: "Noch keine Webhooks.",
  deleteConfirm: "Diesen Webhook löschen?",
  eventsOne: "{count} Ereignis",
  eventsMany: "{count} Ereignisse",
};
