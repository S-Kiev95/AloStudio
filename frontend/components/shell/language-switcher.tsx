"use client";

import { Languages } from "lucide-react";

import { isLocale, LOCALE_NAMES, LOCALES } from "@/lib/i18n/config";
import { useLocale, useSwitchLocale, useT } from "@/lib/i18n/provider";
import { cn } from "@/lib/utils";

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
    <label
      className={cn(
        "relative inline-flex h-10 items-center gap-1.5 rounded-control px-2 text-sm text-fg-muted transition-colors",
        "hover:bg-hover-glass hover:text-fg focus-within:outline focus-within:outline-2 focus-within:outline-offset-2 focus-within:outline-neon",
        className,
      )}
    >
      <Languages className="h-4 w-4 shrink-0" aria-hidden />
      <span className="sr-only">{t("auth.language")}</span>
      <select
        value={locale}
        onChange={(e) => {
          if (isLocale(e.target.value)) switchLocale(e.target.value);
        }}
        className="cursor-pointer appearance-none bg-transparent pr-1 text-sm text-inherit focus:outline-none"
      >
        {LOCALES.map((code) => (
          <option key={code} value={code} lang={code} className="bg-surface-2 text-fg">
            {LOCALE_NAMES[code]}
          </option>
        ))}
      </select>
    </label>
  );
}
