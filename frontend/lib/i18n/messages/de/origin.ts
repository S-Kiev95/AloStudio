import type { origin as es } from "../es/origin";
import type { Strings } from "../types";

export const origin: Strings<typeof es> = {
  title: "Herkunft",
  set: "Herkunft angeben",
  source: "Wie der Kontakt kam",
  channel: "Kanal",
  detail: "Detail",
  detailPlaceholder: "z. B. von Juan empfohlen, Messe im Oktober…",
  unknown: "Nicht angegeben",
  noChannel: "Keiner",
  none: "Noch nicht bekannt, wie der Kontakt kam.",
  since: "Seit {date}",
  saveFailed: "Die Herkunft konnte nicht gespeichert werden.",
  sources: {
    channel: "Über einen Kanal geschrieben",
    ad: "Anzeige",
    post: "Beitrag",
    shortlink: "Direktlink",
    referral: "Empfehlung",
    event: "Veranstaltung oder Messe",
    walk_in: "Persönlicher Besuch",
    phone: "Anruf",
    website: "Website",
    other: "Sonstiges",
  },
  channels: {
    whatsapp: "WhatsApp",
    instagram: "Instagram",
    facebook: "Facebook",
    web: "Website-Chat",
    email: "E-Mail",
    telegram: "Telegram",
    sms: "SMS",
    api: "API",
  },
};
