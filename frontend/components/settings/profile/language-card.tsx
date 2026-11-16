"use client";

import { useState } from "react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { useProfile, useUpdateProfile } from "@/lib/api/profile";
import { isLocale, LOCALE_NAMES, LOCALES } from "@/lib/i18n/config";
import { useLocale, useSwitchLocale, useT } from "@/lib/i18n/provider";

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
          <Label htmlFor="p-locale">{t("profile.language.label")}</Label>
          <Select
            id="p-locale"
            value={locale}
            onChange={(e) => onChange(e.target.value)}
            disabled={update.isPending}
            className="sm:max-w-xs"
          >
            {LOCALES.map((code) => (
              <option key={code} value={code} lang={code}>
                {LOCALE_NAMES[code]}
              </option>
            ))}
          </Select>
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
