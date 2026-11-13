import type { metaCatalog as es } from "../es/metaCatalog";
import type { Strings } from "../types";

export const metaCatalog: Strings<typeof es> = {
  title: "Meta カタログ",
  intro: "コマースマネージャのカタログを接続すると、有効な商品がそこに送られ、WhatsApp・Instagram・Facebook で表示できるようになります。",
  howTo: "ID はコマースマネージャ → カタログ → 設定 にあります。トークンは catalog_management 権限とカタログへのアクセス権を持つシステムユーザー（ビジネス設定 → システムユーザー）のものを使います。",
  catalogId: "カタログ ID",
  token: "アクセストークン",
  tokenKeep: "空欄のままにすると現在のものを使います",
  connect: "カタログを接続",
  disconnect: "接続を解除",
  syncNow: "今すぐ同期",
  disconnectConfirm: "カタログの接続を解除しますか？ すでに Meta にある商品はそのまま残ります。",
  unnamed: "名前のないカタログ",
  neverSynced: "まだ同期していません。",
  lastSync: "前回の同期: {date} · 送信 {sent} 件、問題あり {failed} 件",
  stillChecking: "Meta はまだ送信内容を確認中でした。失敗したものは次回の同期で表示されます。",
  autoSync: "商品を変更すると、数秒後に自動で送信されます。",
  synced: "完了: 送信 {sent} 件、削除 {removed} 件、情報不足 {skipped} 件、Meta が拒否 {failed} 件。",
  state: {
    synced: "Meta に掲載中",
    pending: "Meta に未送信",
    missing: "Meta に送信されません。不足: {fields}",
    refused: "Meta が拒否",
  },
  fields: {
    description: "説明",
    price: "価格と通貨",
    url: "リンク",
    image_url: "画像",
  },
  errors: {
    token: "Meta がトークンを受け付けませんでした。有効で期限切れでないか確認してください。",
    permission: "このトークンにはそのカタログへの権限（catalog_management）がありません。",
    catalog_id: "カタログ ID は数字のみです。",
    refused: "Meta がリクエストを拒否しました。",
    unreachable: "Meta に接続できませんでした。しばらくしてからもう一度お試しください。",
    not_connected: "先にカタログを接続してください。",
  },
};
