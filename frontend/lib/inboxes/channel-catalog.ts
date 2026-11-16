import type { ChannelType } from "@/lib/api/inboxes";

/**
 * Channel catalogue — the data that drives both the "add channel" picker and
 * the generic per-channel form. Field shapes mirror the backend
 * `InboxBuilder` validation (`app/domains/inboxes/service.py`). `name`
 * supports a dotted path (`provider_config.api_key`) which the form nests
 * into the channel payload; `fixed` values are always sent.
 *
 * `label`, `blurb`, `help` and `placeholder` hold a dictionary key or, for
 * product and API names ("Bot token", "Page ID"), the literal text: render
 * them through `t()`, which hands back what it doesn't know.
 */
export type FieldType = "text" | "password" | "checkbox" | "select";

export type ChannelField = {
  name: string;
  label: string;
  type: FieldType;
  /** Checkbox only. Ticked unless the author unticks it — a security
   *  switch that defaults off is one nobody remembers to turn on. */
  default?: boolean;
  required?: boolean;
  placeholder?: string;
  help?: string;
  options?: { value: string; label: string }[];
};

export type ChannelDef = {
  type: ChannelType;
  label: string;
  blurb: string;
  /** Constant channel params always sent (e.g. whatsapp provider). */
  fixed?: Record<string, unknown>;
  fields: ChannelField[];
};

