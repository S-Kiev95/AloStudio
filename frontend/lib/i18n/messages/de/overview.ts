import type { overview as es } from "../es/overview";
import type { Strings } from "../types";

export const overview: Strings<typeof es> = {
  live: {
    open: "Offen",
    unattended: "Unbeantwortet",
    unassigned: "Nicht zugewiesen",
    pending: "Ausstehend",
  },
  shortcut: {
    conversations: "Posteingang",
    conversationsDesc: "Nachrichten aus deinen Kanälen",
    instagramDesc: "DMs, Beiträge und Kommentare",
    campaigns: "Kampagnen",
    campaignsDesc: "Versände und Vorlagen",
    reports: "Berichte",
    reportsDesc: "Kennzahlen und Exporte",
  },
  welcome: "Willkommen",
  welcomeNamed: "Hallo, {name}",
  intro: "Alle deine Kanäle, Konversationen und Termine an einem Ort. So sieht es gerade aus und in den letzten 7 Tagen.",
  openInbox: "Posteingang öffnen",
  goCalendar: "Zum Kalender",
  rightNow: "Gerade jetzt",
  last7: "Letzte 7 Tage",
  liveFailed: "Wir konnten den aktuellen Status nicht laden.",
  metricsFailed: "Wir konnten die Kennzahlen des Zeitraums nicht laden.",
  chartFailed: "Wir konnten das Konversationsdiagramm nicht laden.",
  conversations: "Konversationen",
  shortcuts: "Schnellzugriff",
};
