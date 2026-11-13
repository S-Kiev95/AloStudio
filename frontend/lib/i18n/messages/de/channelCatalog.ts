import type { channelCatalog as es } from "../es/channelCatalog";
import type { Strings } from "../types";

export const channelCatalog: Strings<typeof es> = {
  telegram: {
    blurb: "Verbinde einen Telegram-Bot mit dem Token von BotFather.",
    tokenHelp: "Das Token, das dir @BotFather beim Erstellen des Bots gegeben hat.",
    botName: "Name des Bots",
    botNameHelp: "Optional — der @username des Bots.",
  },
  whatsapp: {
    blurb: "WhatsApp-Business-Nummer über die Cloud API von Meta.",
  },
  phoneNumber: "Telefonnummer",
  sms: {
    blurb: "SMS-Nummer über Bandwidth.",
  },
  twilio: {
    blurb: "Twilio-Nummer für SMS oder WhatsApp.",
    medium: "Medium",
  },
  email: {
    blurb: "Ein Postfach als Support-Kanal.",
    address: "E-Mail-Adresse",
    imapEnabled: "E-Mails empfangen (IMAP)",
    imapHelp: "Ohne das kommt nicht im Posteingang an, was dir geschrieben wird.",
    imapServer: "IMAP-Server",
    imapPort: "IMAP-Port",
    imapUser: "IMAP-Benutzername",
    imapPassword: "IMAP-Passwort",
    appPasswordHelp: "Wenn du die Bestätigung in zwei Schritten nutzt, verwende ein App-Passwort.",
    imapSsl: "Sichere IMAP-Verbindung (SSL)",
    smtpEnabled: "E-Mails senden (SMTP)",
    smtpServer: "SMTP-Server",
    smtpPort: "SMTP-Port",
    smtpUser: "SMTP-Benutzername",
    smtpPassword: "SMTP-Passwort",
    smtpStarttls: "Sichere SMTP-Verbindung (STARTTLS)",
  },
  web: {
    blurb: "Eingebetteter Chat für deine Website.",
    siteUrl: "URL der Website",
    welcomeTitle: "Begrüßungstitel",
    welcomePlaceholder: "Hallo! 👋",
    tagline: "Untertitel",
  },
  api: {
    blurb: "Generischer Kanal über eine HTTP-API (optionaler ausgehender Webhook).",
    webhookHelp: "Optional — wohin wir eingehende Nachrichten weiterleiten.",
  },
  facebook: {
    blurb: "Nachrichten und Beiträge deiner Facebook-Seite.",
    userTokenHelp: "Optional — um das Seiten-Token nach Ablauf zu erneuern.",
    instagramIdHelp: "Optional — wenn die Seite mit einem IG-Konto verbunden ist.",
  },
  instagram: {
    blurb: "IG Business per Token. Zum Veröffentlichen und Moderieren von Kommentaren nutze den Bereich Instagram im Menü.",
  },
};
