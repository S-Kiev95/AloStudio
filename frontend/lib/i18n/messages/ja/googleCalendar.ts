import type { googleCalendar as es } from "../es/googleCalendar";
import type { Strings } from "../types";

export const googleCalendar: Strings<typeof es> = {
  title: "Google カレンダー",
  intro: "アジェンダの予約と日付のある CRM タスクが Google カレンダーに表示され、5 分ごとに自動で更新されます。編集は AloStudio で行います。",
  connect: "Google カレンダーを接続",
  reconnect: "再接続",
  disconnect: "接続を解除",
  connectedAs: "{email} として接続中",
  lastSync: "最終同期: {when}",
  waiting: "最初の同期は数分後です",
  revoked: "Google がカレンダーへのアクセスを許可しなくなりました。再接続してください。",
  syncFailed: "前回の同期に失敗しました: {detail}",
  connecting: "カレンダーを接続しています…",
  back: "AloStudio に戻る",
  problems: {
    unavailable: "このインストールでは Google が設定されていません。",
    state: "リンクの期限切れか、別の人のリンクです。もう一度お試しください。",
    exchange: "Google が接続を受け付けませんでした。もう一度お試しください。",
    no_refresh_token: "Google が継続的なアクセスを許可しませんでした。もう一度お試しください。",
    cancelled: "Google との接続がキャンセルされました。",
    failed: "Google に接続できませんでした。",
  },
};
