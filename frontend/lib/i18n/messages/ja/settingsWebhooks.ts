import type { settingsWebhooks as es } from "../es/settingsWebhooks";
import type { Strings } from "../types";

export const settingsWebhooks: Strings<typeof es> = {
  urlRequired: "URL は必須です。",
  eventsRequired: "購読するイベントを 1 つ以上選んでください。",
  saveFailed: "Webhook を保存できませんでした。",
  url: "URL",
  inboxOptional: "受信箱 (任意)",
  events: "購読中のイベント",
  create: "Webhook を作成",
  new: "新しい Webhook",
  edit: "Webhook を編集",
  loadFailed: "Webhook を読み込めませんでした。",
  empty: "Webhook はまだありません。",
  deleteConfirm: "この Webhook を削除しますか？",
  eventsOne: "{count} 件のイベント",
  eventsMany: "{count} 件のイベント",
};
