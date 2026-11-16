import type {
  Channel,
  InstagramPostType,
  TikTokSettings,
} from "@/lib/api/publications";
import { createTranslate, type Translate } from "@/lib/i18n/translate";

export type MediaCandidate = {
  type: "image" | "video";
  url: string;
  filename?: string | null;
};

export type TargetRuleInput = {
  channel: Channel;
  postType: InstagramPostType;
  customContent: string | null;
  tiktok?: TikTokSettings;
};

/** File extension of a media item: of its name, or of the object key our
 * signed links carry (``?key=``), or of the link's path. */
function mediaExtension(m: MediaCandidate): string {
  let name = m.filename ?? "";
  if (!name) {
    try {
      const parsed = new URL(m.url, "https://local.invalid");
      name = parsed.searchParams.get("key") ?? parsed.pathname;
    } catch {
      name = m.url;
    }
  }
  const tail = name.split("/").pop() ?? "";
  return tail.includes(".") ? (tail.split(".").pop() ?? "").toLowerCase() : "";
}

function channelDisplayLabel(channel: Channel): string {
  const base =
    channel.name?.trim() ||
    (channel.username ? `@${channel.username}` : null) ||
    channel.network;
  return base;
}

const utf8 = new TextEncoder();

// The Threads adapter's test for an emoji: a character outside the BMP, a
// symbol (So), a format character (Cf, like the zero-width joiner) or the
// emoji variation selector.
function isThreadsEmoji(char: string): boolean {
  return (
    (char.codePointAt(0) ?? 0) > 0xffff ||
    /^[\p{So}\p{Cf}]$/u.test(char) ||
    char === "️"
  );
}

const X_LINK = /(?:https?:\/\/|www\.)\S+/gi;
const X_LINK_LENGTH = 23;

/** The X adapter's ``x_length``: each link is 23 characters, and characters
 * outside X's light ranges (emoji, CJK…) count double. */
function xLength(text: string): number {
  const links = text.match(X_LINK) ?? [];
  let total = links.length * X_LINK_LENGTH;
  for (const char of text.replace(X_LINK, "")) {
    const code = char.codePointAt(0) ?? 0;
    const light =
      code <= 4351 ||
      (code >= 8192 && code <= 8205) ||
      (code >= 8208 && code <= 8223) ||
      (code >= 8242 && code <= 8247);
    total += light ? 1 : 2;
  }
  return total;
}

/** The chosen X channels whose text has a link: X charges much more for
 * those posts. Worth a notice, not a problem: the post can still go out. */
export function xChannelsWithLink(
  sharedContent: string,
  targets: TargetRuleInput[],
): string[] {
  return targets
    .filter((t) => t.channel.network === "x")
    .filter((t) => (t.customContent ?? sharedContent).match(X_LINK))
    .map((t) => channelDisplayLabel(t.channel));
}

/**
 * Length of ``text`` as the backend counts it for ``network``: code points
 * (Python's ``len``), and on Threads each emoji by its UTF-8 bytes
 * (``threads_length``). ``text.length`` counts UTF-16 units, which makes an
 * emoji 2 everywhere: too long for most networks, too short for Threads.
 */
export function textLength(network: string, text: string): number {
  if (network === "x") return xLength(text);
  if (network !== "threads") return Array.from(text).length;
  let total = 0;
  for (const char of text) {
    total += isThreadsEmoji(char) ? utf8.encode(char).length : 1;
  }
  return total;
}

/** Text limit of the networks that publish through a webhook (Slack: a
 *  section block's text). */
const WEBHOOK_TEXT_MAX: Record<string, number> = { discord: 2000, slack: 3000 };

/**
 * Character limit for ``network`` given current media selection, or ``null``
 * when the network has no known client-side limit.
 */
export function channelCharLimit(
  network: string,
  media: MediaCandidate[],
): number | null {
  switch (network) {
    case "instagram":
      return 2200;
    case "facebook_page":
      return 63206;
    case "threads":
      return 500;
    case "x":
      return 280;
    case "linkedin":
      return 3000;
    case "tiktok":
      return media.length > 0 && media.every((m) => m.type === "image")
        ? 4000
        : 2200;
    case "telegram":
      return media.length > 0 ? 1024 : 4096;
    case "discord":
    case "slack": {
      const videoLinkChars = media
        .filter((m) => m.type === "video")
        .reduce((sum, v) => sum + (v.url ? v.url.length + 1 : 0), 0);
      return Math.max(0, WEBHOOK_TEXT_MAX[network] - videoLinkChars);
    }
    default:
      return null;
  }
}

