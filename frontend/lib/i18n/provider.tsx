"use client";

import { useRouter } from "next/navigation";
import { createContext, type ReactNode, useCallback, useContext, useMemo } from "react";

import {
  DEFAULT_LOCALE,
  INTL_TAGS,
  LOCALE_COOKIE,
  type Locale,
} from "./config";
import { createTranslate, type Translate } from "./translate";

type I18nValue = { locale: Locale; t: Translate };

const I18nContext = createContext<I18nValue>({
  locale: DEFAULT_LOCALE,
  t: createTranslate(DEFAULT_LOCALE),
});

export function I18nProvider({
  locale,
  children,
}: {
  locale: Locale;
  children: ReactNode;
}) {
  const value = useMemo(
    () => ({ locale, t: createTranslate(locale) }),
    [locale],
  );
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

/** `t("nav.home")`. Outside the provider (tests) it answers in Spanish. */
export function useT(): Translate {
  return useContext(I18nContext).t;
}

export function useLocale(): Locale {
  return useContext(I18nContext).locale;
}

/** The `Intl` tag for the current language, e.g. `"es-UY"`. */
export function useIntlTag(): string {
  return INTL_TAGS[useLocale()];
}

export function writeLocaleCookie(locale: Locale): void {
  // A year; the profile is the lasting copy, this is for the first render.
  document.cookie = `${LOCALE_COOKIE}=${locale}; path=/; max-age=31536000; samesite=lax`;
}

/**
 * Switch the interface language: writes the cookie and re-renders, server
 * components included. Saving it in the profile is the caller's job, so
 * this also works signed out (the login page).
 */
export function useSwitchLocale(): (locale: Locale) => void {
  const router = useRouter();
  return useCallback(
    (locale: Locale) => {
      writeLocaleCookie(locale);
      router.refresh();
    },
    [router],
  );
}
