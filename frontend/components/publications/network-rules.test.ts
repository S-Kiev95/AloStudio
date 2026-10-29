import { describe, expect, it } from "vitest";

import type { Channel } from "@/lib/api/publications";

import {
  channelCharLimit,
  minSharedCharLimit,
  validatePublicationTargets,
} from "./network-rules";

function ch(id: number, network: string, name = network): Channel {
  return {
    id,
    network,
    name,
    username: null,
    avatar_url: null,
    status: "active",
    status_message: null,
    inbox_id: null,
  };
}

describe("network-rules", () => {
  it("calcula el límite compartido más chico entre los canales sin override", () => {
    const ig = ch(1, "instagram", "IG");
    const th = ch(2, "threads", "TH");
    const tg = ch(3, "telegram", "TG");

    // Shared across IG (2200) + Threads (500) -> 500
    expect(
      minSharedCharLimit(
        [
          { channel: ig, postType: "feed", customContent: null },
          { channel: th, postType: "feed", customContent: null },
        ],
        [{ type: "image", url: "https://s3/1.jpg" }],
      ),
    ).toBe(500);

    // If Threads has a custom override, shared counter checks IG (2200) + Telegram w/ media (1024) -> 1024
    expect(
      minSharedCharLimit(
        [
          { channel: ig, postType: "feed", customContent: null },
          { channel: th, postType: "feed", customContent: "Override" },
          { channel: tg, postType: "feed", customContent: null },
        ],
        [{ type: "image", url: "https://s3/1.jpg" }],
      ),
    ).toBe(1024);

    // Telegram without media allows 4096
    expect(channelCharLimit("telegram", [])).toBe(4096);
  });

  it("valida las reglas de Facebook Page, Discord con videos y Story de Instagram", () => {
    const fb = ch(1, "facebook_page", "FB");
    const dc = ch(2, "discord", "DC");
    const ig = ch(3, "instagram", "IG");

    // Facebook rejects mixing images and video
    expect(
      validatePublicationTargets(
        "Hola",
        [
          { type: "image", url: "https://s3/a.jpg" },
          { type: "video", url: "https://s3/b.mp4" },
        ],
        [{ channel: fb, postType: "feed", customContent: null }],
      )[0],
    ).toMatch(/sin mezclar/i);

    // Discord counts video URL length against the 2000-character limit
    const videoUrl = "https://cdn.example.com/videos/demo-clip.mp4"; // 44 chars + 1
    expect(
      validatePublicationTargets(
        "a".repeat(1960),
        [{ type: "video", url: videoUrl }],
        [{ channel: dc, postType: "feed", customContent: null }],
      )[0],
    ).toMatch(/2000 caracteres/);

    // Instagram Story requires exactly 1 image or video
    expect(
      validatePublicationTargets(
        "",
        [
          { type: "image", url: "https://s3/1.jpg" },
          { type: "image", url: "https://s3/2.jpg" },
        ],
        [{ channel: ig, postType: "story", customContent: null }],
      )[0],
    ).toMatch(/Instagram Story.*exactamente 1/i);
  });
});
