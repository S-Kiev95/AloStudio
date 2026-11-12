import type { notificationsPage as es } from "../es/notificationsPage";
import type { Strings } from "../types";

export const notificationsPage: Strings<typeof es> = {
  filter: "Filter",
  unread: "Unread",
  loadFailed: "Couldn't load the notifications.",
  emptyUnread: "You have no unread notifications.",
  markRead: "Mark as read",
  pagination: "Pagination",
  counts: "{unread} unread · {total} total",
  pageOf: "Page {n} of {pages}",
};
