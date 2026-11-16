import type { overview as es } from "../es/overview";
import type { Strings } from "../types";

export const overview: Strings<typeof es> = {
  live: {
    open: "対応中",
    unattended: "未応答",
    unassigned: "未割り当て",
    pending: "保留",
  },
  shortcut: {
    conversations: "会話",
    conversationsDesc: "受信トレイ",
    instagramDesc: "DM、投稿、コメント",
    campaigns: "キャンペーン",
    campaignsDesc: "一斉送信とテンプレート",
    reports: "レポート",
    reportsDesc: "指標とエクスポート",
  },
  welcome: "ようこそ",
  intro: "すべてのチャネル、会話、予約をひとつの場所で。現在の状況と過去 7 日間の動きです。",
  openInbox: "受信トレイを開く",
  goCalendar: "カレンダーへ",
  rightNow: "現在",
  last7: "過去 7 日間",
  metricsFailed: "期間の指標を読み込めませんでした。",
  conversations: "会話",
  shortcuts: "ショートカット",
};
