import type { notificationsPage as es } from "../es/notificationsPage";
import type { Strings } from "../types";

export const notificationsPage: Strings<typeof es> = {
  filter: "Filtro",
  unread: "Não lidas",
  loadFailed: "Não foi possível carregar as notificações.",
  emptyUnread: "Você não tem notificações não lidas.",
  markRead: "Marcar como lida",
  pagination: "Paginação",
  counts: "{unread} não lidas · {total} no total",
  pageOf: "Página {n} de {pages}",
};
