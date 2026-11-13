import type { settingsSignatures as es } from "../es/settingsSignatures";
import type { Strings } from "../types";

export const settingsSignatures: Strings<typeof es> = {
  tooLong: "署名は {max} 文字以内にしてください。",
  textRequired: "署名の文面を入力してください。",
  saveFailed: "署名を保存できませんでした。",
  updateFailed: "署名を更新できませんでした。",
  deleteFailed: "署名を削除できませんでした。",
  title: "署名",
  intro: "アカウントに署名を追加して投稿で再利用したり、新しい投稿ごとに自動で付けたりできます。",
  add: "署名を追加",
  loadFailed: "署名を読み込めませんでした。",
  empty: "署名はまだありません。",
  auto: "自動",
  unsetAuto: "自動を解除",
  setAuto: "自動にする",
  edit: "署名を編集",
  delete: "署名を削除",
  text: "署名の文面",
  textPlaceholder: "例: DM またはウェブサイトからお問い合わせください。",
  autoQuestion: "新しい投稿ごとに自動で付けますか？",
  save: "署名を保存",
};
