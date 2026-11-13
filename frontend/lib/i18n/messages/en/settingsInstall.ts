import type { settingsInstall as es } from "../es/settingsInstall";
import type { Strings } from "../types";

export const settingsInstall: Strings<typeof es> = {
  configuredCount: "{done}/{total} configured",
  netConfigured: "configured",
  netNotConfigured: "not configured",
  operatorOnly: "Only the installation's operator can see this screen. Ask whoever deployed it for access.",
  loadFailed: "Couldn't load the configuration.",
  intro: "Settings that apply to all of AloStudio, not to one account. You can leave them empty and fill them in when you have the credentials — the app works without them, and each feature tells you what it's missing.",
  network: "Network",
  clearFailed: "Couldn't clear it.",
  notConfigured: "Not configured",
  configured: "Configured",
  savedHere: "saved from here",
  resetToServer: "go back to the server value",
  fromEnv: "comes from the server file (.env)",
  groups: {
    meta: "Meta (Facebook and Instagram)",
    mail: "Outgoing mail",
    publishing: "Publishing networks",
    access: "Access",
    webhooks: "Webhooks",
    brand: "Brand",
    ai: "Artificial intelligence",
  },
  items: {
    META_APP_ID: {
      title: "Facebook App ID",
      description: "Identifies AloStudio to Meta in the Facebook Login flow. There's one for the whole installation, not one per client.",
    },
    META_APP_SECRET: {
      title: "Facebook App Secret",
      description: "The secret key of the same app. Used to exchange tokens.",
    },
    META_INSTAGRAM_APP_ID: {
      title: "Instagram App ID",
      description: "For the Instagram Login flow, which doesn't need a Facebook Page. It's a different app from the Facebook one.",
    },
    META_INSTAGRAM_APP_SECRET: {
      title: "Instagram App Secret",
      description: "The secret key of the Instagram app.",
    },
    META_OAUTH_REDIRECT_URI: {
      title: "OAuth redirect URL",
      description: "Where the browser returns after authorizing. It has to match *exactly* the one you entered in the Meta dashboard, including https and the trailing slash.",
    },
    SMTP_HOST: {
      title: "SMTP server",
      description: "Where AloStudio's emails go out (password resets, confirmations, invitations, notices). With Gmail: smtp.gmail.com.",
    },
    SMTP_PORT: {
      title: "SMTP port",
      description: "With Gmail: 465 (with TLS on).",
    },
    SMTP_TLS: {
      title: "Encrypted connection (TLS)",
      description: "On for port 465 (Gmail).",
    },
    SMTP_USER: {
      title: "SMTP username",
      description: "With Gmail: the full address of the sending account.",
    },
    SMTP_PASSWORD: {
      title: "SMTP password",
      description: "With Gmail: a 16-letter app password (Google Account → Security → App passwords; needs 2-Step Verification). Not your account password.",
    },
    MAIL_FROM: {
      title: "Sender",
      description: "Who appears as the sender, for example \"AloStudio <yourmail@gmail.com>\". With Gmail it has to be the same account.",
    },
    PUBLISHING_OAUTH_REDIRECT_URI: {
      title: "Redirect URL for connecting networks",
      description: "One URL for every network connected from the calendar (Threads, LinkedIn, TikTok, X and any added later): where the browser returns after authorizing. It's https://<your domain>/api/v1/publishing/oauth/callback and is entered the same way in each network's developer app.",
    },
    THREADS_APP_ID: {
      title: "Threads App ID",
      description: "The \"Threads App ID\" of the Meta app (Basic settings), different from the Facebook and Instagram App IDs.",
    },
    THREADS_APP_SECRET: {
      title: "Threads App Secret",
      description: "The Threads secret key of the same app.",
    },
    LINKEDIN_CLIENT_ID: {
      title: "LinkedIn Client ID",
      description: "From the app at linkedin.com/developers, Auth tab.",
    },
    LINKEDIN_CLIENT_SECRET: {
      title: "LinkedIn Client Secret",
      description: "The Primary Client Secret from the same Auth tab.",
    },
    TIKTOK_CLIENT_KEY: {
      title: "TikTok client key",
      description: "From the app at developers.tiktok.com, App details → Credentials.",
    },
    TIKTOK_CLIENT_SECRET: {
      title: "TikTok client secret",
      description: "The Client secret from the same section.",
    },
    TIKTOK_VERIFICATION_FILE: {
      title: "TikTok verification file: name",
      description: "When verifying the URL prefix https://<domain>/ in the TikTok app (URL properties), TikTok gives you a file to download. Paste its name here exactly, for example tiktokAbC123.txt. Production and each sandbox give a different one: separate them with commas.",
    },
    TIKTOK_VERIFICATION_CONTENT: {
      title: "TikTok verification file: content",
      description: "The text inside that file (open it with Notepad). If there are several files, paste the text of each separated by commas.",
    },
    X_CLIENT_ID: {
      title: "X Client ID",
      description: "From the app at console.x.com, Keys and tokens → OAuth 2.0. The app has to be a Web App, with read and write permission.",
    },
    X_CLIENT_SECRET: {
      title: "X Client Secret",
      description: "The OAuth 2.0 Client Secret from the same section.",
    },
    ENABLE_ACCOUNT_SIGNUP: {
      title: "Open account signup",
      description: "Lets anyone who reaches the URL create an account and get in as an administrator, without confirming their email. Off, only the operator creates accounts. Turn it on only if the installation is self-service.",
    },
    GOOGLE_CLIENT_ID: {
      title: "Sign in with Google: Client ID",
      description: "From the OAuth client ID (web application) at console.cloud.google.com. With this and the secret, the sign-in screen shows «Sign in with Google». Only already-invited users get in. Authorized redirect URL: https://<domain>/auth/google/callback.",
    },
    GOOGLE_CLIENT_SECRET: {
      title: "Sign in with Google: Client secret",
      description: "The secret of the same OAuth client ID.",
    },
    GOOGLE_ALLOWED_DOMAIN: {
      title: "Sign in with Google: allowed domain",
      description: "Optional. A Google Workspace domain (for example, myschool.edu): only accounts from that domain are accepted. Empty, any Google account with the email of an invited user.",
    },
    META_VERIFY_WEBHOOK_SIGNATURE: {
      title: "Verify webhook signatures",
      description: "Rejects Meta webhooks whose signature doesn't validate. Needs the App Secret. Keep it on in production.",
    },
    FB_VERIFY_TOKEN: {
      title: "Messenger verify token",
      description: "The text you entered in the Meta dashboard when registering the Messenger webhook. Meta repeats it to check the URL is yours.",
    },
    IG_VERIFY_TOKEN: {
      title: "Instagram verify token",
      description: "The same, for the Instagram webhook.",
    },
    APP_BASE_URL: {
      title: "Public dashboard URL",
      description: "The address used to build the links in emails, attachments and the OAuth return.",
    },
    OPENAI_API_KEY: {
      title: "OpenAI key",
      description: "Used by the chat agent and the Help Center search. Create it at platform.openai.com; it's billed by usage on that account.",
    },
    OPENAI_AGENT_MODEL: {
      title: "Agent model",
      description: "The OpenAI model the chat agent uses, for example gpt-5.4-mini (fast and cheap) or gpt-5.5 (more capable).",
    },
  },
};
