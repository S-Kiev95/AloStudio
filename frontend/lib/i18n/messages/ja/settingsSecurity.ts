import type { settingsSecurity as es } from "../es/settingsSecurity";
import type { Strings } from "../types";

export const settingsSecurity: Strings<typeof es> = {
  fillAll: "3 つの欄をすべて入力してください。",
  min8: "新しいパスワードは 8 文字以上にしてください。",
  mismatch: "確認用のパスワードが新しいパスワードと一致しません。",
  changeFailed: "パスワードを変更できませんでした。",
  changePassword: "パスワードを変更",
  updated: "パスワードを更新しました。",
  current: "現在のパスワード",
  new: "新しいパスワード",
  min8Short: "8 文字以上。",
  repeat: "新しいパスワード (確認)",
  update: "パスワードを更新",
};
