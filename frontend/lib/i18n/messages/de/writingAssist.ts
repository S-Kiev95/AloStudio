import type { writingAssist as es } from "../es/writingAssist";
import type { Strings } from "../types";

export const writingAssist: Strings<typeof es> = {
  button: "KI",
  working: "Schreibt…",
  menu: "KI-Hilfe",
  actions: {
    improve: "Text verbessern",
    fix: "Rechtschreibung korrigieren",
    formal: "Förmlicher",
    friendly: "Freundlicher",
    shorter: "Kürzer",
    translate: "Übersetzen in…",
    summarize: "Unterhaltung zusammenfassen",
  },
  summarizeHint: "Wird als private Notiz eingefügt",
  back: "Zurück",
  writeFirst: "Schreib etwas, um es zu verbessern oder zu übersetzen.",
  tooLong: "Der Text ist zu lang: höchstens {max} Zeichen.",
  undo: "Rückgängig",
  problems: {
    disabled: "Die KI-Hilfe ist in dieser Installation ausgeschaltet.",
    action: "Das kann die KI nicht.",
    text: "Der Text ist leer oder zu lang.",
    language: "Wähle eine Sprache aus der Liste.",
    conversation: "Die Unterhaltung hat noch keine Nachrichten zum Zusammenfassen.",
    budget: "Das KI-Ausgabenlimit für diesen Monat ist erreicht.",
    failed: "Die KI hat nicht geantwortet. Versuch es noch einmal.",
  },
};
