import type { ChannelType } from "@/lib/api/inboxes";

/**
 * Channel catalogue — the data that drives both the "add channel" picker and
 * the generic per-channel form. Field shapes mirror the backend
 * `InboxBuilder` validation (`app/domains/inboxes/service.py`). `name`
 * supports a dotted path (`provider_config.api_key`) which the form nests
 * into the channel payload; `fixed` values are always sent.
 */
export type FieldType = "text" | "password" | "checkbox" | "select";

export type ChannelField = {
  name: string;
  label: string;
  type: FieldType;
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

export const CHANNEL_CATALOG: ChannelDef[] = [
  {
    type: "telegram",
    label: "Telegram",
    blurb: "Conectá un bot de Telegram con el token de BotFather.",
    fields: [
      {
        name: "bot_token",
        label: "Bot token",
        type: "password",
        required: true,
        placeholder: "123456789:AA…",
        help: "El token que te dio @BotFather al crear el bot.",
      },
      {
        name: "bot_name",
        label: "Nombre del bot",
        type: "text",
        placeholder: "MiNegocioBot",
        help: "Opcional — el @username del bot.",
      },
    ],
  },
  {
    type: "whatsapp",
    label: "WhatsApp (Cloud API)",
    blurb: "Número de WhatsApp Business vía la Cloud API de Meta.",
    fixed: { provider: "whatsapp_cloud" },
    fields: [
      {
        name: "phone_number",
        label: "Número de teléfono",
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
    blurb: "Número de SMS a través de Bandwidth.",
    fields: [
      {
        name: "phone_number",
        label: "Número de teléfono",
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
    blurb: "Número de Twilio para SMS o WhatsApp.",
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
        label: "Número de teléfono",
        type: "text",
        required: true,
        placeholder: "+15551234567",
      },
      {
        name: "medium",
        label: "Medio",
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
    blurb: "Una casilla de correo como canal de soporte.",
    fields: [
      {
        name: "email",
        label: "Dirección de email",
        type: "text",
        required: true,
        placeholder: "soporte@tudominio.com",
      },
    ],
  },
  {
    type: "web_widget",
    label: "Web widget",
    blurb: "Chat embebido para tu sitio web.",
    fields: [
      {
        name: "website_url",
        label: "URL del sitio",
        type: "text",
        required: true,
        placeholder: "https://tudominio.com",
      },
      {
        name: "welcome_title",
        label: "Título de bienvenida",
        type: "text",
        placeholder: "¡Hola! 👋",
      },
      {
        name: "welcome_tagline",
        label: "Subtítulo",
        type: "text",
      },
    ],
  },
  {
    type: "api",
    label: "API",
    blurb: "Canal genérico vía API HTTP (webhook saliente opcional).",
    fields: [
      {
        name: "webhook_url",
        label: "Webhook URL",
        type: "text",
        placeholder: "https://tu-servicio.com/webhook",
        help: "Opcional — adónde reenviamos los mensajes entrantes.",
      },
    ],
  },
  {
    type: "facebook",
    label: "Facebook Messenger",
    blurb: "Página de Facebook (token manual; el flujo OAuth llega después).",
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
        help: "Opcional — para refrescar el token de página al expirar.",
      },
      {
        name: "instagram_id",
        label: "Instagram ID",
        type: "text",
        help: "Opcional — si la página está conectada a una cuenta de IG.",
      },
    ],
  },
  {
    type: "instagram",
    label: "Instagram (Direct)",
    blurb:
      "IG Business por token. Para publicar y moderar comentarios, usá la sección Instagram del menú.",
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

export function channelDef(type: string): ChannelDef | undefined {
  return CHANNEL_CATALOG.find((c) => c.type === type);
}
