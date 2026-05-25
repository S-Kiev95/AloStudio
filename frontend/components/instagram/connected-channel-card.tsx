"use client";

import { Instagram, Trash2 } from "lucide-react";

import { type Inbox, useChannelSettings } from "@/lib/api/instagram";
import { cn } from "@/lib/utils";

/** One connected Instagram channel + its capabilities (login type). */
export function ConnectedChannelCard({
  accountId,
  inbox,
}: {
  accountId: string;
  inbox: Inbox;
}) {
  const settings = useChannelSettings(accountId, inbox.channel_id);

  // No settings row (404) = legacy Phase-5e channel → treat as Facebook.
  const loginType = settings.data?.login_type ?? "facebook";
  const canDelete = settings.data?.can_delete_media ?? true;

  return (
    <div className="flex items-center gap-3 rounded-lg border border-border bg-surface p-4">
      <span className="flex h-10 w-10 items-center justify-center rounded-full bg-primary/10 text-primary">
        <Instagram className="h-5 w-5" aria-hidden />
      </span>
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium text-fg">{inbox.name}</p>
        <p className="text-xs text-fg-muted">
          {loginType === "instagram" ? "Instagram Login" : "Facebook Login"}
        </p>
      </div>
      <span
        className={cn(
          "flex items-center gap-1 rounded-full px-2 py-0.5 text-xs",
          canDelete
            ? "bg-success/10 text-success"
            : "bg-warning/10 text-warning",
        )}
        title={
          canDelete
            ? "Puede borrar publicaciones por API"
            : "Instagram Login no permite borrar por API"
        }
      >
        <Trash2 className="h-3 w-3" aria-hidden />
        {canDelete ? "Borrado: sí" : "Borrado: no"}
      </span>
    </div>
  );
}
