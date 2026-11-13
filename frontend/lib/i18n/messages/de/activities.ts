import type { activities as es } from "../es/activities";
import type { Strings } from "../types";

export const activities: Strings<typeof es> = {
  pageTitle: "Aufgaben",
  new: "Neue Aufgabe",
  edit: "Aufgabe bearbeiten",
  create: "Aufgabe erstellen",
  kind: "Art",
  kinds: {
    task: "Aufgabe",
    call: "Anruf",
    meeting: "Termin",
    email: "E-Mail",
  },
  titlePlaceholder: "z. B. Anrufen, um die Anmeldung zu bestätigen",
  due: "Fällig",
  dueInvalid: "Das Fälligkeitsdatum ist ungültig.",
  opportunity: "Verkaufschance",
  noOpportunity: "Keine",
  saveFailed: "Die Aufgabe konnte nicht gespeichert werden.",
  deleteConfirm: "Die Aufgabe „{title}“ löschen?",
  loadFailed: "Die Aufgaben konnten nicht geladen werden.",
  markDone: "„{title}“ als erledigt markieren",
  groups: {
    overdue: "Überfällig",
    today: "Heute",
    upcoming: "Demnächst",
    undated: "Ohne Datum",
    done: "Erledigt",
  },
  show: "Anzeigen",
  pending: "Offen",
  mine: "Meine",
  nonePending: "Keine offenen Aufgaben.",
  noneDone: "Noch keine erledigten Aufgaben.",
  noneForContact: "Dieser Kontakt hat keine offenen Aufgaben.",
};
