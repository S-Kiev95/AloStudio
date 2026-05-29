"use client";

import { AlertTriangle } from "lucide-react";
import { useEffect } from "react";

import { FallbackPanel } from "@/components/system/fallback-panel";

export default function HelpCenterError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // eslint-disable-next-line no-console
    console.error("AloStudio /hc error", error);
  }, [error]);

  return (
    <FallbackPanel
      icon={AlertTriangle}
      title="No pudimos cargar el Help Center"
      description="Intentá recargar en un momento."
      primary={{ label: "Reintentar", onClick: reset }}
    />
  );
}
