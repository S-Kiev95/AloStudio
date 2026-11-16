import type { settingsBots as es } from "../es/settingsBots";
import type { Strings } from "../types";

export const settingsBots: Strings<typeof es> = {
  deleteConfirm: "ボット「{name}」を削除しますか？",
  saveFailed: "ボットを保存できませんでした。",
  outgoingUrl: "送信先 URL",
  outgoingUrlHint: "バックエンドはメッセージイベントをこの URL に送信します。",
  create: "ボットを作成",
  new: "新しいボット",
  edit: "ボットを編集",
  loadFailed: "ボットを読み込めませんでした。",
  empty: "ボットはまだありません。",
  secret: "シークレット:",
  rotateSecret: "シークレットを再発行",
  rotateFailed: "シークレットを再発行できませんでした。",
};
