import type { hc as es } from "../es/hc";
import type { Strings } from "../types";

export const hc: Strings<typeof es> = {
  articleEmpty: "この記事にはまだ内容がありません。",
  categoryEmpty: "このカテゴリーに公開済みの記事はまだありません。",
  errorTitle: "ヘルプセンターを読み込めませんでした",
  errorBody: "しばらくしてから再読み込みしてください。",
  notFoundTitle: "この記事は見つかりませんでした",
  notFoundBody: "公開が終了したか、リンクが変更された可能性があります。",
  categories: "カテゴリー",
  recentArticles: "最近の記事",
  noArticles: "公開済みの記事はまだありません。",
  backToSite: "サイトに戻る",
  poweredBy: "Powered by AloStudio",
};
