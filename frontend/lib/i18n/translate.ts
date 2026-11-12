import { DEFAULT_LOCALE, type Locale } from "./config";
import { en } from "./messages/en";
import { es, type Messages } from "./messages/es";
import { pt } from "./messages/pt";

export const MESSAGES: Record<Locale, Messages> = { es, en, pt };

/** Every dotted path to a text: `"nav.home"`, `"auth.login.title"`… */
type Paths<T> = {
  [K in keyof T & string]: T[K] extends string ? K : `${K}.${Paths<T[K]>}`;
}[keyof T & string];

export type MessageKey = Paths<Messages>;
export type Vars = Record<string, string | number>;
export type Translate = (key: MessageKey, vars?: Vars) => string;

function lookup(messages: Messages, key: string): string | undefined {
  let node: unknown = messages;
  for (const part of key.split(".")) {
    if (node === null || typeof node !== "object") return undefined;
    node = (node as Record<string, unknown>)[part];
  }
  return typeof node === "string" ? node : undefined;
}

/**
 * A `t()` for one language. `{name}` in a text is replaced by `vars.name`.
 * A key missing from a translation falls back to Spanish, then to the key
 * itself, so a gap shows up on screen instead of breaking the page.
 */
export function createTranslate(locale: Locale): Translate {
  const messages = MESSAGES[locale];
  return (key, vars) => {
    const text =
      lookup(messages, key) ?? lookup(MESSAGES[DEFAULT_LOCALE], key) ?? key;
    if (!vars) return text;
    return text.replace(/\{(\w+)\}/g, (match, name: string) =>
      name in vars ? String(vars[name]) : match,
    );
  };
}
