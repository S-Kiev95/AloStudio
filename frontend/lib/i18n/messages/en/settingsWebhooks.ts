import type { settingsWebhooks as es } from "../es/settingsWebhooks";
import type { Strings } from "../types";

export const settingsWebhooks: Strings<typeof es> = {
  urlRequired: "The URL is required.",
  eventsRequired: "Pick at least one event to subscribe to.",
  saveFailed: "Couldn't save the webhook.",
  url: "URL",
  inboxOptional: "Inbox (optional)",
  events: "Subscribed events",
  create: "Create webhook",
  new: "New webhook",
  edit: "Edit webhook",
  loadFailed: "Couldn't load the webhooks.",
  empty: "No webhooks yet.",
  deleteConfirm: "Delete this webhook?",
  eventsOne: "{count} event",
  eventsMany: "{count} events",
};
