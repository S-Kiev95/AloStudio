import type { agent as es } from "../es/agent";
import type { Strings } from "../types";

export const agent: Strings<typeof es> = {
  suggestions: {
    write: "明日 10 時に、すべてのチャネルで投稿を用意して",
    week: "今週の予定は？",
    lastMonth: "先月の投稿の結果はどうだった？",
  },
  unconfigured: "エージェントはまだ設定されていません。インストールの管理者が 設定 → インストール → 人工知能 で OpenAI のキーを登録する必要があります。",
  readOnly: "投稿や統計を確認できます。投稿の作成・削除は管理者が行います。",
  greeting: "こんにちは、AloStudio のエージェントです。チャネルへの投稿の作成や予約、カレンダーの確認、投稿の結果のお知らせができます。",
  seeInCalendar: "カレンダーで見る",
  newChat: "新しいチャット",
  chat: "チャット",
  chats: "チャット",
  statusFailed: "エージェントの状態を確認できませんでした。",
  chatNotFound: "このチャットは見つかりませんでした。",
  chatLoadFailed: "チャットを読み込めませんでした。",
  thinking: "考え中…",
  composer: {
    label: "エージェントへのメッセージ",
    unavailable: "エージェントは利用できません",
    placeholder: "メッセージを入力…",
    send: "メッセージを送信",
  },
  deleteFailed: "チャットを削除できませんでした。",
  closeList: "チャット一覧を閉じる",
  chatsLoadFailed: "チャットを読み込めませんでした。",
  noChats: "チャットはまだありません。",
  toConfirm: "確認待ち",
  deleteChat: "チャットを削除",
  pending: {
    seeLess: "閉じる",
    seeMore: "もっと見る",
    changeHint: "変更したい点があれば書いてください。エージェントが新しい案を作ります。",
    willDelete: "この投稿は削除されます",
    soon: "数分以内に公開されます",
    at: "{when} に公開",
  },
  deleteConfirm: "チャット「{title}」を削除しますか？",
  deleteChatNamed: "チャット {title} を削除",
};
