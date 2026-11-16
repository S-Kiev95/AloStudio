import type { settingsCsat as es } from "../es/settingsCsat";
import type { Strings } from "../types";

export const settingsCsat: Strings<typeof es> = {
  metricsFailed: "Die CSAT-Kennzahlen konnten nicht geladen werden.",
  rating: "Bewertung",
  responses: "Antworten",
  responsesFailed: "Die Antworten konnten nicht geladen werden.",
  noResponses: "Keine Antworten in diesem Zeitraum.",
  surveysSent: "Gesendete Umfragen",
  responseRate: "Antwortquote",
  average: "Durchschnitt",
  distribution: "Verteilung",
  anonymous: "Anonym",
  noComment: "(kein Kommentar)",
  agent: "Agent: {name}",
};
