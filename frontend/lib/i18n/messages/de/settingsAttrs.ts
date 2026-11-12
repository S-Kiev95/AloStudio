import type { settingsAttrs as es } from "../es/settingsAttrs";
import type { Strings } from "../types";

export const settingsAttrs: Strings<typeof es> = {
  displayNameRequired: "Der Anzeigename ist ein Pflichtfeld.",
  saveFailed: "Das Attribut konnte nicht gespeichert werden.",
  displayName: "Anzeigename",
  appliesTo: "Gilt für",
  regex: "Muster (Regex)",
  regexHint: "Hinweis für den Benutzer",
  regexHintPlaceholder: "z. B. ABC-1234",
  values: "Werte",
  noValues: "Die Liste enthält noch keine Werte.",
  newValue: "Neuer Wert",
  create: "Attribut erstellen",
  new: "Neues Attribut",
  edit: "Attribut bearbeiten",
  model: "Modell",
  loadFailed: "Die Attribute konnten nicht geladen werden.",
  empty: "Noch keine Attribute definiert.",
  deleteConfirm: "„{name}“ löschen?",
  keyReadonly: "Schlüssel: {key} (nicht änderbar)",
};
