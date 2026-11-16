"use client";

import { AlertTriangle } from "lucide-react";
import { useEffect } from "react";

import { FallbackPanel } from "@/components/system/fallback-panel";
import { useT } from "@/lib/i18n/provider";

/** Dashboard-level error boundary — keeps the shell visible. */
export default function AccountError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  const t = useT();
  useEffect(() => {
    console.error("AloStudio account error", error);
  }, [error]);

  return (
    <FallbackPanel
      icon={AlertTriangle}
      title={t("errors.sectionTitle")}
      description={t("errors.sectionBody")}
      primary={{ label: t("actions.retry"), onClick: reset }}
    />
  );
}
