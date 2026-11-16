import type { errors as es } from "../es/errors";
import type { Strings } from "../types";

export const errors: Strings<typeof es> = {
  sectionTitle: "Dieser Bereich konnte nicht geladen werden",
  sectionBody: "Beim Abrufen der Daten ist etwas schiefgelaufen. Versuch es gleich noch einmal.",
  accountNotFoundTitle: "Wir haben nicht gefunden, was du suchst",
  accountNotFoundBody: "Dieser Pfad existiert in diesem Konto nicht.",
  noAccountsTitle: "Keine Konten",
  noAccountsBody: "Dein Benutzer ist noch keinem Konto zugeordnet.",
  pageTitle: "Etwas ist schiefgelaufen",
  pageBody: "Beim Laden dieser Seite gab es ein Problem. Lade sie neu.",
  goHome: "Zur Startseite",
  notFoundTitle: "Seite nicht gefunden",
  notFoundBody: "Die URL existiert nicht oder der Inhalt ist nicht mehr verfügbar.",
};
