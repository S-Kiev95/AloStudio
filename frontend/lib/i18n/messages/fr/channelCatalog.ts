import type { channelCatalog as es } from "../es/channelCatalog";
import type { Strings } from "../types";

export const channelCatalog: Strings<typeof es> = {
  telegram: {
    blurb: "Connectez un bot Telegram avec le jeton de BotFather.",
    tokenHelp: "Le jeton que @BotFather vous a donné en créant le bot.",
    botName: "Nom du bot",
    botNameHelp: "Facultatif — le @username du bot.",
  },
  whatsapp: {
    blurb: "Numéro WhatsApp Business via la Cloud API de Meta.",
  },
  phoneNumber: "Numéro de téléphone",
  sms: {
    blurb: "Numéro SMS via Bandwidth.",
  },
  twilio: {
    blurb: "Numéro Twilio pour SMS ou WhatsApp.",
    medium: "Support",
  },
  email: {
    blurb: "Une boîte e-mail comme canal d’assistance.",
    address: "Adresse e-mail",
    imapEnabled: "Recevoir les e-mails (IMAP)",
    imapHelp: "Sans cela, ce qu’on vous écrit n’arrive pas dans la boîte de réception.",
    imapServer: "Serveur IMAP",
    imapPort: "Port IMAP",
    imapUser: "Utilisateur IMAP",
    imapPassword: "Mot de passe IMAP",
    appPasswordHelp: "Si vous utilisez la validation en deux étapes, utilisez un mot de passe d’application.",
    imapSsl: "Connexion IMAP sécurisée (SSL)",
    smtpEnabled: "Envoyer les e-mails (SMTP)",
    smtpServer: "Serveur SMTP",
    smtpPort: "Port SMTP",
    smtpUser: "Utilisateur SMTP",
    smtpPassword: "Mot de passe SMTP",
    smtpStarttls: "Connexion SMTP sécurisée (STARTTLS)",
  },
  web: {
    blurb: "Chat intégré pour votre site web.",
    siteUrl: "URL du site",
    welcomeTitle: "Titre de bienvenue",
    welcomePlaceholder: "Bonjour ! 👋",
    tagline: "Sous-titre",
  },
  api: {
    blurb: "Canal générique via API HTTP (webhook sortant facultatif).",
    webhookHelp: "Facultatif — où nous transférons les messages entrants.",
  },
  facebook: {
    blurb: "Messages et publications de votre Page Facebook.",
    userTokenHelp: "Facultatif — pour renouveler le jeton de la page à son expiration.",
    instagramIdHelp: "Facultatif — si la page est connectée à un compte IG.",
  },
  instagram: {
    blurb: "IG Business par jeton. Pour publier et modérer les commentaires, utilisez la section Instagram du menu.",
  },
};
