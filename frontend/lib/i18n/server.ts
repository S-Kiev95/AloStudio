import "server-only";

import { cookies, headers } from "next/headers";

import { LOCALE_COOKIE, type Locale, resolveLocale } from "./config";
import { createTranslate, type Translate } from "./translate";

/** The visitor's language on the server: cookie, then the browser. */
export async function getLocale(): Promise<Locale> {
  const [jar, head] = await Promise.all([cookies(), headers()]);
  return resolveLocale(
    jar.get(LOCALE_COOKIE)?.value,
    head.get("accept-language"),
  );
}

/** `t()` for server components. */
export async function getT(): Promise<Translate> {
  return createTranslate(await getLocale());
}
