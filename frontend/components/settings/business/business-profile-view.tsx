"use client";

import { Building2 } from "lucide-react";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useBusinessProfile, useSaveBusinessProfile } from "@/lib/api/business-profile";
import { useIsAccountAdmin } from "@/lib/api/profile";
import { useT } from "@/lib/i18n/provider";

/**
 * Ajustes → Sobre el negocio: the business described once, for every AI of
 * the account (the voice agent that answers calls, the decisions model, the
 * chat agent). Administrators write it; everybody can read it.
 */
export function BusinessProfileView({ accountId }: { accountId: string }) {
  const t = useT();
  const isAdmin = useIsAccountAdmin(accountId);
  const profile = useBusinessProfile(accountId);
  const save = useSaveBusinessProfile(accountId);
  const [text, setText] = useState("");
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (profile.data) setText(profile.data.text);
  }, [profile.data]);

  const max = profile.data?.max ?? 8000;

  async function submit() {
    setSaved(false);
    try {
      await save.mutateAsync(text);
      setSaved(true);
    } catch {
      // shown below from save.error
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <Building2 className="h-4 w-4 text-fg-muted" aria-hidden />
          {t("businessProfile.title")}
        </CardTitle>
        <p className="mt-1 max-w-3xl text-sm text-fg-muted">{t("businessProfile.intro")}</p>
      </CardHeader>
      <CardContent className="space-y-3">
        {profile.isLoading ? (
          <p className="text-sm text-fg-muted">{t("businessProfile.loading")}</p>
        ) : profile.error ? (
          <p role="alert" className="text-sm text-danger">
            {t("businessProfile.loadFailed")}
          </p>
        ) : (
          <>
            <div className="space-y-1.5">
              <Label htmlFor="business-profile">{t("businessProfile.label")}</Label>
              <Textarea
                id="business-profile"
                rows={12}
                value={text}
                maxLength={max}
                readOnly={!isAdmin}
                placeholder={t("businessProfile.placeholder")}
                onChange={(e) => {
                  setSaved(false);
                  setText(e.target.value);
                }}
              />
              <p className="text-xs text-fg-muted">
                {isAdmin ? t("businessProfile.hint") : t("businessProfile.readOnly")}
              </p>
            </div>
            {isAdmin ? (
              <div className="flex flex-wrap items-center gap-3">
                <Button size="sm" onClick={() => void submit()} loading={save.isPending}>
                  {t("businessProfile.save")}
                </Button>
                {saved ? (
                  <span role="status" className="text-sm text-success">
                    {t("businessProfile.saved")}
                  </span>
                ) : null}
                {save.error ? (
                  <span role="alert" className="text-sm text-danger">
                    {t("businessProfile.saveFailed")}
                  </span>
                ) : null}
              </div>
            ) : null}
          </>
        )}
      </CardContent>
    </Card>
  );
}
