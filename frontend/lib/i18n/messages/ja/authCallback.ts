import type { authCallback as es } from "../es/authCallback";
import type { Strings } from "../types";

export const authCallback: Strings<typeof es> = {
  googleCancelled: "Google でのログインがキャンセルされました。",
  googleFailed: "Google でログインできませんでした。",
  googleTitle: "Google でログイン",
  signingIn: "ログイン中…",
  ssoNoToken: "アクセスリンクにトークンが含まれていません。",
  ssoFailed: "ログインできませんでした。リンクの有効期限が切れている可能性があります。",
  ssoTitle: "Postiz からのアクセス",
};
