import type { settingsSignatures as es } from "../es/settingsSignatures";
import type { Strings } from "../types";

export const settingsSignatures: Strings<typeof es> = {
  tooLong: "Die Signatur darf höchstens {max} Zeichen lang sein.",
  textRequired: "Schreib den Text der Signatur.",
  saveFailed: "Die Signatur konnte nicht gespeichert werden.",
  updateFailed: "Die Signatur konnte nicht aktualisiert werden.",
  deleteFailed: "Die Signatur konnte nicht gelöscht werden.",
  title: "Signaturen",
  intro: "Du kannst deinem Konto Signaturen hinzufügen, um sie in deinen Beiträgen wiederzuverwenden oder automatisch an jeden neuen Beitrag anzuhängen.",
  add: "Signatur hinzufügen",
  loadFailed: "Die Signaturen konnten nicht geladen werden.",
  empty: "Noch keine Signaturen.",
  auto: "Automatisch",
  unsetAuto: "Automatik entfernen",
  setAuto: "Automatisch machen",
  edit: "Signatur bearbeiten",
  delete: "Signatur löschen",
  text: "Text der Signatur",
  textPlaceholder: "z. B. Schreib uns eine Direktnachricht oder besuche unsere Website.",
  autoQuestion: "Automatisch an jeden neuen Beitrag anhängen?",
  save: "Signatur speichern",
};
