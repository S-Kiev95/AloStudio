import type { agent as es } from "../es/agent";
import type { Strings } from "../types";

export const agent: Strings<typeof es> = {
  suggestions: {
    write: "Erstelle einen Beitrag für morgen um 10 Uhr auf allen meinen Kanälen",
    week: "Was habe ich diese Woche geplant?",
    lastMonth: "Wie liefen meine Beiträge im letzten Monat?",
  },
  unconfigured: "Der Agent ist noch nicht eingerichtet. Ein Betreiber der Installation muss den OpenAI-Schlüssel unter Einstellungen → Installation → Künstliche Intelligenz eintragen.",
  readOnly: "Du kannst Beiträge und Statistiken abfragen. Beiträge erstellen oder löschen kann nur ein Administrator.",
  greeting: "Hallo, ich bin der AloStudio-Agent. Ich kann Beiträge für deine Kanäle erstellen und planen, deinen Kalender prüfen und dir sagen, wie deine Beiträge gelaufen sind.",
  seeInCalendar: "Im Kalender ansehen",
  newChat: "Neuer Chat",
  chat: "Chat",
  chats: "Chats",
  statusFailed: "Der Status des Agenten konnte nicht abgefragt werden.",
  chatNotFound: "Dieser Chat wurde nicht gefunden.",
  chatLoadFailed: "Der Chat konnte nicht geladen werden.",
  thinking: "Denkt nach…",
  composer: {
    label: "Nachricht an den Agenten",
    unavailable: "Der Agent ist nicht verfügbar",
    placeholder: "Schreib eine Nachricht…",
    send: "Nachricht senden",
  },
  deleteFailed: "Der Chat konnte nicht gelöscht werden.",
  closeList: "Chatliste schließen",
  chatsLoadFailed: "Die Chats konnten nicht geladen werden.",
  noChats: "Du hast noch keine Chats.",
  toConfirm: "Zu bestätigen",
  deleteChat: "Chat löschen",
  pending: {
    seeLess: "Weniger anzeigen",
    seeMore: "Mehr anzeigen",
    changeHint: "Wenn du etwas ändern willst, schreib es und der Agent macht einen neuen Vorschlag.",
    willDelete: "Dieser Beitrag wird gelöscht",
    soon: "Geht in den nächsten Minuten raus",
    at: "Geht raus: {when}",
  },
  deleteConfirm: "Den Chat „{title}“ löschen?",
  deleteChatNamed: "Chat {title} löschen",
};
