import type { channelCatalog as es } from "../es/channelCatalog";
import type { Strings } from "../types";

export const channelCatalog: Strings<typeof es> = {
  telegram: {
    blurb: "BotFather のトークンで Telegram ボットを接続します。",
    tokenHelp: "ボット作成時に @BotFather から受け取ったトークン。",
    botName: "ボット名",
    botNameHelp: "任意 — ボットの @username。",
  },
  whatsapp: {
    blurb: "Meta の Cloud API 経由の WhatsApp Business 番号。",
  },
  phoneNumber: "電話番号",
  sms: {
    blurb: "Bandwidth 経由の SMS 番号。",
  },
  twilio: {
    blurb: "SMS または WhatsApp 用の Twilio 番号。",
    medium: "手段",
  },
  email: {
    blurb: "サポート窓口としてのメールボックス。",
    address: "メールアドレス",
    imapEnabled: "メールを受信 (IMAP)",
    imapHelp: "これがないと、届いたメールが受信箱に入りません。",
    imapServer: "IMAP サーバー",
    imapPort: "IMAP ポート",
    imapUser: "IMAP ユーザー名",
    imapPassword: "IMAP パスワード",
    appPasswordHelp: "2 段階認証を使っている場合は、アプリ パスワードを使ってください。",
    imapSsl: "安全な IMAP 接続 (SSL)",
    smtpEnabled: "メールを送信 (SMTP)",
    smtpServer: "SMTP サーバー",
    smtpPort: "SMTP ポート",
    smtpUser: "SMTP ユーザー名",
    smtpPassword: "SMTP パスワード",
    smtpStarttls: "安全な SMTP 接続 (STARTTLS)",
  },
  web: {
    blurb: "Web サイトに埋め込むチャット。",
    siteUrl: "サイトの URL",
    welcomeTitle: "ウェルカムタイトル",
    welcomePlaceholder: "こんにちは！👋",
    tagline: "サブタイトル",
  },
  api: {
    blurb: "HTTP API による汎用チャネル (送信 Webhook は任意)。",
    webhookHelp: "任意 — 受信メッセージの転送先。",
  },
  facebook: {
    blurb: "Facebook ページのメッセージと投稿。",
    userTokenHelp: "任意 — 期限切れ時にページトークンを更新するため。",
    instagramIdHelp: "任意 — ページが IG アカウントに接続されている場合。",
  },
  instagram: {
    blurb: "トークンによる IG ビジネス。投稿の公開やコメントの管理には、メニューの Instagram セクションを使ってください。",
  },
};
