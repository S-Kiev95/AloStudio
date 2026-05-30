"use client";

import { AlertTriangle } from "lucide-react";
import { useEffect } from "react";

import { FallbackPanel } from "@/components/system/fallback-panel";

/**
 * Root error boundary. Catches anything thrown during render that no
 * deeper ``error.tsx`` already handled. Logs to the console so the
 * stack survives in dev/staging; in production we'd hook this up to
 * Sentry/etc.
 */
export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("AloStudio uncaught error", error);
  }, [error]);

  return (
    <div className="min-h-dvh bg-bg text-fg">
      <div className="flex min-h-dvh items-center justify-center p-6">
        <FallbackPanel
          icon={AlertTriangle}
          title="Algo salió mal"
          description="Tuvimos un problema cargando esta página. Probá recargar."
          primary={{ label: "Reintentar", onClick: reset }}
          secondary={{ label: "Ir al inicio", href: "/" }}
        />
      </div>
    </div>
  );
}
