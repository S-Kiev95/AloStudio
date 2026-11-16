import type { channelCatalog as es } from "../es/channelCatalog";
import type { Strings } from "../types";

export const channelCatalog: Strings<typeof es> = {
  telegram: {
    blurb: "Connect a Telegram bot with the token from BotFather.",
    tokenHelp: "The token @BotFather gave you when you created the bot.",
    botName: "Bot name",
    botNameHelp: "Optional — the bot's @username.",
  },
  whatsapp: {
    blurb: "WhatsApp Business number through Meta's Cloud API.",
  },
  phoneNumber: "Phone number",
  sms: {
    blurb: "SMS number through Bandwidth.",
  },
  twilio: {
    blurb: "Twilio number for SMS or WhatsApp.",
    medium: "Medium",
  },
  email: {
    blurb: "A mailbox as a support channel.",
    address: "Email address",
    imapEnabled: "Receive email (IMAP)",
    imapHelp: "Without this, what people write to you doesn't reach the inbox.",
    imapServer: "IMAP server",
    imapPort: "IMAP port",
    imapUser: "IMAP username",
    imapPassword: "IMAP password",
    appPasswordHelp: "If you use two-step verification, use an app password.",
    imapSsl: "Secure IMAP connection (SSL)",
    smtpEnabled: "Send email (SMTP)",
    smtpServer: "SMTP server",
    smtpPort: "SMTP port",
    smtpUser: "SMTP username",
    smtpPassword: "SMTP password",
    smtpStarttls: "Secure SMTP connection (STARTTLS)",
  },
  web: {
    blurb: "Embedded chat for your website.",
    siteUrl: "Website URL",
    welcomeTitle: "Welcome title",
    welcomePlaceholder: "Hi there! 👋",
    tagline: "Tagline",
  },
  api: {
    blurb: "Generic channel over an HTTP API (optional outgoing webhook).",
    webhookHelp: "Optional — where we forward incoming messages.",
  },
  facebook: {
    blurb: "Messages and posts from your Facebook Page.",
    userTokenHelp: "Optional — to refresh the page token when it expires.",
    instagramIdHelp: "Optional — if the page is connected to an IG account.",
  },
  instagram: {
    blurb: "IG Business by token. To publish and moderate comments, use the Instagram section in the menu.",
  },
};
