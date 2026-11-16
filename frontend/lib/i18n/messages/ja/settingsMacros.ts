import type { settingsMacros as es } from "../es/settingsMacros";
import type { Strings } from "../types";

export const settingsMacros: Strings<typeof es> = {
  action: "アクション",
  noParams: "パラメーターなし",
  params: "パラメーター",
  removeAction: "アクションを削除",
  back: "マクロ一覧に戻る",
  loadFailed: "マクロを読み込めませんでした。",
  needAction: "アクションを 1 つ以上追加してください。",
  saveFailed: "マクロを保存できませんでした。",
  visibility: "公開範囲",
  personal: "個人",
  globalLong: "全体 (アカウント全員に表示)",
  actions: "アクション",
  needActionHint: "マクロの動作を決めるアクションを 1 つ以上追加してください。",
  addAction: "アクションを追加",
  create: "マクロを作成",
  new: "新しいマクロ",
  listLoadFailed: "マクロを読み込めませんでした。",
  empty: "マクロはまだありません。",
  global: "全体",
  deleteConfirm: "マクロ「{name}」を削除しますか？",
  actionsOne: "{count} 件のアクション",
  actionsMany: "{count} 件のアクション",
  by: "{name} 作成",
};
