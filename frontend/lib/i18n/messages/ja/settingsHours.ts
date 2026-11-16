import type { settingsHours as es } from "../es/settingsHours";
import type { Strings } from "../types";

export const settingsHours: Strings<typeof es> = {
  saveFailed: "営業時間を保存できませんでした。",
  loading: "営業時間を読み込み中…",
  loadFailed: "営業時間を読み込めませんでした。",
  weekly: "週間スケジュール",
  closed: "休業",
  allDay: "24 時間",
  opens: "開始",
  closes: "終了",
  inboxesLoadFailed: "受信箱を読み込めませんでした。",
  noInboxes: "接続済みの受信箱はまだありません。",
};
