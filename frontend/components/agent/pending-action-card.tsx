"use client";

import { useState } from "react";

import { NetworkIcon, networkLabel } from "@/components/publications/network-icon";
import { Button } from "@/components/ui/button";
import type { AgentPendingAction } from "@/lib/api/agent";
import { cn } from "@/lib/utils";

import { formatPendingSchedule } from "./agent-time";

const MAX_COLLAPSED_LINES = 8;
const MAX_COLLAPSED_CHARS = 480;

export function PendingActionCard({
  action,
  canWrite,
  disabled = false,
  isConfirming,
  isRejecting,
  error,
  onConfirm,
  onReject,
}: {
  action: AgentPendingAction;
  canWrite: boolean;
  disabled?: boolean;
  isConfirming: boolean;
  isRejecting: boolean;
  error: string | null;
  onConfirm: () => void;
  onReject: () => void;
}) {
  const [expanded, setExpanded] = useState(false);

  const content = action.publication.content ?? "";
  const hasContent = content.trim().length > 0;
  const isCollapsible =
    content.split("\n").length > MAX_COLLAPSED_LINES ||
    Array.from(content).length > MAX_COLLAPSED_CHARS;

  const isCancel = action.tool === "cancel_publication";

  return (
    <div
      data-testid="agent-pending-action-card"
      className="space-y-3 rounded-md border border-glass bg-surface-2 p-4"
    >
      <h3 className="text-sm font-semibold text-fg">{action.title}</h3>

      {action.publication.channels.length > 0 ? (
        <div className="flex flex-wrap items-center gap-2">
          {action.publication.channels.map((ch) => (
            <span
              key={ch.id}
              className="inline-flex items-center gap-1.5 rounded-sm border border-glass bg-field px-2 py-1 text-xs font-medium text-fg"
            >
              <NetworkIcon network={ch.network} />
              <span>{ch.name?.trim() || networkLabel(ch.network)}</span>
            </span>
          ))}
        </div>
      ) : null}

      {hasContent ? (
        <div>
          <p
            className={cn(
              "whitespace-pre-wrap break-words text-sm text-fg",
              !expanded && isCollapsible && "line-clamp-[8]",
            )}
          >
            {content}
          </p>
          {isCollapsible ? (
            <button
              type="button"
              onClick={() => setExpanded((prev) => !prev)}
              className="mt-1 text-xs font-medium text-info hover:underline"
            >
              {expanded ? "Ver menos" : "Ver más"}
            </button>
          ) : null}
        </div>
      ) : null}

      {action.publication.media.length > 0 ? (
        <div className="flex flex-wrap gap-2">
          {action.publication.media.map((m, idx) => (
            <div
              key={m.id ?? `${m.url}-${idx}`}
              className="h-16 w-16 shrink-0 overflow-hidden rounded-md border border-glass bg-field"
            >
              {m.type === "video" ? (
                <video
                  src={m.url}
                  preload="metadata"
                  muted
                  className="h-full w-full object-cover"
                />
              ) : (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={m.url}
                  alt={`Medio ${idx + 1}`}
                  loading="lazy"
                  className="h-full w-full object-cover"
                />
              )}
            </div>
          ))}
        </div>
      ) : null}

      <p className="font-numeric text-xs font-medium tabular-nums text-fg-muted">
        {formatPendingSchedule(action)}
      </p>

      {error ? (
        <p role="alert" className="text-xs text-danger">
          {error}
        </p>
      ) : null}

      <div className="flex flex-wrap items-center gap-2 pt-0.5">
        {canWrite ? (
          <Button
            type="button"
            size="sm"
            variant={isCancel ? "destructive" : "primary"}
            loading={isConfirming}
            disabled={isRejecting || disabled}
            onClick={onConfirm}
          >
            {action.confirm_label}
          </Button>
        ) : null}
        <Button
          type="button"
          size="sm"
          variant="secondary"
          loading={isRejecting}
          disabled={isConfirming || disabled}
          onClick={onReject}
        >
          Cancelar
        </Button>
      </div>

      <p className="text-xs text-fg-muted">
        Si querés cambiar algo, escribilo y el agente arma una nueva propuesta.
      </p>
    </div>
  );
}
