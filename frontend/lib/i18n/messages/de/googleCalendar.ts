import type { googleCalendar as es } from "../es/googleCalendar";
import type { Strings } from "../types";

export const googleCalendar: Strings<typeof es> = {
  title: "Google Kalender",
  intro: "Deine Termine aus der Agenda und deine CRM-Aufgaben mit Datum erscheinen in deinem Google Kalender und aktualisieren sich alle 5 Minuten. Bearbeitet werden sie in AloStudio.",
  connect: "Google Kalender verbinden",
  reconnect: "Neu verbinden",
  disconnect: "Trennen",
  connectedAs: "Verbunden als {email}",
  lastSync: "letzte Synchronisierung: {when}",
  waiting: "die erste Synchronisierung kommt in ein paar Minuten",
  revoked: "Google gewährt keinen Zugriff mehr auf deinen Kalender. Verbinde ihn neu.",
  syncFailed: "Die letzte Synchronisierung ist fehlgeschlagen: {detail}",
  connecting: "Dein Kalender wird verbunden…",
  back: "Zurück zu AloStudio",
  problems: {
    unavailable: "Google ist in dieser Installation nicht eingerichtet.",
    state: "Der Link ist abgelaufen oder gehörte jemand anderem. Versuch es noch einmal.",
    exchange: "Google hat die Verbindung nicht angenommen. Versuch es noch einmal.",
    no_refresh_token: "Google hat keinen dauerhaften Zugriff gewährt. Versuch es noch einmal.",
    cancelled: "Die Verbindung mit Google wurde abgebrochen.",
    failed: "Verbindung mit Google nicht möglich.",
  },
};
