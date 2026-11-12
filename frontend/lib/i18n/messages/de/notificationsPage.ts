import type { notificationsPage as es } from "../es/notificationsPage";
import type { Strings } from "../types";

export const notificationsPage: Strings<typeof es> = {
  filter: "Filter",
  unread: "Ungelesen",
  loadFailed: "Die Benachrichtigungen konnten nicht geladen werden.",
  emptyUnread: "Du hast keine ungelesenen Benachrichtigungen.",
  markRead: "Als gelesen markieren",
  pagination: "Seitennavigation",
  counts: "{unread} ungelesen · {total} insgesamt",
  pageOf: "Seite {n} von {pages}",
};
