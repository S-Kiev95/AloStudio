import { describe, expect, it } from "vitest";

import { relativeTime } from "@/lib/time";

import { resolveLocale } from "./config";
import { en } from "./messages/en";
import { es } from "./messages/es";
import { pt } from "./messages/pt";
import { createTranslate, type MessageKey } from "./translate";

function keys(obj: object, prefix = ""): string[] {
  return Object.entries(obj).flatMap(([k, v]) =>
    typeof v === "string" ? [`${prefix}${k}`] : keys(v, `${prefix}${k}.`),
  );
}

describe("resolveLocale", () => {
  it("prefers the saved choice", () => {
    expect(resolveLocale("pt", "en-US,en;q=0.9")).toBe("pt");
  });

  it("falls back to the first supported browser language", () => {
    expect(resolveLocale(undefined, "fr-FR,pt-BR;q=0.8,en;q=0.5")).toBe("pt");
    expect(resolveLocale("de", "en-GB")).toBe("en");
  });

  it("ends in Spanish", () => {
    expect(resolveLocale(null, "fr,de")).toBe("es");
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
    const base = keys(es).sort();
    expect(keys(en).sort()).toEqual(base);
    expect(keys(pt).sort()).toEqual(base);
  });

  it("keep the same placeholders as Spanish", () => {
    const vars = (s: string) => (s.match(/\{\w+\}/g) ?? []).sort().join();
    const t = { es: createTranslate("es"), en: createTranslate("en"), pt: createTranslate("pt") };
    for (const key of keys(es) as MessageKey[]) {
      expect(vars(t.en(key)), key).toBe(vars(t.es(key)));
      expect(vars(t.pt(key)), key).toBe(vars(t.es(key)));
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
