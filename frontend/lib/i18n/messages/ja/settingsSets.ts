import type { settingsSets as es } from "../es/settingsSets";
import type { Strings } from "../types";

export const settingsSets: Strings<typeof es> = {
  title: "セット ({count})",
  channelsLabel: "チャネル: {names}",
  deleteFailed: "セットを削除できませんでした。",
  intro: "コンテンツのセットを管理して、投稿で簡単に再利用できます。",
  add: "セットを追加",
  loadFailed: "セットを読み込めませんでした。",
  empty: "保存済みのセットはまだありません。",
  noChannels: "チャネルなし",
  edit: "セットを編集",
  delete: "セットを削除",
};
