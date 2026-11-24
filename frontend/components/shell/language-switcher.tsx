"use client";

import { Languages } from "lucide-react";

import { Listbox, type ListboxOption } from "@/components/ui/listbox";
import { LOCALE_NAMES, LOCALES, type Locale } from "@/lib/i18n/config";
import { useLocale, useSwitchLocale, useT } from "@/lib/i18n/provider";

const LOCALE_OPTIONS: readonly ListboxOption<Locale>[] = LOCALES.map(
  (code) => ({
    value: code,
    label: LOCALE_NAMES[code],
    lang: code,
  }),
);

/**
 * Compact language picker for the signed-out screens (login, password
 * reset). Signed in, the choice lives in Ajustes → Mi perfil and is saved
 * to the profile; here it only sets the cookie.
 */
export function LanguageSwitcher({ className }: { className?: string }) {
  const t = useT();
  const locale = useLocale();
  const switchLocale = useSwitchLocale();

  return (
    <Listbox
      value={locale}
      onChange={switchLocale}
      options={LOCALE_OPTIONS}
      variant="compact"
      align="end"
      aria-label={t("auth.language")}
      leadingIcon={<Languages className="h-4 w-4 shrink-0" aria-hidden />}
      className={className}
    />
  );
}
