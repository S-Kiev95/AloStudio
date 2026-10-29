"use client";

import {
  ExternalLink,
  Pencil,
  RefreshCw,
  RotateCcw,
  Trash2,
  X,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { formatDateTimeLocal } from "@/components/agenda/week-utils";
import { Button } from "@/components/ui/button";
import {
  canDeletePublication,
  canEditPublication,
  canRefreshMetrics,
  canRetryPublication,
  type MetricName,
  type ParsedPublicationError,
  parsePublicationError,
  type Publication,
  useDeletePublication,
  usePublication,
  useRefreshPublicationMetrics,
  useRetryPublication,
} from "@/lib/api/publications";

import { ChannelAvatar, channelDisplayName } from "./network-icon";
import { PublicationErrorAlert } from "./publication-error-alert";
import {
  PublicationStateBadge,
  TargetStateBadge,
} from "./publication-state-badge";

const METRIC_FIELDS: { key: MetricName; label: string }[] = [
  { key: "views", label: "Vistas" },
  { key: "reach", label: "Alcance" },
  { key: "interactions", label: "Interacciones" },
  { key: "likes", label: "Me gusta" },
  { key: "comments", label: "Comentarios" },
  { key: "shares", label: "Compartidos" },
  { key: "saves", label: "Guardados" },
];

export function formatUpdatedAgo(iso: string | null | undefined): string {
  if (!iso) return "";
  const ms = new Date(iso).getTime();
  if (Number.isNaN(ms)) return "";
  const diffSec = Math.max(0, Math.round((Date.now() - ms) / 1000));
  if (diffSec < 60) return "actualizado hace menos de 1m";
  const min = Math.round(diffSec / 60);
  if (min < 60) return `actualizado hace ${min}m`;
  const hr = Math.round(min / 60);
  if (hr < 24) return `actualizado hace ${hr}h`;
  const days = Math.round(hr / 24);
  return `actualizado hace ${days}d`;
}

export function formatMetricValue(val: number | null | undefined): string {
  return val == null ? "—" : val.toLocaleString();
}

export function PublicationDetailDialog({
  accountId,
  publication,
  open,
  onClose,
  isAdmin,
  onEdit,
}: {
  accountId: string;
  publication: Publication | null;
  open: boolean;
  onClose: () => void;
  isAdmin: boolean;
  onEdit?: (pub: Publication) => void;
}) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const [error, setError] = useState<ParsedPublicationError | null>(null);

  const detailQuery = usePublication(
    accountId,
    open && publication ? publication.id : null,
    publication ?? undefined,
  );
  const retryMutation = useRetryPublication(accountId);
  const refreshMutation = useRefreshPublicationMetrics(accountId);
  const deleteMutation = useDeletePublication(accountId);

  useEffect(() => {
    const el = dialogRef.current;
    if (!el) return;
    if (open) {
      if (!el.open) {
        if (typeof el.showModal === "function") {
          el.showModal();
        } else {
          el.setAttribute("open", "");
        }
      }
    } else if (el.open) {
      if (typeof el.close === "function") {
        el.close();
      } else {
        el.removeAttribute("open");
      }
    }
  }, [open]);

  useEffect(() => {
    if (open) setError(null);
  }, [open, publication?.id]);

  const pub = detailQuery.data ?? publication;
  if (!open || !pub) return null;

  const dateIso = pub.published_at ?? pub.scheduled_for ?? pub.created_at;
  const dateLabel = dateIso ? formatDateTimeLocal(dateIso) : "Sin fecha";

  async function handleRetry() {
    if (!pub) return;
    setError(null);
    try {
      await retryMutation.mutateAsync(pub.id);
    } catch (err) {
      setError(
        parsePublicationError(err, "No se pudo reintentar la publicación."),
      );
    }
  }

  async function handleRefreshMetrics() {
    if (!pub) return;
    setError(null);
    try {
      await refreshMutation.mutateAsync(pub.id);
    } catch (err) {
      setError(
        parsePublicationError(
          err,
          "No se pudieron actualizar las estadísticas.",
        ),
      );
    }
  }

  async function handleDelete() {
    if (!pub) return;
    if (!window.confirm("¿Borrar esta publicación?")) return;
    setError(null);
    try {
      await deleteMutation.mutateAsync(pub.id);
      onClose();
    } catch (err) {
      setError(
        parsePublicationError(err, "No se pudo borrar la publicación."),
      );
    }
  }

  const showEdit = isAdmin && canEditPublication(pub.state) && Boolean(onEdit);
  const showRetry = isAdmin && canRetryPublication(pub.state);
  const showRefresh = isAdmin && canRefreshMetrics(pub.state);
  const showDelete = isAdmin && canDeletePublication(pub.state);

  return (
    <dialog
      ref={dialogRef}
      onClose={onClose}
      aria-labelledby="publication-detail-title"
      className="max-h-[92dvh] w-full max-w-2xl overflow-y-auto rounded-panel border border-glass bg-surface p-0 text-fg shadow-menu backdrop:bg-backdrop/75"
    >
      <div className="space-y-4 p-5">
        <div className="flex items-start justify-between gap-3 border-b border-glass pb-3">
          <div className="space-y-1">
            <div className="flex flex-wrap items-center gap-2">
              <h2
                id="publication-detail-title"
                className="text-lg font-medium text-fg"
              >
                Detalle de publicación
              </h2>
              <PublicationStateBadge state={pub.state} />
            </div>
            <p className="font-numeric text-xs tabular-nums text-fg-muted">
              {dateLabel}
            </p>
          </div>

          <button
            type="button"
            aria-label="Cerrar diálogo"
            onClick={onClose}
            className="inline-flex h-9 w-9 items-center justify-center rounded-md text-fg-muted hover:bg-hover-glass focus-visible:outline focus-visible:outline-2 focus-visible:outline-neon"
          >
            <X className="h-4 w-4" aria-hidden />
          </button>
        </div>

        <PublicationErrorAlert error={error} onDismiss={() => setError(null)} />

        {pub.content?.trim() ? (
          <div className="rounded-md border border-glass bg-field/60 p-3">
            <p className="whitespace-pre-wrap break-words text-sm text-fg">
              {pub.content}
            </p>
          </div>
        ) : null}

        {pub.media.length > 0 ? (
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
            {pub.media.map((m, idx) => (
              <div
                key={`${m.url}-${idx}`}
                className="aspect-square overflow-hidden rounded-md border border-glass bg-field"
              >
                {m.type === "video" ? (
                  <video
                    controls
                    preload="metadata"
                    src={m.url}
                    className="h-full w-full object-cover"
                  >
                    <track kind="captions" />
                  </video>
                ) : (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    src={m.url}
                    alt={`Medio ${idx + 1}`}
                    className="h-full w-full object-cover"
                  />
                )}
              </div>
            ))}
          </div>
        ) : null}

        {/* Targets */}
        <div className="space-y-3">
          <h3 className="text-xs font-medium uppercase tracking-[0.08em] text-fg-muted">
            Destinos ({pub.targets.length})
          </h3>
          {pub.targets.map((target) => {
            const chName = channelDisplayName(target.channel);
            const hasMetrics =
              Object.keys(target.metrics ?? {}).length > 0 ||
              target.state === "published" ||
              Boolean(target.metrics_updated_at) ||
              Boolean(target.metrics_error);

            return (
              <div
                key={target.id}
                className="space-y-2.5 rounded-md border border-glass bg-surface-2 p-3"
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex items-center gap-2.5">
                    <ChannelAvatar channel={target.channel} size="sm" />
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium text-fg">
                          {chName}
                        </span>
                        {target.settings?.post_type ? (
                          <span className="rounded-sm bg-field px-1.5 py-0.5 text-[10px] uppercase text-fg-muted">
                            {target.settings.post_type}
                          </span>
                        ) : null}
                      </div>
                      {target.channel.username &&
                      chName !== `@${target.channel.username}` ? (
                        <p className="text-xs text-fg-muted">
                          @{target.channel.username}
                        </p>
                      ) : null}
                    </div>
                  </div>

                  <div className="flex items-center gap-2">
                    <TargetStateBadge state={target.state} />
                    {target.permalink ? (
                      <a
                        href={target.permalink}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-1 text-xs font-medium text-info hover:underline"
                      >
                        Ver en la red
                        <ExternalLink className="h-3 w-3" aria-hidden />
                      </a>
                    ) : null}
                  </div>
                </div>

                {target.content_override ? (
                  <p className="whitespace-pre-wrap break-words rounded-sm border border-glass bg-field px-2.5 py-1.5 text-xs text-fg">
                    {target.content_override}
                  </p>
                ) : null}

                {target.error_message ? (
                  <div
                    role="alert"
                    className="rounded-sm border border-danger/30 bg-danger/5 px-2.5 py-2 text-xs text-danger"
                  >
                    {target.error_message}
                  </div>
                ) : null}

                {hasMetrics ? (
                  <div className="space-y-1.5 pt-1">
                    <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                      {METRIC_FIELDS.map((mf) => (
                        <div
                          key={mf.key}
                          className="rounded-sm border border-glass bg-field px-2.5 py-1.5"
                        >
                          <p className="text-[10px] uppercase tracking-wide text-fg-muted">
                            {mf.label}
                          </p>
                          <p className="font-numeric text-sm font-semibold tabular-nums text-fg">
                            {formatMetricValue(target.metrics?.[mf.key])}
                          </p>
                        </div>
                      ))}
                    </div>

                    {target.metrics_error ? (
                      <p className="text-xs text-warning">
                        {target.metrics_error}
                      </p>
                    ) : target.metrics_updated_at ? (
                      <p className="text-xs text-fg-muted">
                        {formatUpdatedAgo(target.metrics_updated_at)}
                      </p>
                    ) : null}
                  </div>
                ) : null}
              </div>
            );
          })}
        </div>

        {/* Admin Actions */}
        {showEdit || showRetry || showRefresh || showDelete ? (
          <div className="flex flex-wrap items-center justify-end gap-2 border-t border-glass pt-3">
            {showEdit && onEdit ? (
              <Button
                type="button"
                size="sm"
                variant="secondary"
                onClick={() => onEdit(pub)}
              >
                <Pencil className="h-4 w-4" aria-hidden />
                Editar
              </Button>
            ) : null}

            {showRefresh ? (
              <Button
                type="button"
                size="sm"
                variant="secondary"
                loading={refreshMutation.isPending}
                onClick={() => void handleRefreshMetrics()}
              >
                <RefreshCw className="h-4 w-4" aria-hidden />
                Actualizar estadísticas
              </Button>
            ) : null}

            {showRetry ? (
              <Button
                type="button"
                size="sm"
                loading={retryMutation.isPending}
                onClick={() => void handleRetry()}
              >
                <RotateCcw className="h-4 w-4" aria-hidden />
                Reintentar
              </Button>
            ) : null}

            {showDelete ? (
              <Button
                type="button"
                size="sm"
                variant="destructive"
                loading={deleteMutation.isPending}
                onClick={() => void handleDelete()}
              >
                <Trash2 className="h-4 w-4" aria-hidden />
                Borrar
              </Button>
            ) : null}
          </div>
        ) : null}
      </div>
    </dialog>
  );
}
