import type { igCapabilities as es } from "../es/igCapabilities";
import type { Strings } from "../types";

export const igCapabilities: Strings<typeof es> = {
  publish: "写真、カルーセル、リール、ストーリーズを公開",
  comments: "コメントの閲覧と返信 (自動ルール付き)",
  insights: "投稿のインサイト",
  facebook: {
    summary: "すべての機能が使える方法です。メッセージに対応するならこちらがおすすめです。",
    requirement: "Instagram アカウントにリンクされた Facebook ページが必要です。",
    dmsNote: "メッセージは本文と添付ファイル付きで届きます。",
  },
  dms: "ダイレクトメッセージの受信と返信",
  deletePosts: "AloStudio から投稿を削除",
  instagram: {
    summary: "接続は簡単ですが、メッセージは使えません。",
    requirement: "Facebook ページは不要です。",
    dmsNote: "Meta はメッセージの到着を通知しますが本文を送らないため、会話を再現できません。これは Meta 側の制限で、AloStudio の問題ではありません。",
    deleteNote: "Meta はこの API で削除を提供していません。Instagram アプリから削除する必要があります。",
  },
};
