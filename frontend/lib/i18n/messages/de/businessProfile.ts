import type { businessProfile as es } from "../es/businessProfile";
import type { Strings } from "../types";

export const businessProfile: Strings<typeof es> = {
  title: "Über das Unternehmen",
  intro: "Beschreiben Sie einmal, was das Unternehmen macht und wie es arbeitet. Alle KI-Agenten des Kontos lesen es: der für Anrufe, der zum Einordnen von Gesprächen und der für den Chat.",
  label: "Beschreibung des Unternehmens",
  placeholder: "Was es verkauft oder welche Leistungen es anbietet, Öffnungszeiten, Adresse, Zahlungsarten, Umtausch- und Rückgaberegeln, häufige Fragen, was nicht zu tun ist…",
  hint: "Preise und Produkte kommen aus dem Katalog, lange Antworten aus dem Hilfecenter: Hier steht, was dort fehlt.",
  readOnly: "Ein Administrator des Kontos bearbeitet es.",
  loading: "Wird geladen…",
  loadFailed: "Die Beschreibung konnte nicht geladen werden.",
  save: "Speichern",
  saved: "Gespeichert.",
  saveFailed: "Konnte nicht gespeichert werden (bis zu 8.000 Zeichen).",
};
