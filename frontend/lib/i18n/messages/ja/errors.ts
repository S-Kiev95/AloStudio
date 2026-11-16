import type { errors as es } from "../es/errors";
import type { Strings } from "../types";

export const errors: Strings<typeof es> = {
  sectionTitle: "このセクションを読み込めませんでした",
  sectionBody: "データの取得中に問題が発生しました。しばらくしてからもう一度お試しください。",
  accountNotFoundTitle: "お探しのものが見つかりませんでした",
  accountNotFoundBody: "このアカウントにそのパスはありません。",
  noAccountsTitle: "アカウントなし",
  noAccountsBody: "このユーザーにはまだアカウントが紐づいていません。",
  pageTitle: "問題が発生しました",
  pageBody: "このページの読み込み中に問題が発生しました。再読み込みしてください。",
  goHome: "ホームへ",
  notFoundTitle: "ページが見つかりません",
  notFoundBody: "URL が存在しないか、コンテンツが利用できなくなっています。",
};
