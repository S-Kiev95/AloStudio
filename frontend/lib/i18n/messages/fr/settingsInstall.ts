import type { settingsInstall as es } from "../es/settingsInstall";
import type { Strings } from "../types";

export const settingsInstall: Strings<typeof es> = {
  configuredCount: "{done}/{total} configurés",
  netConfigured: "configuré",
  netNotConfigured: "non configuré",
  operatorOnly: "Seul l’opérateur de l’installation peut voir cet écran. Demandez l’accès à la personne qui l’a déployée.",
  loadFailed: "Impossible de charger la configuration.",
  intro: "Des paramètres valables pour tout AloStudio, pas pour un seul compte. Vous pouvez les laisser vides et les remplir quand vous aurez les identifiants — l’app fonctionne sans eux, et chaque fonction vous indique ce qui lui manque.",
  network: "Réseau",
  clearFailed: "Impossible d’effacer.",
  notConfigured: "Non configuré",
  configured: "Configuré",
  savedHere: "enregistré ici",
  resetToServer: "revenir à la valeur du serveur",
  fromEnv: "provient du fichier du serveur (.env)",
  groups: {
    meta: "Meta (Facebook et Instagram)",
    mail: "E-mail sortant",
    publishing: "Réseaux de publication",
    access: "Accès",
    webhooks: "Webhooks",
    brand: "Marque",
    ai: "Intelligence artificielle",
  },
  items: {
    META_APP_ID: {
      title: "App ID Facebook",
      description: "Identifie AloStudio auprès de Meta dans le flux Facebook Login. Il y en a un seul pour toute l’installation, pas un par client.",
    },
    META_APP_SECRET: {
      title: "App Secret Facebook",
      description: "La clé secrète de la même app. Elle sert à l’échange de jetons.",
    },
    META_INSTAGRAM_APP_ID: {
      title: "App ID Instagram",
      description: "Pour le flux Instagram Login, qui n’a pas besoin de Page Facebook. C’est une app différente de celle de Facebook.",
    },
    META_INSTAGRAM_APP_SECRET: {
      title: "App Secret Instagram",
      description: "La clé secrète de l’app Instagram.",
    },
    META_OAUTH_REDIRECT_URI: {
      title: "URL de redirection OAuth",
      description: "Où revient le navigateur après l’autorisation. Elle doit correspondre *exactement* à celle saisie dans le tableau de bord Meta, y compris le https et la barre finale.",
    },
    SMTP_HOST: {
      title: "Serveur SMTP",
      description: "Par où partent les e-mails d’AloStudio (réinitialisation du mot de passe, confirmations, invitations, avis). Avec Gmail : smtp.gmail.com.",
    },
    SMTP_PORT: {
      title: "Port SMTP",
      description: "Avec Gmail : 465 (avec TLS activé).",
    },
    SMTP_TLS: {
      title: "Connexion chiffrée (TLS)",
      description: "Activé pour le port 465 (Gmail).",
    },
    SMTP_USER: {
      title: "Utilisateur SMTP",
      description: "Avec Gmail : l’adresse complète du compte expéditeur.",
    },
    SMTP_PASSWORD: {
      title: "Mot de passe SMTP",
      description: "Avec Gmail : un mot de passe d’application de 16 lettres (Compte Google → Sécurité → Mots de passe des applications ; nécessite la validation en deux étapes). Pas celui de votre compte.",
    },
    MAIL_FROM: {
      title: "Expéditeur",
      description: "Qui apparaît comme expéditeur, par exemple \"AloStudio <votremail@gmail.com>\". Avec Gmail, ce doit être le même compte.",
    },
    PUBLISHING_OAUTH_REDIRECT_URI: {
      title: "URL de redirection pour connecter les réseaux",
      description: "Une seule URL pour tous les réseaux connectés depuis le calendrier (Threads, LinkedIn, TikTok, X et ceux qui s’ajouteront) : où revient le navigateur après l’autorisation. C’est https://<votre domaine>/api/v1/publishing/oauth/callback et elle se saisit de la même façon dans l’app développeur de chaque réseau.",
    },
    THREADS_APP_ID: {
      title: "App ID Threads",
      description: "Le \"Threads App ID\" de l’app Meta (Paramètres de base), différent des App ID Facebook et Instagram.",
    },
    THREADS_APP_SECRET: {
      title: "App Secret Threads",
      description: "La clé secrète Threads de la même app.",
    },
    LINKEDIN_CLIENT_ID: {
      title: "Client ID LinkedIn",
      description: "De l’app sur linkedin.com/developers, onglet Auth.",
    },
    LINKEDIN_CLIENT_SECRET: {
      title: "Client Secret LinkedIn",
      description: "Le Primary Client Secret du même onglet Auth.",
    },
    TIKTOK_CLIENT_KEY: {
      title: "Client key TikTok",
      description: "De l’app sur developers.tiktok.com, section App details → Credentials.",
    },
    TIKTOK_CLIENT_SECRET: {
      title: "Client secret TikTok",
      description: "Le Client secret de la même section.",
    },
    TIKTOK_VERIFICATION_FILE: {
      title: "Fichier de vérification TikTok : nom",
      description: "En vérifiant le préfixe d’URL https://<domaine>/ dans l’app TikTok (URL properties), TikTok fournit un fichier à télécharger. Collez ici son nom exact, par exemple tiktokAbC123.txt. La production et chaque sandbox en donnent un différent : séparez-les par des virgules.",
    },
    TIKTOK_VERIFICATION_CONTENT: {
      title: "Fichier de vérification TikTok : contenu",
      description: "Le texte contenu dans ce fichier (ouvrez-le avec le Bloc-notes). S’il y a plusieurs fichiers, collez le texte de chacun séparé par des virgules.",
    },
    X_CLIENT_ID: {
      title: "Client ID X",
      description: "De l’app sur console.x.com, section Keys and tokens → OAuth 2.0. L’app doit être de type Web App, avec autorisation de lecture et d’écriture.",
    },
    X_CLIENT_SECRET: {
      title: "Client Secret X",
      description: "Le OAuth 2.0 Client Secret de la même section.",
    },
    ENABLE_ACCOUNT_SIGNUP: {
      title: "Inscription ouverte",
      description: "Permet à quiconque arrive sur l’URL de créer un compte et d’entrer comme administrateur, sans confirmer son e-mail. Désactivé, seul l’opérateur crée les comptes. Activez-le uniquement si l’installation est en libre-service.",
    },
    GOOGLE_CLIENT_ID: {
      title: "Connexion avec Google : Client ID",
      description: "De l’ID client OAuth (application Web) sur console.cloud.google.com. Avec cette valeur et le secret, l’écran de connexion affiche « Se connecter avec Google ». Seuls les utilisateurs déjà invités peuvent entrer. URL de redirection autorisée : https://<domaine>/auth/google/callback.",
    },
    GOOGLE_CLIENT_SECRET: {
      title: "Connexion avec Google : Client secret",
      description: "Le secret du même ID client OAuth.",
    },
    GOOGLE_ALLOWED_DOMAIN: {
      title: "Connexion avec Google : domaine autorisé",
      description: "Facultatif. Un domaine Google Workspace (par exemple, monecole.fr) : seuls les comptes de ce domaine sont acceptés. Vide, n’importe quel compte Google avec l’e-mail d’un utilisateur invité.",
    },
    META_VERIFY_WEBHOOK_SIGNATURE: {
      title: "Vérifier la signature des webhooks",
      description: "Rejette les webhooks Meta dont la signature n’est pas valide. Nécessite l’App Secret. Laissez-le activé en production.",
    },
    FB_VERIFY_TOKEN: {
      title: "Jeton de vérification Messenger",
      description: "Le texte saisi dans le tableau de bord Meta en enregistrant le webhook Messenger. Meta le renvoie pour vérifier que l’URL vous appartient.",
    },
    IG_VERIFY_TOKEN: {
      title: "Jeton de vérification Instagram",
      description: "Pareil, pour le webhook Instagram.",
    },
    APP_BASE_URL: {
      title: "URL publique du tableau de bord",
      description: "L’adresse utilisée pour construire les liens des e-mails, des pièces jointes et du retour OAuth.",
    },
    OPENAI_API_KEY: {
      title: "Clé OpenAI",
      description: "Utilisée par l’agent de chat et la recherche du Help Center. Elle se crée sur platform.openai.com et est facturée à l’usage sur ce compte.",
    },
    OPENAI_AGENT_MODEL: {
      title: "Modèle de l’agent",
      description: "Le modèle OpenAI qu’utilise l’agent de chat, par exemple gpt-5.4-mini (rapide et économique) ou gpt-5.5 (plus performant).",
    },
  },
};
