import type { origin as es } from "../es/origin";
import type { Strings } from "../types";

export const origin: Strings<typeof es> = {
  title: "Origem",
  set: "Indicar origem",
  source: "Como chegou",
  channel: "Canal",
  detail: "Detalhe",
  detailPlaceholder: "Ex.: indicada pelo Juan, feira de outubro…",
  unknown: "Não indicada",
  noChannel: "Nenhum",
  none: "Ainda não se sabe como chegou.",
  since: "Desde {date}",
  saveFailed: "Não foi possível salvar a origem.",
  sources: {
    channel: "Escreveu por um canal",
    ad: "Anúncio",
    post: "Publicação",
    shortlink: "Link direto",
    referral: "Indicação",
    event: "Evento ou feira",
    walk_in: "Visita presencial",
    phone: "Ligação",
    website: "Site",
    other: "Outro",
  },
  channels: {
    whatsapp: "WhatsApp",
    instagram: "Instagram",
    facebook: "Facebook",
    web: "Chat do site",
    email: "E-mail",
    telegram: "Telegram",
    sms: "SMS",
    api: "API",
  },
};
