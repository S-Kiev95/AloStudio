import type { settingsCanned as es } from "../es/settingsCanned";
import type { Strings } from "../types";

export const settingsCanned: Strings<typeof es> = {
  shortCodeRequired: "Das Kürzel ist ein Pflichtfeld.",
  contentRequired: "Der Inhalt ist ein Pflichtfeld.",
  saveFailed: "Die Antwort konnte nicht gespeichert werden.",
  shortCode: "Kürzel",
  content: "Inhalt",
  create: "Antwort erstellen",
  new: "Neue Antwort",
  search: "Antworten suchen",
  searchPlaceholder: "Nach Kürzel oder Inhalt suchen…",
  edit: "Antwort bearbeiten",
  loadFailed: "Die Antworten konnten nicht geladen werden.",
  noneFound: "Keine Antworten gefunden.",
  empty: "Noch keine Antworten.",
  deleteConfirm: "„/{code}“ löschen?",
  shortCodeHint: "Gib {code} im Editor ein, um die Antwort einzufügen.",
  shortCodeExample: "kürzel",
};
