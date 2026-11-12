import type { settingsAssign as es } from "../es/settingsAssign";
import type { Strings } from "../types";

export const settingsAssign: Strings<typeof es> = {
  deleteConfirm: "Die Richtlinie „{name}“ löschen?",
  perWindow: "{limit} Konv. / {secs}s",
  limitSentence: "Jedem Agenten werden höchstens {limit} Konversationen alle {window} Sekunden zugewiesen.",
  priority: {
    earliest_created: "Die älteste zuerst",
    longest_waiting: "Die am längsten wartende",
  },
  subtitle: "Automatische Verteilung von Konversationen auf die Agenten eines Posteingangs.",
  new: "Neue Richtlinie",
  edit: "Richtlinie bearbeiten",
  loadFailed: "Die Richtlinien konnten nicht geladen werden.",
  empty: "Noch keine Richtlinien.",
  limitInvalid: "Das Limit muss eine ganze Zahl größer als 0 sein.",
  windowInvalid: "Das Zeitfenster muss eine ganze Zahl größer als 0 sein.",
  saveFailed: "Die Richtlinie konnte nicht gespeichert werden.",
  fairDistribution: "Ausgewogene Verteilung",
  optional: "Optional",
  priorityLabel: "Priorität der Konversationen",
  priorityHint: "Welche wartende Konversation ein verfügbarer Agent zuerst übernimmt.",
  limitPerAgent: "Limit pro Agent",
  windowSeconds: "Zeitfenster (Sekunden)",
  active: "Richtlinie aktiv",
  create: "Richtlinie erstellen",
};
