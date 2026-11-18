import type { handoff as es } from "../es/handoff";
import type { Strings } from "../types";

export const handoff: Strings<typeof es> = {
  ai: "AloStudios KI",
  nobody: "Niemand",
  settings: {
    title: "Übergabe",
    intro: "Wenn Metas Agent oder die KI eine Konversation an das Team übergibt und niemand zugewiesen ist, übernimmt die passende zuständige Person: zuerst die des Chats (im Kontaktbereich gewählt), dann die des ersten Labels der Konversation, dann die des Posteingangs (Einstellungen → Posteingänge) und zuletzt die allgemeine. Greift keine, wird der ganze Posteingang benachrichtigt.",
    labels: "Nach Label",
    labelsHint: "Es gilt die erste Regel von oben, deren Label die Konversation trägt.",
    noLabelRules: "Noch keine Regeln nach Label.",
    label: "Label der Regel {n}",
    target: "Zuständig für Regel {n}",
    pickLabel: "Label wählen",
    pickTarget: "Zuständige Person wählen",
    up: "Regel {n} nach oben",
    down: "Regel {n} nach unten",
    remove: "Regel {n} entfernen",
    add: "Regel hinzufügen",
    noLabels: "Um nach Label zu übergeben, lege zuerst Labels unter Einstellungen → Labels an.",
    account: "Allgemein zuständig",
    accountHint: "Übernimmt, was keine Regel und kein Posteingang abdeckt.",
    save: "Speichern",
    saved: "Gespeichert.",
  },
  contact: {
    title: "Übergabe dieses Chats",
    byRules: "Nach den Regeln",
    hint: "Wenn ein Bot diesen Kontakt übergibt, übernimmt diese Person vor Labels und Posteingang.",
  },
  problems: {
    failed: "Speichern fehlgeschlagen. Bitte erneut versuchen.",
    loadFailed: "Die Regeln konnten nicht geladen werden.",
    one_target: "Wähle eine Person oder die KI, nicht beides.",
    ai_unavailable: "Dieses Konto hat AloStudios KI noch nicht.",
    not_a_member: "Diese Person gehört nicht mehr zum Konto.",
    too_many: "Zu viele Regeln (höchstens 50).",
    repeated_label: "Ein Label kommt in zwei Regeln vor.",
    unknown_label: "Eines der Labels gibt es nicht mehr.",
    no_target: "Jede Regel braucht eine zuständige Person.",
  },
};
