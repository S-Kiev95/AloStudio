"use client";

import { AlertTriangle } from "lucide-react";
import { useEffect } from "react";

import { FallbackPanel } from "@/components/system/fallback-panel";
import { useT } from "@/lib/i18n/provider";

export default function HelpCenterError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  const t = useT();
  useEffect(() => {
    console.error("AloStudio /hc error", error);
  }, [error]);

  return (
    <FallbackPanel
      icon={AlertTriangle}
      title={t("hc.errorTitle")}
      description={t("hc.errorBody")}
      primary={{ label: t("actions.retry"), onClick: reset }}
    />
  );
}
