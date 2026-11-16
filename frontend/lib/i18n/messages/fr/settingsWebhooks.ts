import type { settingsWebhooks as es } from "../es/settingsWebhooks";
import type { Strings } from "../types";

export const settingsWebhooks: Strings<typeof es> = {
  urlRequired: "L’URL est obligatoire.",
  eventsRequired: "Choisissez au moins un événement auquel vous abonner.",
  saveFailed: "Impossible d’enregistrer le webhook.",
  url: "URL",
  inboxOptional: "Boîte de réception (facultatif)",
  events: "Événements abonnés",
  create: "Créer le webhook",
  new: "Nouveau webhook",
  edit: "Modifier le webhook",
  loadFailed: "Impossible de charger les webhooks.",
  empty: "Aucun webhook pour l’instant.",
  deleteConfirm: "Supprimer ce webhook ?",
  eventsOne: "{count} événement",
  eventsMany: "{count} événements",
};
