import type { PostState } from "@/lib/api/instagram-posts";
import { cn } from "@/lib/utils";
import type { MessageKey } from "@/lib/i18n/translate";
import { useT } from "@/lib/i18n/provider";

const STYLES: Record<PostState, string> = {
  pending: "bg-warning/10 text-warning",
  publishing: "bg-info/10 text-info",
  published: "bg-success/10 text-success",
  failed: "bg-danger/10 text-danger",
  deleted: "bg-surface-2 text-fg-muted",
};

const LABELS: Record<PostState, MessageKey> = {
  pending: "instagram.state.pending",
  publishing: "instagram.state.publishing",
  published: "instagram.state.published",
  failed: "instagram.state.failed",
  deleted: "instagram.state.deleted",
};

export function StateBadge({ state }: { state: PostState }) {
  const t = useT();
  return (
    <span
      className={cn(
        "inline-flex rounded-full px-2 py-0.5 text-xs font-medium",
        STYLES[state] ?? "bg-surface-2 text-fg-muted",
      )}
    >
      {LABELS[state] ? t(LABELS[state]) : state}
    </span>
  );
}
