import { LOCALE_COOKIE, resolveLocale } from "./config";
import { createTranslate, type Translate } from "./translate";

/**
 * A `t()` for code that runs outside React — API helpers, upload
 * validation, error fallbacks — where `useT()` can't reach. The language is
 * the one in the cookie: the switcher writes it and the dashboard keeps it in
 * step with the profile. Only the cookie, not the browser's language, so
 * these texts always match the rest of the screen.
 */
export function clientT(): Translate {
  let saved: string | undefined;
  if (typeof document !== "undefined") {
    saved = document.cookie
      .split("; ")
      .find((c) => c.startsWith(`${LOCALE_COOKIE}=`))
      ?.slice(LOCALE_COOKIE.length + 1);
  }
  return createTranslate(resolveLocale(saved, null));
}
