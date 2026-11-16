/**
 * What each way of connecting an Instagram account actually gets you.
 *
 * This exists because none of it was visible before connecting. The
 * differences are not cosmetic — one flow delivers DMs with their text
 * and the other delivers empty events, one can delete a post and the
 * other cannot — and every one of these was learned by connecting an
 * account and watching something fail silently days later.
 *
 * Every entry below was verified live against Meta on 2026-08-22, on a
 * real account, not read off a table.
 */

import type { MessageKey } from "@/lib/i18n/translate";

export type CapabilityLevel = "yes" | "partial" | "no";

export type Capability = {
  label: MessageKey;
  level: CapabilityLevel;
  /** Shown when the answer is not a plain yes. */
  note?: MessageKey;
};

export type ConnectFlow = {
  id: "facebook" | "instagram";
  title: string;
  /** One line on who this flow is for. */
  summary: MessageKey;
  requirement: MessageKey;
  capabilities: Capability[];
};

const PUBLISH: Capability = {
  label: "igCapabilities.publish",
  level: "yes",
};
const COMMENTS: Capability = {
  label: "igCapabilities.comments",
  level: "yes",
};
const INSIGHTS: Capability = { label: "igCapabilities.insights", level: "yes" };

export const CONNECT_FLOWS: ConnectFlow[] = [
  {
    id: "facebook",
    title: "Facebook Login", // i18n-ignore
    summary:
      "igCapabilities.facebook.summary",
    requirement:
      "igCapabilities.facebook.requirement",
    capabilities: [
      PUBLISH,
      COMMENTS,
      INSIGHTS,
      {
        label: "igCapabilities.dms",
        level: "yes",
        note: "igCapabilities.facebook.dmsNote",
      },
      {
        label: "igCapabilities.deletePosts",
        level: "yes",
      },
    ],
  },
  {
    id: "instagram",
    title: "Instagram Login", // i18n-ignore
    summary:
      "igCapabilities.instagram.summary",
    requirement: "igCapabilities.instagram.requirement",
    capabilities: [
      PUBLISH,
      COMMENTS,
      INSIGHTS,
      {
        label: "igCapabilities.dms",
        level: "partial",
        note: "igCapabilities.instagram.dmsNote",
      },
      {
        label: "igCapabilities.deletePosts",
        level: "no",
        note: "igCapabilities.instagram.deleteNote",
      },
    ],
  },
];

export function flowById(id: ConnectFlow["id"]): ConnectFlow {
  const found = CONNECT_FLOWS.find((f) => f.id === id);
  if (!found) throw new Error(`flujo desconocido: ${id}`);
  return found;
}
