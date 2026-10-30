"use client";

import { Button } from "@/components/ui/button";

import { CopyField } from "./copy-field";

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
  return (
    <div className="space-y-3 rounded-md border border-warning bg-surface-2 p-4">
      <div>
        <p className="text-sm font-medium text-fg">
          {clientSecret ? "Guardalo ahora: no se vuelve a mostrar" : "App creada"}
        </p>
        <p className="text-xs text-fg-muted">
          {clientSecret
            ? "El secreto de la app solo se ve esta vez. Si lo perdés, regeneralo y actualizá la app."
            : "Es una app pública: no tiene secreto y tiene que usar PKCE."}
        </p>
      </div>
      <CopyField label="Client ID" value={clientId} />
      {clientSecret ? <CopyField label="Client secret" value={clientSecret} /> : null}
      <div className="flex justify-end">
        <Button size="sm" variant="ghost" onClick={onDismiss}>
          Cerrar
        </Button>
      </div>
    </div>
  );
}
