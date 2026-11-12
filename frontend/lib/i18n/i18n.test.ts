import { describe, expect, it } from "vitest";

import { relativeTime } from "@/lib/time";

import { LOCALES, resolveLocale } from "./config";
import { es } from "./messages/es";
import { createTranslate, MESSAGES, type MessageKey } from "./translate";

function keys(obj: object, prefix = ""): string[] {
  return Object.entries(obj).flatMap(([k, v]) =>
    typeof v === "string" ? [`${prefix}${k}`] : keys(v, `${prefix}${k}.`),
  );
}

const SOURCE_KEYS = keys(es) as MessageKey[];
const placeholders = (s: string) => (s.match(/\{\w+\}/g) ?? []).sort().join();

describe("resolveLocale", () => {
  it("prefers the saved choice", () => {
    expect(resolveLocale("pt", "en-US,en;q=0.9")).toBe("pt");
  });

  it("falls back to the first supported browser language", () => {
    expect(resolveLocale(undefined, "it-IT,pt-BR;q=0.8,en;q=0.5")).toBe("pt");
    expect(resolveLocale("xx", "ja-JP")).toBe("ja");
  });

  it("ends in Spanish", () => {
    expect(resolveLocale(null, "it,ru")).toBe("es");
    expect(resolveLocale(null, null)).toBe("es");
  });
});

describe("createTranslate", () => {
  it("translates and fills in values", () => {
    expect(createTranslate("en")("nav.home")).toBe("Home");
    expect(
      createTranslate("es")("notifications.titleUnread", { count: 3 }),
    ).toBe("Notificaciones (3 sin leer)");
  });

  it("shows the key for something that doesn't exist", () => {
    expect(createTranslate("pt")("nope.missing" as MessageKey)).toBe(
      "nope.missing",
    );
  });

  it("leaves a placeholder without a value as is", () => {
    expect(createTranslate("en")("theme.label")).toBe("Theme: {name}");
  });
});

describe("dictionaries", () => {
  // The type check already enforces this; the test catches an `as` slipped in.
  it("have the same keys in every language", () => {
    const base = [...SOURCE_KEYS].sort();
    for (const locale of LOCALES) {
      expect(keys(MESSAGES[locale]).sort(), locale).toEqual(base);
    }
  });

  it("have every text filled in", () => {
    for (const locale of LOCALES) {
      const t = createTranslate(locale);
      for (const key of SOURCE_KEYS) {
        expect(t(key).trim(), `${locale} ${key}`).not.toBe("");
      }
    }
  });

  it("keep the same placeholders as Spanish", () => {
    const source = createTranslate("es");
    for (const locale of LOCALES) {
      const t = createTranslate(locale);
      for (const key of SOURCE_KEYS) {
        expect(placeholders(t(key)), `${locale} ${key}`).toBe(
          placeholders(source(key)),
        );
      }
    }
  });
});

describe("relativeTime", () => {
  it("speaks the given language", () => {
    const fiveMinAgo = Math.floor(Date.now() / 1000) - 300;
    expect(relativeTime(fiveMinAgo)).toBe("hace 5m");
    expect(relativeTime(fiveMinAgo, "en")).toBe("5m ago");
    expect(relativeTime(fiveMinAgo, "pt")).toBe("há 5 min");
  });
});
