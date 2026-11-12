import type { settingsHours as es } from "../es/settingsHours";
import type { Strings } from "../types";

export const settingsHours: Strings<typeof es> = {
  saveFailed: "Impossible d’enregistrer les horaires.",
  loading: "Chargement des horaires…",
  loadFailed: "Impossible de charger les horaires.",
  weekly: "Horaires hebdomadaires",
  closed: "Fermé",
  allDay: "24 heures",
  opens: "Ouvre",
  closes: "Ferme",
  inboxesLoadFailed: "Impossible de charger les boîtes de réception.",
  noInboxes: "Aucune boîte de réception connectée pour l’instant.",
};
