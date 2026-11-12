import type { oauth as es } from "../es/oauth";
import type { Strings } from "../types";

export const oauth: Strings<typeof es> = {
  scope: {
    readPosts: "投稿、チャネル、統計の閲覧",
    readConversations: "会話と連絡先の閲覧",
    writePosts: "投稿の予約と削除",
    writeConversations: "会話への返信と整理",
  },
  cannotAuthorize: "承認できません",
  invalidRequest: "アプリのリクエストが正しくありません。",
  backToApp: "AloStudio に戻る",
  createdBy: "作成者",
  willBeAbleTo: "次のことができるようになります:",
  whichAccount: "どのアカウントですか？",
  roleNotAllowed: "このアカウントでのあなたの権限では、このアクセスを許可できません",
  sendFailed: "回答を送信できませんでした。",
  authorize: "承認",
  wantsAccess: "{app} が AloStudio アカウントへのアクセスを求めています",
  redirectNote: "{host} に移動します。アクセスは 設定 → OAuth アプリ でいつでも取り消せます。",
};
