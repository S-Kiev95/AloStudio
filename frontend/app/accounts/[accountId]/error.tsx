"use client";

import { AlertTriangle } from "lucide-react";
import { useEffect } from "react";

import { FallbackPanel } from "@/components/system/fallback-panel";

/** Dashboard-level error boundary — keeps the shell visible. */
export default function AccountError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("AloStudio account error", error);
  }, [error]);

  return (
    <FallbackPanel
      icon={AlertTriangle}
      title="No pudimos cargar esta sección"
      description="Algo falló al traer los datos. Probá de nuevo en un momento."
      primary={{ label: "Reintentar", onClick: reset }}
    />
  );
}
