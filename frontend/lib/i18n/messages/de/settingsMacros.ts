import type { settingsMacros as es } from "../es/settingsMacros";
import type { Strings } from "../types";

export const settingsMacros: Strings<typeof es> = {
  action: "Aktion",
  noParams: "Keine Parameter",
  params: "Parameter",
  removeAction: "Aktion entfernen",
  back: "Zurück zu den Makros",
  loadFailed: "Das Makro konnte nicht geladen werden.",
  needAction: "Füge mindestens eine Aktion hinzu.",
  saveFailed: "Das Makro konnte nicht gespeichert werden.",
  visibility: "Sichtbarkeit",
  personal: "Persönlich",
  globalLong: "Global (für das ganze Konto sichtbar)",
  actions: "Aktionen",
  needActionHint: "Füge mindestens eine Aktion hinzu, um festzulegen, was das Makro tut.",
  addAction: "Aktion hinzufügen",
  create: "Makro erstellen",
  new: "Neues Makro",
  listLoadFailed: "Die Makros konnten nicht geladen werden.",
  empty: "Noch keine Makros.",
  global: "Global",
  deleteConfirm: "Das Makro „{name}“ löschen?",
  actionsOne: "{count} Aktion",
  actionsMany: "{count} Aktionen",
  by: "von {name}",
};
