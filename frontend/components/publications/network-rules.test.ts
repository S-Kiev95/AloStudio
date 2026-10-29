import { describe, expect, it } from "vitest";

import type { Channel } from "@/lib/api/publications";

import {
  channelCharLimit,
  minSharedCharLimit,
  textLength,
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
    ).toEqual({ limit: 500, network: "threads" });

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
    ).toEqual({ limit: 1024, network: "telegram" });

    // Telegram without media allows 4096
    expect(channelCharLimit("telegram", [])).toBe(4096);
  });

  it("cuenta el texto como el backend: emoji por sus bytes en Threads, un carácter en el resto", () => {
    // 😀 is one code point (Python's len) but two UTF-16 units and 4 UTF-8 bytes.
    expect(textLength("instagram", "hola 😀")).toBe(6);
    expect(textLength("threads", "hola 😀")).toBe(9);
    // ❤️ = U+2764 (So, 3 bytes) + U+FE0F (variation selector, 3 bytes).
    expect(textLength("threads", String.fromCodePoint(0x2764, 0xfe0f))).toBe(6);
    // Accented letters are one character each, also on Threads.
    expect(
      textLength("threads", `${String.fromCodePoint(0xf1)}and${String.fromCodePoint(0xfa)}`),
    ).toBe(5);

    const th = ch(1, "threads", "TH");
    // 200 emoji pass as 400 UTF-16 units, but Threads counts 800.
    expect(
      validatePublicationTargets("😀".repeat(200), [], [
        { channel: th, postType: "feed", customContent: null },
      ])[0],
    ).toMatch(/Threads.*500 caracteres.*\(800\/500\)/);

    // A text of 2200 emoji still fits Instagram: one character each.
    const ig = ch(2, "instagram", "IG");
    expect(
      validatePublicationTargets(
        "😀".repeat(2200),
        [{ type: "image", url: "https://s3/1.jpg" }],
        [{ channel: ig, postType: "feed", customContent: null }],
      ),
    ).toEqual([]);
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
