import type { PublicationState, TargetState } from "@/lib/api/publications";
import { cn } from "@/lib/utils";

export const PUBLICATION_STATE_LABELS: Record<PublicationState, string> = {
  draft: "Borrador",
  scheduled: "Programada",
  publishing: "Publicando",
  published: "Publicada",
  partially_published: "Publicada en parte",
  failed: "Falló",
};

const PUBLICATION_STATE_STYLES: Record<PublicationState, string> = {
  draft: "bg-surface-2 text-fg-muted",
  scheduled: "bg-info/10 text-info",
  publishing: "bg-warning/10 text-warning",
  published: "bg-success/10 text-success",
  partially_published: "bg-warning/15 text-warning",
  failed: "bg-danger/10 text-danger",
};

export const PUBLICATION_STATE_FILTERS: {
  value: PublicationState | undefined;
  label: string;
}[] = [
  { value: undefined, label: "Todas" },
  { value: "draft", label: "Borrador" },
  { value: "scheduled", label: "Programada" },
  { value: "publishing", label: "Publicando" },
  { value: "published", label: "Publicada" },
  { value: "partially_published", label: "Publicada en parte" },
  { value: "failed", label: "Falló" },
];

export function PublicationStateBadge({
  state,
  className,
}: {
  state: PublicationState;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex shrink-0 items-center rounded-pill px-2 py-0.5 text-[11px] font-medium leading-tight",
        PUBLICATION_STATE_STYLES[state] ?? "bg-surface-2 text-fg-muted",
        className,
      )}
    >
      {PUBLICATION_STATE_LABELS[state] ?? state}
    </span>
  );
}

const TARGET_STATE_LABELS: Record<TargetState, string> = {
  pending: "Pendiente",
  publishing: "Publicando",
  published: "Publicada",
  failed: "Falló",
};

const TARGET_STATE_STYLES: Record<TargetState, string> = {
  pending: "bg-surface-2 text-fg-muted",
  publishing: "bg-info/10 text-info",
  published: "bg-success/10 text-success",
  failed: "bg-danger/10 text-danger",
};

export function TargetStateBadge({ state }: { state: TargetState }) {
  return (
    <span
      className={cn(
        "inline-flex shrink-0 items-center rounded-pill px-2 py-0.5 text-[11px] font-medium leading-tight",
        TARGET_STATE_STYLES[state] ?? "bg-surface-2 text-fg-muted",
      )}
    >
      {TARGET_STATE_LABELS[state] ?? state}
    </span>
  );
}
