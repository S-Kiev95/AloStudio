import type { settingsInstall as es } from "../es/settingsInstall";
import type { Strings } from "../types";

export const settingsInstall: Strings<typeof es> = {
  configuredCount: "{done}/{total} 件設定済み",
  netConfigured: "設定済み",
  netNotConfigured: "未設定",
  operatorOnly: "この画面はインストールの運用者だけが見られます。デプロイした人にアクセスを依頼してください。",
  loadFailed: "設定を読み込めませんでした。",
  intro: "アカウント単位ではなく、AloStudio 全体に適用される設定です。認証情報がそろうまで空欄のままでかまいません。アプリはなくても動作し、各機能が何が足りないかを知らせます。",
  network: "ネットワーク",
  clearFailed: "削除できませんでした。",
  notConfigured: "未設定",
  configured: "設定済み",
  savedHere: "ここで保存",
  resetToServer: "サーバーの値に戻す",
  fromEnv: "サーバーのファイル (.env) から読み込み",
};
