import type { closing as es } from "../es/closing";
import type { Strings } from "../types";

export const closing: Strings<typeof es> = {
  settings: {
    title: "Abschlussnotizen",
    intro: "Wer eine Unterhaltung im Panel erledigt, gibt den Grund an. Die Statistiken zählen, wie viele aus welchem Grund abgeschlossen wurden.",
    enabled: "Beim Erledigen nach dem Grund fragen",
    enabledHint: "Ein Fenster zeigt die Gründe und eine optionale Notiz. Automatisierungen und Massenaktionen erledigen ohne Nachfrage.",
    required: "Grund verpflichtend machen",
    requiredHint: "Ohne Grund lässt sich im Panel nichts erledigen.",
    categories: "Gründe",
    categoriesHint: "Bis zu 30, in der angezeigten Reihenfolge. Benennst du einen um, behalten frühere Abschlüsse den alten Namen.",
    category: "Grund {n}",
    add: "Grund hinzufügen",
    remove: "{category} entfernen",
    save: "Speichern",
    saved: "Gespeichert.",
  },
  dialog: {
    title: "Unterhaltung erledigen",
    question: "Warum wird sie abgeschlossen?",
    optional: "Der Grund ist optional.",
    note: "Notiz (optional)",
    notePlaceholder: "Was man wissen sollte, falls der Kunde wieder schreibt",
    cancel: "Abbrechen",
    resolve: "Erledigen",
  },
  report: {
    title: "Abschlussgründe",
    total: "Abschlüsse mit Grund oder Notiz: {count}",
    none: "Nur Notiz",
    empty: "In diesem Zeitraum gibt es noch keine Abschlüsse mit Grund.",
    off: "Abschlussnotizen sind ausgeschaltet.",
    turnOn: "In den Einstellungen einschalten",
    failed: "Die Abschlussgründe konnten nicht geladen werden.",
  },
  problems: {
    disabled: "Abschlussnotizen sind ausgeschaltet.",
    required: "Wähle einen Grund, um zu erledigen.",
    category: "Dieser Grund steht nicht mehr in der Liste. Wähle einen anderen.",
    note: "Die Notiz darf bis zu 2.000 Zeichen lang sein.",
    categories: "Es muss zwischen 1 und 30 Gründe geben.",
    category_length: "Jeder Grund darf bis zu 60 Zeichen lang sein.",
    duplicate_category: "Zwei Gründe sind gleich.",
    failed: "Speichern fehlgeschlagen. Versuch es noch einmal.",
  },
};
