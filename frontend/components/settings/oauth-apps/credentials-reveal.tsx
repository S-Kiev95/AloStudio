"use client";

import { Button } from "@/components/ui/button";

import { CopyField } from "./copy-field";
import { useT } from "@/lib/i18n/provider";

/**
 * The app's credentials right after creating it or regenerating its secret.
 * The secret is not stored by AloStudio: once this is closed it is gone.
 */
export function CredentialsReveal({
  clientId,
  clientSecret,
  onDismiss,
}: {
  clientId: string;
  clientSecret?: string;
  onDismiss: () => void;
}) {
  const t = useT();
  return (
    <div className="space-y-3 rounded-md border border-warning bg-surface-2 p-4">
      <div>
        <p className="text-sm font-medium text-fg">
          {clientSecret ? t("settingsOauth.saveNow") : t("settingsOauth.created")}
        </p>
        <p className="text-xs text-fg-muted">
          {clientSecret
            ? t("settingsOauth.secretOnce")
            : t("settingsOauth.publicNoSecret")}
        </p>
      </div>
      {/* i18n-ignore-start: OAuth field names */}
      <CopyField label="Client ID" value={clientId} />
      {clientSecret ? <CopyField label="Client secret" value={clientSecret} /> : null}
      {/* i18n-ignore-end */}
      <div className="flex justify-end">
        <Button size="sm" variant="ghost" onClick={onDismiss}>
          {t("actions.close")}
        </Button>
      </div>
    </div>
  );
}
