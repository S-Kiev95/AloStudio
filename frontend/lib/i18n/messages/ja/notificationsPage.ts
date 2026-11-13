import type { notificationsPage as es } from "../es/notificationsPage";
import type { Strings } from "../types";

export const notificationsPage: Strings<typeof es> = {
  filter: "フィルター",
  unread: "未読",
  loadFailed: "通知を読み込めませんでした。",
  emptyUnread: "未読の通知はありません。",
  markRead: "既読にする",
  pagination: "ページ送り",
  counts: "未読 {unread} 件 · 全 {total} 件",
  pageOf: "{pages} ページ中 {n} ページ",
};
