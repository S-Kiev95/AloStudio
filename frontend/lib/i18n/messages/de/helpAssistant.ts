import type { helpAssistant as es } from "../es/helpAssistant";
import type { Strings } from "../types";

export const helpAssistant: Strings<typeof es> = {
  title: "Hilfe",
  intro: "Frag, wie etwas in AloStudio geht, und ich führe dich zum richtigen Bildschirm.",
  examples: "Zum Beispiel: „Wie gebe ich eine Unterhaltung an jemand anderen?“ oder „Wo ändere ich mein Passwort?“.",
  question: "Deine Frage",
  placeholder: "Wie mache ich…?",
  ask: "Fragen",
  thinking: "Suche in der Hilfe… das kann ein paar Sekunden dauern.",
  goTo: "Zu {screen}",
  problems: {
    disabled: "Die Hilfe ist in dieser Installation nicht eingeschaltet.",
    question: "Schreib deine Frage.",
    busy: "Die Hilfe wird vorbereitet. Versuch es in ein paar Minuten noch einmal.",
    failed: "Die Hilfe hat nicht geantwortet. Versuch es noch einmal.",
  },
};
