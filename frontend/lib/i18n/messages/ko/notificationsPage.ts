import type { notificationsPage as es } from "../es/notificationsPage";
import type { Strings } from "../types";

export const notificationsPage: Strings<typeof es> = {
  filter: "필터",
  unread: "읽지 않음",
  loadFailed: "알림을 불러오지 못했습니다.",
  emptyUnread: "읽지 않은 알림이 없습니다.",
  markRead: "읽음으로 표시",
  pagination: "페이지 이동",
  counts: "읽지 않음 {unread}개 · 전체 {total}개",
  pageOf: "{pages}페이지 중 {n}페이지",
};
