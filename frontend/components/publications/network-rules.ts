import type {
  Channel,
  InstagramPostType,
  TikTokSettings,
} from "@/lib/api/publications";

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

/**
 * Length of ``text`` as the backend counts it for ``network``: code points
 * (Python's ``len``), and on Threads each emoji by its UTF-8 bytes
 * (``threads_length``). ``text.length`` counts UTF-16 units, which makes an
 * emoji 2 everywhere: too long for most networks, too short for Threads.
 */
export function textLength(network: string, text: string): number {
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
    const length = textLength(net, text);

    if (net === "instagram") {
      if (length > 2200) {
        problems.push(
          `${label} (Instagram): el texto supera los 2200 caracteres (${length}/2200).`,
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
      if (length > 63206) {
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
      if (length > 500) {
        problems.push(
          `${label} (Threads): el texto supera los 500 caracteres, contando cada emoji como varios (${length}/500).`,
        );
      }
      if (media.length > 20) {
        problems.push(
          `${label} (Threads): admite hasta 20 imágenes o videos.`,
        );
      }
      continue;
    }

    if (net === "tiktok") {
      const limit = channelCharLimit("tiktok", media) ?? 2200;
      if (media.length === 0) {
        problems.push(`${label} (TikTok): agregá un video o al menos una foto.`);
      } else if (videoCount > 0 && imageCount > 0) {
        problems.push(
          `${label} (TikTok): se publica un video o fotos, sin mezclarlos.`,
        );
      } else if (videoCount > 1) {
        problems.push(`${label} (TikTok): publica un solo video por vez.`);
      } else if (imageCount > 35) {
        problems.push(`${label} (TikTok): admite hasta 35 fotos.`);
      } else if (
        media.some(
          (m) =>
            m.type === "image" &&
            !["jpg", "jpeg", "webp"].includes(mediaExtension(m)),
        )
      ) {
        problems.push(`${label} (TikTok): solo acepta fotos en JPG o WebP.`);
      }
      if (length > limit) {
        problems.push(
          `${label} (TikTok): el texto supera los ${limit} caracteres (${length}/${limit}).`,
        );
      }
      const chosen = t.tiktok;
      if (!chosen?.privacy_level) {
        problems.push(`${label} (TikTok): elegí quién puede ver la publicación.`);
      }
      if (chosen?.disclose && !chosen.brand_organic && !chosen.brand_content) {
        problems.push(
          `${label} (TikTok): indicá si el contenido promociona tu marca, a un tercero o ambos.`,
        );
      }
      if (chosen?.brand_content && chosen.privacy_level === "SELF_ONLY") {
        problems.push(
          `${label} (TikTok): el contenido de marca no puede tener visibilidad «Solo yo».`,
        );
      }
      continue;
    }

    if (net === "linkedin") {
      if (!hasText && media.length === 0) {
        problems.push(
          `${label} (LinkedIn): escribí un texto o agregá al menos una imagen.`,
        );
      }
      if (length > 3000) {
        problems.push(
          `${label} (LinkedIn): el texto supera los 3000 caracteres (${length}/3000).`,
        );
      }
      if (videoCount > 0) {
        problems.push(
          `${label} (LinkedIn): los videos todavía no se pueden publicar desde AloStudio.`,
        );
      } else if (imageCount > 20) {
        problems.push(`${label} (LinkedIn): admite hasta 20 imágenes.`);
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
      if (length > limit) {
        problems.push(
          `${label} (Telegram): el texto supera los ${limit} caracteres${media.length > 0 ? " con medios" : ""} (${length}/${limit}).`,
        );
      }
      if (media.length > 10) {
        problems.push(
          `${label} (Telegram): admite hasta 10 imágenes o videos.`,
        );
      }
      continue;
    }

    // Discord and Slack: webhooks, with videos sent as links in the text.
    if (net === "discord" || net === "slack") {
      const name = net === "discord" ? "Discord" : "Slack";
      const max = WEBHOOK_TEXT_MAX[net];
      if (!hasText && media.length === 0) {
        problems.push(
          `${label} (${name}): escribí un texto o agregá al menos un medio.`,
        );
      }
      const videoLinkChars = media
        .filter((m) => m.type === "video")
        .reduce((sum, v) => sum + (v.url ? v.url.length + 1 : 0), 0);
      const effectiveLen = length + videoLinkChars;
      if (effectiveLen > max) {
        problems.push(
          `${label} (${name}): el texto${videoCount > 0 ? " más los links de video" : ""} supera los ${max} caracteres.`,
        );
      }
      if (imageCount > 10) {
        problems.push(`${label} (${name}): admite hasta 10 imágenes.`);
      }
    }
  }

  return problems;
}
