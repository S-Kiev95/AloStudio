"use client";

import { AlertCircle, RefreshCw } from "lucide-react";

import { Button } from "@/components/ui/button";
import { useT } from "@/lib/i18n/provider";
import { cn } from "@/lib/utils";

/**
 * Shared error surface with a Reintentar action. Keeps failed data states
 * honest instead of rendering fake zeros or misleading empty states.
 */
export function ErrorState({
  message,
  onRetry,
  retrying = false,
  compact = false,
  className,
}: {
  message: string;
  onRetry?: () => void;
  retrying?: boolean;
  compact?: boolean;
  className?: string;
}) {
  const t = useT();

  return (
    <div
      role="alert"
      className={cn(
        "flex flex-col items-center justify-center rounded-md border border-danger/35 bg-surface text-center",
        compact ? "gap-2.5 px-3 py-4" : "gap-3 px-5 py-8",
        className,
      )}
    >
      <div className="flex items-center justify-center gap-2 text-danger">
        <AlertCircle className={cn("shrink-0", compact ? "h-4 w-4" : "h-5 w-5")} aria-hidden />
        <p className={cn("text-pretty", compact ? "text-xs" : "text-sm")}>{message}</p>
      </div>
      {onRetry ? (
        <Button
          type="button"
          variant="secondary"
          size="sm"
          loading={retrying}
          onClick={onRetry}
        >
          <RefreshCw className="h-3.5 w-3.5" aria-hidden />
          {t("actions.retry")}
        </Button>
      ) : null}
    </div>
  );
}
