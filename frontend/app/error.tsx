"use client";

import { AlertTriangle } from "lucide-react";
import { useEffect } from "react";

import { FallbackPanel } from "@/components/system/fallback-panel";
import { useT } from "@/lib/i18n/provider";

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
  const t = useT();
  useEffect(() => {
    console.error("AloStudio uncaught error", error);
  }, [error]);

  return (
    <div className="min-h-dvh bg-bg text-fg">
      <div className="flex min-h-dvh items-center justify-center p-6">
        <FallbackPanel
          icon={AlertTriangle}
          title={t("errors.pageTitle")}
          description={t("errors.pageBody")}
          primary={{ label: t("actions.retry"), onClick: reset }}
          secondary={{ label: t("errors.goHome"), href: "/" }}
        />
      </div>
    </div>
  );
}
