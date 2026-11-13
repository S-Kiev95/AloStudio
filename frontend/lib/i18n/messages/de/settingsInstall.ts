import type { settingsInstall as es } from "../es/settingsInstall";
import type { Strings } from "../types";

export const settingsInstall: Strings<typeof es> = {
  configuredCount: "{done}/{total} eingerichtet",
  netConfigured: "eingerichtet",
  netNotConfigured: "nicht eingerichtet",
  operatorOnly: "Nur der Betreiber der Installation kann diese Seite sehen. Bitte die Person, die sie bereitgestellt hat, um Zugang.",
  loadFailed: "Die Konfiguration konnte nicht geladen werden.",
  intro: "Einstellungen, die für ganz AloStudio gelten, nicht für ein Konto. Du kannst sie leer lassen und ausfüllen, sobald du die Zugangsdaten hast — die App funktioniert ohne sie, und jede Funktion sagt dir, was ihr fehlt.",
  network: "Netzwerk",
  clearFailed: "Löschen nicht möglich.",
  notConfigured: "Nicht eingerichtet",
  configured: "Eingerichtet",
  savedHere: "hier gespeichert",
  resetToServer: "auf den Serverwert zurücksetzen",
  fromEnv: "stammt aus der Serverdatei (.env)",
  groups: {
    meta: "Meta (Facebook und Instagram)",
    mail: "Ausgehende E-Mail",
    publishing: "Netzwerke zum Veröffentlichen",
    access: "Zugang",
    webhooks: "Webhooks",
    brand: "Marke",
    ai: "Künstliche Intelligenz",
  },
  items: {
    META_APP_ID: {
      title: "Facebook App ID",
      description: "Identifiziert AloStudio gegenüber Meta im Facebook-Login-Ablauf. Es gibt eine für die ganze Installation, nicht eine pro Kunde.",
    },
    META_APP_SECRET: {
      title: "Facebook App Secret",
      description: "Der geheime Schlüssel derselben App. Wird für den Token-Austausch verwendet.",
    },
    META_INSTAGRAM_APP_ID: {
      title: "Instagram App ID",
      description: "Für den Instagram-Login-Ablauf, der keine Facebook-Seite braucht. Es ist eine andere App als die von Facebook.",
    },
    META_INSTAGRAM_APP_SECRET: {
      title: "Instagram App Secret",
      description: "Der geheime Schlüssel der Instagram-App.",
    },
    META_OAUTH_REDIRECT_URI: {
      title: "OAuth-Weiterleitungs-URL",
      description: "Wohin der Browser nach der Autorisierung zurückkehrt. Sie muss *genau* der im Meta-Dashboard eingetragenen entsprechen, einschließlich https und abschließendem Schrägstrich.",
    },
    SMTP_HOST: {
      title: "SMTP-Server",
      description: "Worüber die E-Mails von AloStudio verschickt werden (Passwort zurücksetzen, Bestätigungen, Einladungen, Hinweise). Mit Gmail: smtp.gmail.com.",
    },
    SMTP_PORT: {
      title: "SMTP-Port",
      description: "Mit Gmail: 465 (mit aktiviertem TLS).",
    },
    SMTP_TLS: {
      title: "Verschlüsselte Verbindung (TLS)",
      description: "Aktiviert für Port 465 (Gmail).",
    },
    SMTP_USER: {
      title: "SMTP-Benutzername",
      description: "Mit Gmail: die vollständige Adresse des sendenden Kontos.",
    },
    SMTP_PASSWORD: {
      title: "SMTP-Passwort",
      description: "Mit Gmail: ein App-Passwort mit 16 Buchstaben (Google-Konto → Sicherheit → App-Passwörter; erfordert die Bestätigung in zwei Schritten). Nicht das Passwort deines Kontos.",
    },
    MAIL_FROM: {
      title: "Absender",
      description: "Wer als Absender erscheint, zum Beispiel \"AloStudio <deinemail@gmail.com>\". Mit Gmail muss es dasselbe Konto sein.",
    },
    PUBLISHING_OAUTH_REDIRECT_URI: {
      title: "Weiterleitungs-URL beim Verbinden von Netzwerken",
      description: "Eine einzige URL für alle Netzwerke, die über den Kalender verbunden werden (Threads, LinkedIn, TikTok, X und künftige): wohin der Browser nach der Autorisierung zurückkehrt. Sie lautet https://<deine Domain>/api/v1/publishing/oauth/callback und wird in der Entwickler-App jedes Netzwerks gleich eingetragen.",
    },
    THREADS_APP_ID: {
      title: "Threads App ID",
      description: "Die \"Threads App ID\" der Meta-App (Grundeinstellungen), verschieden von den App IDs von Facebook und Instagram.",
    },
    THREADS_APP_SECRET: {
      title: "Threads App Secret",
      description: "Der geheime Threads-Schlüssel derselben App.",
    },
    LINKEDIN_CLIENT_ID: {
      title: "LinkedIn Client ID",
      description: "Aus der App auf linkedin.com/developers, Tab Auth.",
    },
    LINKEDIN_CLIENT_SECRET: {
      title: "LinkedIn Client Secret",
      description: "Das Primary Client Secret aus demselben Tab Auth.",
    },
    TIKTOK_CLIENT_KEY: {
      title: "TikTok Client Key",
      description: "Aus der App auf developers.tiktok.com, Bereich App details → Credentials.",
    },
    TIKTOK_CLIENT_SECRET: {
      title: "TikTok Client Secret",
      description: "Das Client Secret aus demselben Bereich.",
    },
    TIKTOK_VERIFICATION_FILE: {
      title: "TikTok-Verifizierungsdatei: Name",
      description: "Beim Verifizieren des URL-Präfixes https://<Domain>/ in der TikTok-App (URL properties) gibt TikTok eine Datei zum Herunterladen. Füge hier genau ihren Namen ein, zum Beispiel tiktokAbC123.txt. Produktion und jede Sandbox geben eine andere: trenne sie mit Kommas.",
    },
    TIKTOK_VERIFICATION_CONTENT: {
      title: "TikTok-Verifizierungsdatei: Inhalt",
      description: "Der Text in dieser Datei (öffne sie mit dem Editor). Bei mehreren Dateien füge den Text jeder Datei durch Kommas getrennt ein.",
    },
    X_CLIENT_ID: {
      title: "X Client ID",
      description: "Aus der App auf console.x.com, Bereich Keys and tokens → OAuth 2.0. Die App muss vom Typ Web App sein, mit Lese- und Schreibberechtigung.",
    },
    X_CLIENT_SECRET: {
      title: "X Client Secret",
      description: "Das OAuth 2.0 Client Secret aus demselben Bereich.",
    },
    ENABLE_ACCOUNT_SIGNUP: {
      title: "Offene Kontoregistrierung",
      description: "Lässt jeden, der die URL aufruft, ein Konto erstellen und als Administrator einsteigen, ohne die E-Mail zu bestätigen. Ausgeschaltet legt nur der Betreiber Konten an. Nur aktivieren, wenn die Installation Selbstbedienung ist.",
    },
    GOOGLE_CLIENT_ID: {
      title: "Mit Google anmelden: Client ID",
      description: "Aus der OAuth-Client-ID (Webanwendung) auf console.cloud.google.com. Mit diesem Wert und dem Secret zeigt die Anmeldeseite „Mit Google anmelden“. Nur bereits eingeladene Benutzer kommen rein. Autorisierte Weiterleitungs-URL: https://<Domain>/auth/google/callback.",
    },
    GOOGLE_CLIENT_SECRET: {
      title: "Mit Google anmelden: Client Secret",
      description: "Das Secret derselben OAuth-Client-ID.",
    },
    GOOGLE_ALLOWED_DOMAIN: {
      title: "Mit Google anmelden: erlaubte Domain",
      description: "Optional. Eine Google-Workspace-Domain (zum Beispiel meineschule.de): nur Konten dieser Domain werden akzeptiert. Leer: jedes Google-Konto mit der E-Mail eines eingeladenen Benutzers.",
    },
    META_VERIFY_WEBHOOK_SIGNATURE: {
      title: "Webhook-Signatur prüfen",
      description: "Lehnt Meta-Webhooks ab, deren Signatur nicht gültig ist. Benötigt das App Secret. In der Produktion aktiviert lassen.",
    },
    FB_VERIFY_TOKEN: {
      title: "Messenger-Verifizierungstoken",
      description: "Der Text, den du im Meta-Dashboard beim Einrichten des Messenger-Webhooks eingegeben hast. Meta wiederholt ihn, um zu prüfen, dass die URL dir gehört.",
    },
    IG_VERIFY_TOKEN: {
      title: "Instagram-Verifizierungstoken",
      description: "Dasselbe für den Instagram-Webhook.",
    },
    APP_BASE_URL: {
      title: "Öffentliche URL des Dashboards",
      description: "Mit welcher Adresse die Links in E-Mails, Anhängen und der OAuth-Rückkehr gebaut werden.",
    },
    OPENAI_API_KEY: {
      title: "OpenAI-Schlüssel",
      description: "Wird vom Chat-Agenten und der Help-Center-Suche verwendet. Erstellt auf platform.openai.com und nach Nutzung über dieses Konto abgerechnet.",
    },
    OPENAI_AGENT_MODEL: {
      title: "Modell des Agenten",
      description: "Das OpenAI-Modell, das der Chat-Agent verwendet, zum Beispiel gpt-5.4-mini (schnell und günstig) oder gpt-5.5 (leistungsfähiger).",
    },
  },
};
