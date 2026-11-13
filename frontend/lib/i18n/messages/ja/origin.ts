import type { origin as es } from "../es/origin";
import type { Strings } from "../types";

export const origin: Strings<typeof es> = {
  title: "流入元",
  set: "流入元を設定",
  source: "きっかけ",
  channel: "チャネル",
  detail: "詳細",
  detailPlaceholder: "例：Juan さんの紹介、10 月の展示会…",
  unknown: "未設定",
  noChannel: "なし",
  none: "流入元はまだ分かっていません。",
  since: "{date} から",
  saveFailed: "流入元を保存できませんでした。",
  sources: {
    channel: "チャネルから連絡",
    ad: "広告",
    post: "投稿",
    shortlink: "直接リンク",
    referral: "紹介",
    event: "イベント・展示会",
    walk_in: "来店",
    phone: "電話",
    website: "Web サイト",
    other: "その他",
  },
  channels: {
    whatsapp: "WhatsApp",
    instagram: "Instagram",
    facebook: "Facebook",
    web: "Web サイトのチャット",
    email: "メール",
    telegram: "Telegram",
    sms: "SMS",
    api: "API",
  },
};
