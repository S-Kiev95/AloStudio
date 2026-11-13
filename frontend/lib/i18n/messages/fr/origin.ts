import type { origin as es } from "../es/origin";
import type { Strings } from "../types";

export const origin: Strings<typeof es> = {
  title: "Origine",
  set: "Indiquer l’origine",
  source: "Comment il est arrivé",
  channel: "Canal",
  detail: "Détail",
  detailPlaceholder: "Ex. : recommandé par Juan, salon d’octobre…",
  unknown: "Non indiquée",
  noChannel: "Aucun",
  none: "On ne sait pas encore comment il est arrivé.",
  since: "Depuis le {date}",
  saveFailed: "Impossible d’enregistrer l’origine.",
  sources: {
    channel: "A écrit sur un canal",
    ad: "Publicité",
    post: "Publication",
    shortlink: "Lien direct",
    referral: "Recommandation",
    event: "Événement ou salon",
    walk_in: "Visite en personne",
    phone: "Appel",
    website: "Site web",
    other: "Autre",
  },
  channels: {
    whatsapp: "WhatsApp",
    instagram: "Instagram",
    facebook: "Facebook",
    web: "Chat du site",
    email: "E-mail",
    telegram: "Telegram",
    sms: "SMS",
    api: "API",
  },
};
