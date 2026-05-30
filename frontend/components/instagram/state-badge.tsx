import type { PostState } from "@/lib/api/instagram-posts";
import { cn } from "@/lib/utils";

const STYLES: Record<PostState, string> = {
  pending: "bg-warning/10 text-warning",
  publishing: "bg-info/10 text-info",
  published: "bg-success/10 text-success",
  failed: "bg-danger/10 text-danger",
  deleted: "bg-surface-2 text-fg-muted",
};

const LABELS: Record<PostState, string> = {
  pending: "Pendiente",
  publishing: "Publicando",
  published: "Publicado",
  failed: "Falló",
  deleted: "Eliminado",
};

export function StateBadge({ state }: { state: PostState }) {
  return (
    <span
      className={cn(
        "inline-flex rounded-full px-2 py-0.5 text-xs font-medium",
        STYLES[state] ?? "bg-surface-2 text-fg-muted",
      )}
    >
      {LABELS[state] ?? state}
    </span>
  );
}
