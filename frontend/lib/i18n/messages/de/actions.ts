import type { actions as es } from "../es/actions";
import type { Strings } from "../types";

export const actions: Strings<typeof es> = {
  apply: "Anwenden",
  cancel: "Abbrechen",
  selectPlaceholder: "Auswählen…",
  edit: "Bearbeiten",
  clear: "Zurücksetzen",
  previous: "Zurück",
  next: "Weiter",
  addPlaceholder: "Hinzufügen…",
  back: "Zurück",
  send: "Senden",
  close: "Schließen",
  retry: "Erneut versuchen",
  discard: "Verwerfen",
  yes: "Ja",
  no: "Nein",
  page: "Seite {n}",
};
