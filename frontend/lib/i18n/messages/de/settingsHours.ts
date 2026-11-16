import type { settingsHours as es } from "../es/settingsHours";
import type { Strings } from "../types";

export const settingsHours: Strings<typeof es> = {
  saveFailed: "Die Öffnungszeiten konnten nicht gespeichert werden.",
  loading: "Öffnungszeiten werden geladen…",
  loadFailed: "Die Öffnungszeiten konnten nicht geladen werden.",
  weekly: "Wöchentliche Zeiten",
  closed: "Geschlossen",
  allDay: "24 Stunden",
  opens: "Öffnet",
  closes: "Schließt",
  inboxesLoadFailed: "Die Posteingänge konnten nicht geladen werden.",
  noInboxes: "Noch keine Posteingänge verbunden.",
};
