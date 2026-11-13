import type { settingsCanned as es } from "../es/settingsCanned";
import type { Strings } from "../types";

export const settingsCanned: Strings<typeof es> = {
  shortCodeRequired: "ショートカットは必須です。",
  contentRequired: "内容は必須です。",
  saveFailed: "返信を保存できませんでした。",
  shortCode: "ショートカット",
  content: "内容",
  create: "返信を作成",
  new: "新しい返信",
  search: "返信を検索",
  searchPlaceholder: "ショートカットまたは内容で検索…",
  edit: "返信を編集",
  loadFailed: "返信を読み込めませんでした。",
  noneFound: "返信が見つかりませんでした。",
  empty: "返信はまだありません。",
  deleteConfirm: "「/{code}」を削除しますか？",
  shortCodeHint: "エディターで {code} と入力すると返信が挿入されます。",
  shortCodeExample: "ショートカット",
};
