"use client";

import { useState } from "react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Listbox, type ListboxOption } from "@/components/ui/listbox";
import { useProfile, useUpdateProfile } from "@/lib/api/profile";
import {
  isLocale,
  LOCALE_NAMES,
  LOCALES,
  type Locale,
} from "@/lib/i18n/config";
import { useLocale, useSwitchLocale, useT } from "@/lib/i18n/provider";

const LOCALE_OPTIONS: readonly ListboxOption<Locale>[] = LOCALES.map(
  (code) => ({
    value: code,
    label: LOCALE_NAMES[code],
    lang: code,
  }),
);

/**
 * Interface language (F13). Switches right away (cookie + re-render) and is
 * kept in the profile's `ui_settings.locale`, so it follows the user to
 * other devices: the dashboard re-applies it after signing in.
 */
export function LanguageCard() {
  const t = useT();
  const locale = useLocale();
  const switchLocale = useSwitchLocale();
  const profile = useProfile();
  const update = useUpdateProfile();
  const [error, setError] = useState(false);

  async function onChange(value: string) {
    if (!isLocale(value) || value === locale) return;
    setError(false);
    switchLocale(value);
    try {
      // The backend replaces ui_settings whole: keep what else is there.
      await update.mutateAsync({
        ui_settings: { ...(profile.data?.ui_settings ?? {}), locale: value },
      });
    } catch {
      setError(true);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("profile.language.title")}</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-1.5">
          <Label id="p-locale-label" htmlFor="p-locale">
            {t("profile.language.label")}
          </Label>
          <Listbox
            id="p-locale"
            value={locale}
            onChange={(next) => void onChange(next)}
            options={LOCALE_OPTIONS}
            disabled={update.isPending}
            aria-labelledby="p-locale-label"
            className="sm:max-w-xs"
          />
          <p className="text-xs text-fg-muted">
            {t("profile.language.description")}
          </p>
          {error ? (
            <p role="alert" className="text-sm text-danger">
              {t("profile.language.saveFailed")}
            </p>
          ) : null}
        </div>
      </CardContent>
    </Card>
  );
}
