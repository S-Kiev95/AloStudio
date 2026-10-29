import type { Channel, InstagramPostType } from "@/lib/api/publications";

export type MediaCandidate = {
  type: "image" | "video";
  url: string;
};

export type TargetRuleInput = {
  channel: Channel;
  postType: InstagramPostType;
  customContent: string | null;
};

function channelDisplayLabel(channel: Channel): string {
  const base =
    channel.name?.trim() ||
    (channel.username ? `@${channel.username}` : null) ||
    channel.network;
  return base;
}

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
    case "telegram":
      return media.length > 0 ? 1024 : 4096;
    case "discord": {
      const videoLinkChars = media
        .filter((m) => m.type === "video")
        .reduce((sum, v) => sum + (v.url ? v.url.length + 1 : 0), 0);
      return Math.max(0, 2000 - videoLinkChars);
    }
    default:
      return null;
  }
}

/** Smallest character limit across the chosen channels that use the shared text. */
export function minSharedCharLimit(
  targets: TargetRuleInput[],
  media: MediaCandidate[],
): number | null {
  let min: number | null = null;
  for (const t of targets) {
    if (t.customContent !== null) continue;
    const limit = channelCharLimit(t.channel.network, media);
    if (limit !== null && (min === null || limit < min)) {
      min = limit;
    }
  }
  // If every chosen channel has custom text, fall back to the min across all chosen channels.
  if (min === null) {
    for (const t of targets) {
      const limit = channelCharLimit(t.channel.network, media);
      if (limit !== null && (min === null || limit < min)) {
        min = limit;
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
): string[] {
  const problems: string[] = [];

  if (targets.length === 0) {
    problems.push("Elegí al menos un canal para la publicación.");
    return problems;
  }

  const imageCount = media.filter((m) => m.type === "image").length;
  const videoCount = media.filter((m) => m.type === "video").length;

  for (const t of targets) {
    const label = channelDisplayLabel(t.channel);
    const text = t.customContent !== null ? t.customContent : sharedContent;
    const hasText = text.trim().length > 0;
    const net = t.channel.network;

    if (net === "instagram") {
      if (text.length > 2200) {
        problems.push(
          `${label} (Instagram): el texto supera los 2200 caracteres (${text.length}/2200).`,
        );
      }
      if (t.postType === "feed") {
        if (media.length < 1 || media.length > 10) {
          problems.push(
            `${label} (Instagram Feed): requiere entre 1 y 10 imágenes o videos.`,
          );
        }
      } else if (t.postType === "reels") {
        if (media.length !== 1 || media[0].type !== "video") {
          problems.push(
            `${label} (Instagram Reels): requiere exactamente 1 video.`,
          );
        }
      } else if (t.postType === "story") {
        if (media.length !== 1) {
          problems.push(
            `${label} (Instagram Story): requiere exactamente 1 imagen o video.`,
          );
        }
      }
      continue;
    }

    if (net === "facebook_page") {
      if (!hasText && media.length === 0) {
        problems.push(
          `${label} (Facebook): escribí un texto o agregá al menos un medio.`,
        );
      }
      if (text.length > 63206) {
        problems.push(
          `${label} (Facebook): el texto supera los 63206 caracteres.`,
        );
      }
      if (media.length > 0) {
        const validImagesOnly = videoCount === 0 && imageCount <= 10;
        const validSingleVideo = media.length === 1 && videoCount === 1;
        if (!validImagesOnly && !validSingleVideo) {
          problems.push(
            `${label} (Facebook): admite hasta 10 imágenes o 1 video solo (sin mezclar).`,
          );
        }
      }
      continue;
    }

    if (net === "threads") {
      if (!hasText && media.length === 0) {
        problems.push(
          `${label} (Threads): escribí un texto o agregá al menos un medio.`,
        );
      }
      if (text.length > 500) {
        problems.push(
          `${label} (Threads): el texto supera los 500 caracteres (${text.length}/500).`,
        );
      }
      if (media.length > 20) {
        problems.push(
          `${label} (Threads): admite hasta 20 imágenes o videos.`,
        );
      }
      continue;
    }

    if (net === "telegram") {
      if (!hasText && media.length === 0) {
        problems.push(
          `${label} (Telegram): escribí un texto o agregá al menos un medio.`,
        );
      }
      const limit = media.length > 0 ? 1024 : 4096;
      if (text.length > limit) {
        problems.push(
          `${label} (Telegram): el texto supera los ${limit} caracteres${media.length > 0 ? " con medios" : ""} (${text.length}/${limit}).`,
        );
      }
      if (media.length > 10) {
        problems.push(
          `${label} (Telegram): admite hasta 10 imágenes o videos.`,
        );
      }
      continue;
    }

    if (net === "discord") {
      if (!hasText && media.length === 0) {
        problems.push(
          `${label} (Discord): escribí un texto o agregá al menos un medio.`,
        );
      }
      const videoLinkChars = media
        .filter((m) => m.type === "video")
        .reduce((sum, v) => sum + (v.url ? v.url.length + 1 : 0), 0);
      const effectiveLen = text.length + videoLinkChars;
      if (effectiveLen > 2000) {
        problems.push(
          `${label} (Discord): el texto${videoCount > 0 ? " más los links de video" : ""} supera los 2000 caracteres.`,
        );
      }
      if (imageCount > 10) {
        problems.push(`${label} (Discord): admite hasta 10 imágenes.`);
      }
    }
  }

  return problems;
}
