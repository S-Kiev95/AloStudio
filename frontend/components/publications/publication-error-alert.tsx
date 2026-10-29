"use client";

import { X } from "lucide-react";

import type { ParsedPublicationError } from "@/lib/api/publications";
import { cn } from "@/lib/utils";

export function PublicationErrorAlert({
  error,
  onDismiss,
  className,
}: {
  error: ParsedPublicationError | null;
  onDismiss?: () => void;
  className?: string;
}) {
  if (!error) return null;

  return (
    <div
      role="alert"
      className={cn(
        "flex items-start justify-between gap-2 rounded-md border border-danger/30 bg-danger/5 px-3 py-2 text-sm text-danger",
        className,
      )}
    >
      <div className="min-w-0 flex-1">
        <p>{error.message}</p>
        {error.errors.length > 0 ? (
          <ul className="mt-1 list-disc space-y-0.5 pl-5 text-xs">
            {error.errors.map((item, idx) => (
              <li key={idx}>{item}</li>
            ))}
          </ul>
        ) : null}
      </div>
      {onDismiss ? (
        <button
          type="button"
          aria-label="Cerrar aviso"
          onClick={onDismiss}
          className="inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-sm text-danger/80 hover:bg-danger/10 hover:text-danger"
        >
          <X className="h-3.5 w-3.5" aria-hidden />
        </button>
      ) : null}
    </div>
  );
}