/**
 * Smallest character limit across the chosen channels that use the shared
 * text, with the network it comes from (its count is the one to show: see
 * ``textLength``).
 */
export function minSharedCharLimit(
  targets: TargetRuleInput[],
  media: MediaCandidate[],
): { limit: number; network: string } | null {
  let min: { limit: number; network: string } | null = null;
  for (const t of targets) {
    if (t.customContent !== null) continue;
    const limit = channelCharLimit(t.channel.network, media);
    if (limit !== null && (min === null || limit < min.limit)) {
      min = { limit, network: t.channel.network };
    }
  }
  // If every chosen channel has custom text, fall back to the min across all chosen channels.
  if (min === null) {
    for (const t of targets) {
      const limit = channelCharLimit(t.channel.network, media);
      if (limit !== null && (min === null || limit < min.limit)) {
        min = { limit, network: t.channel.network };
      }
    }
  }
  return min;
}

/**
 * Validate a publication's targets, text, and media against the per-network
 * rules table before sending to the backend.
 */
export function validatePublicationTargets(
  sharedContent: string,
  media: MediaCandidate[],
  targets: TargetRuleInput[],
  tr: Translate = createTranslate("es"),
): string[] {
  const problems: string[] = [];

  if (targets.length === 0) {
    problems.push(tr("publications.rules.pickChannel"));
    return problems;
  }

  const imageCount = media.filter((m) => m.type === "image").length;
  const videoCount = media.filter((m) => m.type === "video").length;

  for (const t of targets) {
    const label = channelDisplayLabel(t.channel);
    const text = t.customContent !== null ? t.customContent : sharedContent;
    const hasText = text.trim().length > 0;
    const net = t.channel.network;
    const length = textLength(net, text);

    if (net === "instagram") {
      if (length > 2200) {
        problems.push(
          tr("publications.rules.textTooLong", { label, net: "Instagram", limit: 2200, length }),
        );
      }
      if (t.postType === "feed") {
        if (media.length < 1 || media.length > 10) {
          problems.push(
            tr("publications.rules.igFeed", { label }),
          );
        }
      } else if (t.postType === "reels") {
        if (media.length !== 1 || media[0].type !== "video") {
          problems.push(
            tr("publications.rules.igReels", { label }),
          );
        }
      } else if (t.postType === "story") {
        if (media.length !== 1) {
          problems.push(
            tr("publications.rules.igStory", { label }),
          );
        }
      }
      continue;
    }

    if (net === "facebook_page") {
      if (!hasText && media.length === 0) {
        problems.push(
          tr("publications.rules.needTextOrMedia", { label, net: "Facebook" }),
        );
      }
      if (length > 63206) {
        problems.push(
          tr("publications.rules.textTooLongPlain", { label, net: "Facebook", limit: 63206 }),
        );
      }
      if (media.length > 0) {
        const validImagesOnly = videoCount === 0 && imageCount <= 10;
        const validSingleVideo = media.length === 1 && videoCount === 1;
        if (!validImagesOnly && !validSingleVideo) {
          problems.push(
            tr("publications.rules.fbMedia", { label }),
          );
        }
      }
      continue;
    }

    if (net === "x") {
      if (!hasText && media.length === 0) {
        problems.push(
          tr("publications.rules.needTextOrMedia", { label, net: "X" }),
        );
      }
      if (length > 280) {
        problems.push(
          tr("publications.rules.xTextTooLong", { label, length }),
        );
      }
      if (videoCount > 0 && media.length > 1) {
        problems.push(
          tr("publications.rules.oneVideoOnly", { label, net: "X" }),
        );
      } else if (media.length > 4) {
        problems.push(tr("publications.rules.maxImages", { label, net: "X", max: 4 }));
      }
      continue;
    }

    if (net === "threads") {
      if (!hasText && media.length === 0) {
        problems.push(
          tr("publications.rules.needTextOrMedia", { label, net: "Threads" }),
        );
      }
      if (length > 500) {
        problems.push(
          tr("publications.rules.threadsTextTooLong", { label, length }),
        );
      }
      if (media.length > 20) {
        problems.push(
          tr("publications.rules.maxMedia", { label, net: "Threads", max: 20 }),
        );
      }
      continue;
    }

    if (net === "tiktok") {
      const limit = channelCharLimit("tiktok", media) ?? 2200;
      if (media.length === 0) {
        problems.push(tr("publications.rules.tiktokNeedMedia", { label }));
      } else if (videoCount > 0 && imageCount > 0) {
        problems.push(
          tr("publications.rules.tiktokNoMix", { label }),
        );
      } else if (videoCount > 1) {
        problems.push(tr("publications.rules.tiktokOneVideo", { label }));
      } else if (imageCount > 35) {
        problems.push(tr("publications.rules.tiktokMaxPhotos", { label, max: 35 }));
      } else if (
        media.some(
          (m) =>
            m.type === "image" &&
            !["jpg", "jpeg", "webp"].includes(mediaExtension(m)),
        )
      ) {
        problems.push(tr("publications.rules.tiktokPhotoFormat", { label }));
      }
      if (length > limit) {
        problems.push(
          tr("publications.rules.textTooLong", { label, net: "TikTok", limit, length }),
        );
      }
      const chosen = t.tiktok;
      if (!chosen?.privacy_level) {
        problems.push(tr("publications.rules.tiktokPickPrivacy", { label }));
      }
      if (chosen?.disclose && !chosen.brand_organic && !chosen.brand_content) {
        problems.push(
          tr("publications.rules.tiktokDisclosure", { label }),
        );
      }
      if (chosen?.brand_content && chosen.privacy_level === "SELF_ONLY") {
        problems.push(
          tr("publications.rules.tiktokBrandSelfOnly", { label }),
        );
      }
      continue;
    }

    if (net === "linkedin") {
      if (!hasText && media.length === 0) {
        problems.push(
          tr("publications.rules.linkedinNeedTextOrMedia", { label }),
        );
      }
      if (length > 3000) {
        problems.push(
          tr("publications.rules.textTooLong", { label, net: "LinkedIn", limit: 3000, length }),
        );
      }
      if (videoCount > 0 && media.length > 1) {
        problems.push(
          tr("publications.rules.oneVideoOnly", { label, net: "LinkedIn" }),
        );
      } else if (imageCount > 20) {
        problems.push(tr("publications.rules.maxImages", { label, net: "LinkedIn", max: 20 }));
      }
      continue;
    }

    if (net === "telegram") {
      if (!hasText && media.length === 0) {
        problems.push(
          tr("publications.rules.needTextOrMedia", { label, net: "Telegram" }),
        );
      }
      const limit = media.length > 0 ? 1024 : 4096;
      if (length > limit) {
        problems.push(
          media.length > 0
            ? tr("publications.rules.telegramTextTooLongWithMedia", { label, limit, length })
            : tr("publications.rules.textTooLong", { label, net: "Telegram", limit, length }),
        );
      }
      if (media.length > 10) {
        problems.push(
          tr("publications.rules.maxMedia", { label, net: "Telegram", max: 10 }),
        );
      }
      continue;
    }

    // Discord and Slack: webhooks, with videos sent as links in the text.
    if (net === "discord" || net === "slack") {
      const name = net === "discord" ? "Discord" : "Slack"; // i18n-ignore
      const max = WEBHOOK_TEXT_MAX[net];
      if (!hasText && media.length === 0) {
        problems.push(
          tr("publications.rules.needTextOrMedia", { label, net: name }),
        );
      }
      const videoLinkChars = media
        .filter((m) => m.type === "video")
        .reduce((sum, v) => sum + (v.url ? v.url.length + 1 : 0), 0);
      const effectiveLen = length + videoLinkChars;
      if (effectiveLen > max) {
        problems.push(
          videoCount > 0
            ? tr("publications.rules.textWithVideoLinksTooLong", { label, net: name, limit: max })
            : tr("publications.rules.textTooLongPlain", { label, net: name, limit: max }),
        );
      }
      if (imageCount > 10) {
        problems.push(tr("publications.rules.maxImages", { label, net: name, max: 10 }));
      }
    }
  }

  return problems;
}
