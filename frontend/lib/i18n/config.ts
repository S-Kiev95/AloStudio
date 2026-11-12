/**
 * Interface languages (F13). Spanish is the source: every text is written
 * in `messages/es.ts` first, and the other languages must have the same
 * keys (the type checker enforces it).
 */
export const LOCALES = ["es", "en", "pt"] as const;
export type Locale = (typeof LOCALES)[number];

export const DEFAULT_LOCALE: Locale = "es";

/** Read on the server for the first render; written when the user picks a
 *  language, and synced from their profile after signing in. */
export const LOCALE_COOKIE = "alo_locale";

/** The name of each language, in that language: it's what someone who
 *  doesn't read the current one looks for. */
export const LOCALE_NAMES: Record<Locale, string> = {
  es: "Español",
  en: "English",
  pt: "Português",
};

/** The regional variant handed to `Intl` for dates, numbers and money.
 *  Rioplatense Spanish and Brazilian Portuguese: who uses the app today. */
export const INTL_TAGS: Record<Locale, string> = {
  es: "es-UY",
  en: "en-US",
  pt: "pt-BR",
};

export function isLocale(value: unknown): value is Locale {
  return typeof value === "string" && (LOCALES as readonly string[]).includes(value);
}

/**
 * The language to use: the saved choice, else the first supported one in
 * the browser's `Accept-Language`, else Spanish.
 */
export function resolveLocale(
  saved: string | null | undefined,
  acceptLanguage: string | null | undefined,
): Locale {
  if (isLocale(saved)) return saved;
  for (const part of (acceptLanguage ?? "").split(",")) {
    const base = part.split(";")[0]?.trim().toLowerCase().split("-")[0];
    if (isLocale(base)) return base;
  }
  return DEFAULT_LOCALE;
}
