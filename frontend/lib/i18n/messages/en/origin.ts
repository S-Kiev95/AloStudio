import type { origin as es } from "../es/origin";
import type { Strings } from "../types";

export const origin: Strings<typeof es> = {
  title: "Origin",
  set: "Set origin",
  source: "How they came",
  channel: "Channel",
  detail: "Detail",
  detailPlaceholder: "E.g. referred by Juan, October fair…",
  unknown: "Not set",
  noChannel: "None",
  none: "How they came is not known yet.",
  since: "Since {date}",
  saveFailed: "Couldn't save the origin.",
  sources: {
    channel: "Wrote on a channel",
    ad: "Ad",
    post: "Post",
    shortlink: "Direct link",
    referral: "Referral",
    event: "Event or fair",
    walk_in: "Walk-in",
    phone: "Phone call",
    website: "Website",
    other: "Other",
  },
  channels: {
    whatsapp: "WhatsApp",
    instagram: "Instagram",
    facebook: "Facebook",
    web: "Website chat",
    email: "Email",
    telegram: "Telegram",
    sms: "SMS",
    api: "API",
  },
};