// i18n-ignore-start: the texts in Spanish are dictionary keys now; what's
// left in English are product and API field names, rendered as they are.
export const CHANNEL_CATALOG: ChannelDef[] = [
  {
    type: "telegram",
    label: "Telegram",
    blurb: "channelCatalog.telegram.blurb",
    fields: [
      {
        name: "bot_token",
        label: "Bot token",
        type: "password",
        required: true,
        placeholder: "123456789:AA…",
        help: "channelCatalog.telegram.tokenHelp",
      },
      {
        name: "bot_name",
        label: "channelCatalog.telegram.botName",
        type: "text",
        placeholder: "MiNegocioBot",
        help: "channelCatalog.telegram.botNameHelp",
      },
    ],
  },
  {
    type: "whatsapp",
    label: "WhatsApp (Cloud API)",
    blurb: "channelCatalog.whatsapp.blurb",
    fixed: { provider: "whatsapp_cloud" },
    fields: [
      {
        name: "phone_number",
        label: "channelCatalog.phoneNumber",
        type: "text",
        required: true,
        placeholder: "+5491122334455",
      },
      {
        name: "provider_config.api_key",
        label: "API key (access token)",
        type: "password",
        required: true,
      },
      {
        name: "provider_config.phone_number_id",
        label: "Phone number ID",
        type: "text",
        required: true,
      },
      {
        name: "provider_config.business_account_id",
        label: "Business account ID",
        type: "text",
        required: true,
      },
    ],
  },
  {
    type: "sms",
    label: "SMS (Bandwidth)",
    blurb: "channelCatalog.sms.blurb",
    fields: [
      {
        name: "phone_number",
        label: "channelCatalog.phoneNumber",
        type: "text",
        required: true,
        placeholder: "+15551234567",
      },
      {
        name: "provider_config.account_id",
        label: "Account ID",
        type: "text",
        required: true,
      },
      {
        name: "provider_config.api_token",
        label: "API token",
        type: "password",
        required: true,
      },
      {
        name: "provider_config.api_secret",
        label: "API secret",
        type: "password",
        required: true,
      },
      {
        name: "provider_config.application_id",
        label: "Application ID",
        type: "text",
        required: true,
      },
    ],
  },
  {
    type: "twilio_sms",
    label: "Twilio (SMS / WhatsApp)",
    blurb: "channelCatalog.twilio.blurb",
    fields: [
      {
        name: "account_sid",
        label: "Account SID",
        type: "text",
        required: true,
        placeholder: "ACxxxxxxxx",
      },
      {
        name: "auth_token",
        label: "Auth token",
        type: "password",
        required: true,
      },
      {
        name: "phone_number",
        label: "channelCatalog.phoneNumber",
        type: "text",
        required: true,
        placeholder: "+15551234567",
      },
      {
        name: "medium",
        label: "channelCatalog.twilio.medium",
        type: "select",
        options: [
          { value: "sms", label: "SMS" },
          { value: "whatsapp", label: "WhatsApp" },
        ],
      },
    ],
  },
  {
    type: "email",
    label: "Email",
    blurb: "channelCatalog.email.blurb",
    fields: [
      {
        name: "email",
        label: "channelCatalog.email.address",
        type: "text",
        required: true,
        placeholder: "soporte@tudominio.com",
      },
      // The credentials belong here, not only on the detail screen: a
      // mailbox created without them neither sends nor receives, and
      // nothing on the create form said so. Optional, because
      // receive-only and send-only are real configurations and the
      // server only demands the rest of a side once it is switched on.
      {
        name: "imap_enabled",
        label: "channelCatalog.email.imapEnabled",
        type: "checkbox",
        help: "channelCatalog.email.imapHelp",
      },
      {
        name: "imap_address",
        label: "channelCatalog.email.imapServer",
        type: "text",
        placeholder: "imap.gmail.com",
      },
      { name: "imap_port", label: "channelCatalog.email.imapPort", type: "text", placeholder: "993" },
      {
        name: "imap_login",
        label: "channelCatalog.email.imapUser",
        type: "text",
        placeholder: "soporte@tudominio.com",
      },
      {
        name: "imap_password",
        label: "channelCatalog.email.imapPassword",
        type: "password",
        help: "channelCatalog.email.appPasswordHelp",
      },
      {
        name: "imap_enable_ssl",
        label: "channelCatalog.email.imapSsl",
        type: "checkbox",
        default: true,
        help: "settingsInboxes.sslHint",
      },
      {
        name: "smtp_enabled",
        label: "channelCatalog.email.smtpEnabled",
        type: "checkbox",
        help: "settingsInboxes.smtpHint",
      },
      {
        name: "smtp_address",
        label: "channelCatalog.email.smtpServer",
        type: "text",
        placeholder: "smtp.gmail.com",
      },
      { name: "smtp_port", label: "channelCatalog.email.smtpPort", type: "text", placeholder: "587" },
      {
        name: "smtp_login",
        label: "channelCatalog.email.smtpUser",
        type: "text",
        placeholder: "soporte@tudominio.com",
      },
      { name: "smtp_password", label: "channelCatalog.email.smtpPassword", type: "password" },
      {
        name: "smtp_enable_starttls_auto",
        label: "channelCatalog.email.smtpStarttls",
        type: "checkbox",
        default: true,
        help: "settingsInboxes.starttlsHint",
      },
    ],
  },
  {
    type: "web_widget",
    label: "Web widget",
    blurb: "channelCatalog.web.blurb",
    fields: [
      {
        name: "website_url",
        label: "channelCatalog.web.siteUrl",
        type: "text",
        required: true,
        placeholder: "https://tudominio.com",
      },
      {
        name: "welcome_title",
        label: "channelCatalog.web.welcomeTitle",
        type: "text",
        placeholder: "channelCatalog.web.welcomePlaceholder",
      },
      {
        name: "welcome_tagline",
        label: "channelCatalog.web.tagline",
        type: "text",
      },
    ],
  },
  {
    type: "api",
    label: "API",
    blurb: "channelCatalog.api.blurb",
    fields: [
      {
        name: "webhook_url",
        label: "Webhook URL",
        type: "text",
        placeholder: "https://tu-servicio.com/webhook",
        help: "channelCatalog.api.webhookHelp",
      },
    ],
  },
  {
    type: "facebook",
    label: "Facebook Messenger",
    blurb: "channelCatalog.facebook.blurb",
    fields: [
      {
        name: "page_id",
        label: "Page ID",
        type: "text",
        required: true,
      },
      {
        name: "page_access_token",
        label: "Page access token",
        type: "password",
        required: true,
      },
      {
        name: "user_access_token",
        label: "User access token",
        type: "password",
        help: "channelCatalog.facebook.userTokenHelp",
      },
      {
        name: "instagram_id",
        label: "Instagram ID",
        type: "text",
        help: "channelCatalog.facebook.instagramIdHelp",
      },
    ],
  },
  {
    type: "instagram",
    label: "Instagram (Direct)",
    blurb:
      "channelCatalog.instagram.blurb",
    fields: [
      {
        name: "instagram_id",
        label: "Instagram ID",
        type: "text",
        required: true,
      },
      {
        name: "access_token",
        label: "Access token",
        type: "password",
        required: true,
      },
    ],
  },
];
// i18n-ignore-end

export function channelDef(type: string): ChannelDef | undefined {
  return CHANNEL_CATALOG.find((c) => c.type === type);
}
