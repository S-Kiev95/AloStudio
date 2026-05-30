"use client";

import { Check, Copy } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";

/**
 * One-time secret reveal — shows the freshly-minted token value with a copy
 * button. The dashboard displays this only after create/rotate; once dismissed
 * the value is unreachable.
 */
export function SecretReveal({
  token,
  onDismiss,
}: {
  token: string;
  onDismiss: () => void;
}) {
  const [copied, setCopied] = useState(false);

  async function copy() {
    try {
      await navigator.clipboard.writeText(token);
      setCopied(true);
      setTimeout(() => setCopied(false), 2_000);
    } catch {
      // clipboard.writeText can throw in non-secure contexts — ignore.
    }
  }

  return (
    <div className="space-y-3 rounded-md border border-warning/30 bg-warning/5 p-4">
      <div>
        <p className="text-sm font-medium text-fg">Guardalo ahora</p>
        <p className="text-xs text-fg-muted">
          Este token solo se muestra una vez. Si lo perdés, vas a tener que
          rotarlo para generar uno nuevo.
        </p>
      </div>
      <div className="flex items-center gap-2">
        <code className="flex-1 truncate rounded border border-border bg-surface px-3 py-2 text-sm">
          {token}
        </code>
        <Button size="sm" variant="secondary" onClick={copy}>
          {copied ? (
            <>
              <Check className="h-4 w-4" aria-hidden /> Copiado
            </>
          ) : (
            <>
              <Copy className="h-4 w-4" aria-hidden /> Copiar
            </>
          )}
        </Button>
      </div>
      <div className="flex justify-end">
        <Button size="sm" variant="ghost" onClick={onDismiss}>
          Cerrar
        </Button>
      </div>
    </div>
  );
}
