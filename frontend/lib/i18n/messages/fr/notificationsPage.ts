import type { notificationsPage as es } from "../es/notificationsPage";
import type { Strings } from "../types";

export const notificationsPage: Strings<typeof es> = {
  filter: "Filtre",
  unread: "Non lues",
  loadFailed: "Impossible de charger les notifications.",
  emptyUnread: "Vous n’avez aucune notification non lue.",
  markRead: "Marquer comme lue",
  pagination: "Pagination",
  counts: "{unread} non lues · {total} au total",
  pageOf: "Page {n} sur {pages}",
};
