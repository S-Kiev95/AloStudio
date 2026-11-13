import type { settingsPlugs as es } from "../es/settingsPlugs";
import type { Strings } from "../types";

export const settingsPlugs: Strings<typeof es> = {
  messageTooLong: "Die Nachricht überschreitet das Maximum von {max} Zeichen ({count}/{max}).",
  channelPlugs: "Plugs von {name}",
  whenLikes: "Bei {n} Likes",
  channelRequired: "Wähle einen Kanal, um den Plug einzurichten.",
  actionRequired: "Wähle eine Aktion aus dem Katalog.",
  thresholdMin: "Der Schwellenwert muss mindestens 1 Like betragen.",
  messageRequired: "Schreib die Nachricht für diese Aktion.",
  saveFailed: "Der Plug konnte nicht gespeichert werden.",
  updateFailed: "Der Plug konnte nicht aktualisiert werden.",
  deleteFailed: "Der Plug konnte nicht gelöscht werden.",
  title: "Plugs",
  intro: "Führe automatische Aktionen für deine Beiträge aus, wenn sie einen Like-Schwellenwert erreichen.",
  loadFailed: "Die Plugs konnten nicht geladen werden.",
  connectThreads: "Verbinde Threads, um automatische Aktionen zu nutzen",
  noChannels: "Keine verbundenen Kanäle mit verfügbaren Aktionen im Katalog.",
  goToCalendar: "Zum Kalender, um Kanäle zu verbinden",
  add: "Plug hinzufügen",
  noneInChannel: "Auf diesem Kanal sind keine automatischen Aktionen eingerichtet.",
  edit: "Plug bearbeiten",
  delete: "Plug löschen",
  lastRuns: "Letzte Ausführungen",
  runOk: "OK",
  runFailed: "Fehlgeschlagen",
  channel: "Kanal",
  thresholdLabel: "Bei N Likes",
  message: "Nachricht",
  messagePlaceholder: "Schreib die automatische Antwort…",
  save: "Plug speichern",
  kinds: {
    reply_after_likes: {
      label: "Bei N Likes antworten",
      description: "Wenn ein Beitrag diese Anzahl Likes erreicht, wird deine Nachricht als Antwort auf genau diesen Beitrag veröffentlicht (zum Beispiel ein Link oder ein Angebot).",
    },
    repost_after_likes: {
      label: "Bei N Likes reposten",
      description: "Wenn ein Beitrag diese Anzahl Likes erreicht, wird er in deinem Profil erneut gepostet, damit deine Follower ihn wieder sehen.",
    },
  },
};
