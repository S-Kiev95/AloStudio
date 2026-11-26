import type { businessProfile as es } from "../es/businessProfile";
import type { Strings } from "../types";

export const businessProfile: Strings<typeof es> = {
  title: "ビジネスについて",
  intro: "会社の事業内容と運営方法を一度だけ記入してください。アカウントのすべてのAIエージェント（通話対応、会話の分類、チャット応答）が参照します。",
  label: "ビジネスの説明",
  placeholder: "販売している商品や提供サービス、営業時間、住所、支払い方法、交換・返品の方針、よくある質問、してはいけないこと…",
  hint: "価格と商品はカタログから、詳しい回答はヘルプセンターから読み込みます。ここにはそれ以外の情報を書いてください。",
  readOnly: "アカウントの管理者が編集します。",
  loading: "読み込み中…",
  loadFailed: "説明を読み込めませんでした。",
  save: "保存",
  saved: "保存しました。",
  saveFailed: "保存できませんでした（8,000文字まで）。",
};
