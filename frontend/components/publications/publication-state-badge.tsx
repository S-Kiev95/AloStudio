import type { PublicationState, TargetState } from "@/lib/api/publications";
import { cn } from "@/lib/utils";
import type { MessageKey } from "@/lib/i18n/translate";
import { useT } from "@/lib/i18n/provider";

export const PUBLICATION_STATE_LABELS: Record<PublicationState, MessageKey> = {
  draft: "publications.state.draft",
  scheduled: "publications.state.scheduled",
  publishing: "publications.state.publishing",
  published: "publications.state.published",
  partially_published: "publications.state.partially_published",
  failed: "publications.state.failed",
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
  label: MessageKey;
}[] = [
  { value: undefined, label: "publications.state.all" },
  { value: "draft", label: "publications.state.draft" },
  { value: "scheduled", label: "publications.state.scheduled" },
  { value: "publishing", label: "publications.state.publishing" },
  { value: "published", label: "publications.state.published" },
  { value: "partially_published", label: "publications.state.partially_published" },
  { value: "failed", label: "publications.state.failed" },
];

export function PublicationStateBadge({
  state,
  className,
}: {
  state: PublicationState;
  className?: string;
}) {
  const t = useT();
  return (
    <span
      className={cn(
        "inline-flex shrink-0 items-center rounded-pill px-2 py-0.5 text-[11px] font-medium leading-tight",
        PUBLICATION_STATE_STYLES[state] ?? "bg-surface-2 text-fg-muted",
        className,
      )}
    >
      {PUBLICATION_STATE_LABELS[state] ? t(PUBLICATION_STATE_LABELS[state]) : state}
    </span>
  );
}

const TARGET_STATE_LABELS: Record<TargetState, MessageKey> = {
  pending: "publications.state.pending",
  publishing: "publications.state.publishing",
  published: "publications.state.published",
  failed: "publications.state.failed",
};

const TARGET_STATE_STYLES: Record<TargetState, string> = {
  pending: "bg-surface-2 text-fg-muted",
  publishing: "bg-info/10 text-info",
  published: "bg-success/10 text-success",
  failed: "bg-danger/10 text-danger",
};

export function TargetStateBadge({ state }: { state: TargetState }) {
  const t = useT();
  return (
    <span
      className={cn(
        "inline-flex shrink-0 items-center rounded-pill px-2 py-0.5 text-[11px] font-medium leading-tight",
        TARGET_STATE_STYLES[state] ?? "bg-surface-2 text-fg-muted",
      )}
    >
      {TARGET_STATE_LABELS[state] ? t(TARGET_STATE_LABELS[state]) : state}
    </span>
  );
}
