"use client";

import {
  AlertCircle,
  ExternalLink,
  Pencil,
  Plus,
  Rss,
  Trash2,
  X,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import {
  ChannelAvatar,
  channelDisplayName,
} from "@/components/publications/network-icon";
import { PublicationErrorAlert } from "@/components/publications/publication-error-alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { SegmentedControl } from "@/components/ui/segmented-control";
import { Select } from "@/components/ui/select";
import { useIsAccountAdmin } from "@/lib/api/profile";
import {
  type Autopost,
  type AutopostMode,
  type FeedPreviewItem,
  type ParsedPublicationError,
  parsePublicationError,
  useCreatePublicationAutopost,
  useDeletePublicationAutopost,
  usePreviewPublicationAutopost,
  usePublicationAutoposts,
  usePublicationChannels,
  useUpdatePublicationAutopost,
} from "@/lib/api/publications";
import { relativeTime } from "@/lib/time";
import { cn } from "@/lib/utils";

type ChannelScope = "all" | "selected";

function formatReviewedAgo(iso: string | null): string {
  if (!iso) return "Sin revisar todavía";
  const ms = Date.parse(iso);
  if (Number.isNaN(ms)) return "Sin revisar todavía";
  const rel = relativeTime(Math.floor(ms / 1000));
  if (!rel) return "Sin revisar todavía";
  if (rel === "ahora" || rel.startsWith("hace ")) {
    return `Revisado ${rel}`;
  }
  return `Revisado el ${rel}`;
}

function formatPreviewDate(iso: string | null): string | null {
  if (!iso) return null;
  const ms = Date.parse(iso);
  if (Number.isNaN(ms)) return null;
  return new Date(ms).toLocaleDateString();
}

export function AutopostsView({ accountId }: { accountId: string }) {
  const isAdmin = useIsAccountAdmin(accountId);
  const autopostsQuery = usePublicationAutoposts(accountId);
  const channelsQuery = usePublicationChannels(accountId);
  const createMutation = useCreatePublicationAutopost(accountId);
  const updateMutation = useUpdatePublicationAutopost(accountId);
  const deleteMutation = useDeletePublicationAutopost(accountId);
  const previewMutation = usePreviewPublicationAutopost(accountId);

  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<Autopost | null>(null);
  const [name, setName] = useState("");
  const [feedUrl, setFeedUrl] = useState("");
  const [mode, setMode] = useState<AutopostMode>("publish");
  const [channelScope, setChannelScope] = useState<ChannelScope>("all");
  const [selectedChannelIds, setSelectedChannelIds] = useState<number[]>([]);
  const [startWithLatest, setStartWithLatest] = useState(false);
  const [active, setActive] = useState(true);

  const [previewItems, setPreviewItems] = useState<FeedPreviewItem[] | null>(
    null,
  );
  const [previewError, setPreviewError] =
    useState<ParsedPublicationError | null>(null);
  const [dialogError, setDialogError] = useState<ParsedPublicationError | null>(
    null,
  );
  const [pageError, setPageError] = useState<ParsedPublicationError | null>(
    null,
  );

  const dialogRef = useRef<HTMLDialogElement>(null);
  const errorRef = useRef<HTMLDivElement>(null);

  const channels = useMemo(
    () => channelsQuery.data ?? [],
    [channelsQuery.data],
  );
  const activeChannels = useMemo(
    () => channels.filter((c) => c.status === "active"),
    [channels],
  );
  const channelById = useMemo(
    () => new Map(channels.map((c) => [c.id, c])),
    [channels],
  );

  useEffect(() => {
    const el = dialogRef.current;
    if (!el) return;
    if (dialogOpen) {
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
  }, [dialogOpen]);

  useEffect(() => {
    if (dialogError) {
      errorRef.current?.scrollIntoView?.({ block: "nearest" });
    }
  }, [dialogError]);

  function openCreate() {
    setEditing(null);
    setName("");
    setFeedUrl("");
    setMode("publish");
    setChannelScope("all");
    setSelectedChannelIds([]);
    setStartWithLatest(false);
    setActive(true);
    setPreviewItems(null);
    setPreviewError(null);
    setDialogError(null);
    setDialogOpen(true);
  }

  function openEdit(item: Autopost) {
    setEditing(item);
    setName(item.name);
    setFeedUrl(item.feed_url);
    setMode(item.mode);
    if (item.channel_ids.length > 0) {
      setChannelScope("selected");
      setSelectedChannelIds(item.channel_ids);
    } else {
      setChannelScope("all");
      setSelectedChannelIds([]);
    }
    setStartWithLatest(item.start_with_latest);
    setActive(item.active);
    setPreviewItems(null);
    setPreviewError(null);
    setDialogError(null);
    setDialogOpen(true);
  }

  function closeDialog() {
    setDialogOpen(false);
    setEditing(null);
    setDialogError(null);
    setPreviewError(null);
  }

  function toggleChannel(channelId: number) {
    setSelectedChannelIds((prev) =>
      prev.includes(channelId)
        ? prev.filter((id) => id !== channelId)
        : [...prev, channelId],
    );
  }

  async function handlePreview() {
    setPreviewError(null);
    setPreviewItems(null);
    const trimmedUrl = feedUrl.trim();
    if (!trimmedUrl) {
      setPreviewError({
        message: "Ingresá la URL del feed para probarlo.",
        errors: [],
      });
      return;
    }

    try {
      const res = await previewMutation.mutateAsync(trimmedUrl);
      setPreviewItems((res.items ?? []).slice(0, 5));
    } catch (err) {
      setPreviewError(
        parsePublicationError(err, "No se pudo leer el feed indicado."),
      );
    }
  }

  const isSubmitting = createMutation.isPending || updateMutation.isPending;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setDialogError(null);

    const trimmedName = name.trim();
    const trimmedUrl = feedUrl.trim();

    if (!trimmedName) {
      setDialogError({
        message: "Indicá un nombre para el auto post.",
        errors: [],
      });
      return;
    }

    if (!trimmedUrl) {
      setDialogError({
        message: "Indicá la URL del feed.",
        errors: [],
      });
      return;
    }

    if (channelScope === "selected" && selectedChannelIds.length === 0) {
      setDialogError({
        message: "Elegí al menos un canal o usá «Todos los canales».",
        errors: [],
      });
      return;
    }

    const payload = {
      name: trimmedName,
      feed_url: trimmedUrl,
      mode,
      active,
      start_with_latest: startWithLatest,
      channel_ids: channelScope === "all" ? [] : selectedChannelIds,
    };

    try {
      if (editing) {
        await updateMutation.mutateAsync({
          id: editing.id,
          patch: payload,
        });
      } else {
        await createMutation.mutateAsync(payload);
      }
      closeDialog();
    } catch (err) {
      setDialogError(
        parsePublicationError(err, "No se pudo guardar el auto post."),
      );
    }
  }

  async function handleToggleActive(item: Autopost) {
    setPageError(null);
    try {
      await updateMutation.mutateAsync({
        id: item.id,
        patch: { active: !item.active },
      });
    } catch (err) {
      setPageError(
        parsePublicationError(err, "No se pudo actualizar el auto post."),
      );
    }
  }

  async function handleDelete(item: Autopost) {
    setPageError(null);
    try {
      await deleteMutation.mutateAsync(item.id);
    } catch (err) {
      setPageError(
        parsePublicationError(err, "No se pudo borrar el auto post."),
      );
    }
  }

  const autoposts = autopostsQuery.data ?? [];

  return (
    <div className="max-w-3xl space-y-4">
      <div className="space-y-1">
        <h2 className="text-xl font-medium text-fg">Auto post</h2>
        <p className="text-sm text-fg-muted">
          Publicá o guardá como borrador automáticamente las nuevas entradas de
          tus feeds RSS o Atom en tus redes sociales.
        </p>
      </div>

      {isAdmin ? (
        <div className="rounded-xl border border-glass bg-surface-1 p-5">
          <Button type="button" onClick={openCreate}>
            <Plus className="h-4 w-4" aria-hidden />
            Agregar auto post
          </Button>
        </div>
      ) : null}

      <PublicationErrorAlert
        error={pageError}
        onDismiss={() => setPageError(null)}
      />

      <div className="overflow-hidden rounded-xl border border-glass bg-surface">
        {autopostsQuery.isLoading ? (
          <p className="p-8 text-center text-sm text-fg-muted">Cargando…</p>
        ) : autopostsQuery.isError ? (
          <p role="alert" className="p-8 text-center text-sm text-danger">
            No se pudieron cargar los auto posts.
          </p>
        ) : autoposts.length === 0 ? (
          <p className="p-8 text-center text-sm text-fg-muted">
            No hay feeds configurados todavía.
          </p>
        ) : (
          <ul className="divide-y divide-glass">
            {autoposts.map((item) => {
              const targetChannels = item.channel_ids
                .map((id) => channelById.get(id))
                .filter((ch): ch is NonNullable<typeof ch> => Boolean(ch));

              return (
                <li
                  key={item.id}
                  className="space-y-2 px-4 py-3.5 transition-colors hover:bg-hover-glass"
                >
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="flex min-w-0 flex-1 items-start gap-3">
                      <span className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-focused text-lit">
                        <Rss className="h-4 w-4" aria-hidden />
                      </span>
                      <div className="min-w-0 flex-1 space-y-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <p className="truncate text-sm font-medium text-fg">
                            {item.name}
                          </p>
                          <span
                            className={cn(
                              "rounded-sm border px-2 py-0.5 text-xs font-medium",
                              item.active
                                ? "border-success bg-surface-2 text-success"
                                : "border-glass bg-surface-2 text-fg-muted",
                            )}
                          >
                            {item.active ? "Activo" : "Pausado"}
                          </span>
                          <span className="rounded-sm border border-glass bg-focused px-2 py-0.5 text-xs text-lit">
                            {item.mode === "publish"
                              ? "Publicar enseguida"
                              : "Guardar como borrador"}
                          </span>
                        </div>

                        <p className="truncate text-xs text-fg-muted">
                          {item.feed_url}
                        </p>

                        <div className="flex flex-wrap items-center gap-3 text-xs text-fg-muted">
                          <span className="font-numeric tabular-nums">
                            {formatReviewedAgo(item.last_checked_at)}
                          </span>
                          <span>·</span>
                          {item.channel_ids.length === 0 ? (
                            <span>Todos los canales</span>
                          ) : targetChannels.length > 0 ? (
                            <span className="inline-flex items-center gap-1.5">
                              {targetChannels.map((ch) => (
                                <span
                                  key={ch.id}
                                  className="inline-flex items-center gap-1"
                                >
                                  <ChannelAvatar channel={ch} size="sm" />
                                  <span>{channelDisplayName(ch)}</span>
                                </span>
                              ))}
                            </span>
                          ) : (
                            <span>
                              {item.channel_ids.length}{" "}
                              {item.channel_ids.length === 1
                                ? "canal"
                                : "canales"}
                            </span>
                          )}
                        </div>
                      </div>
                    </div>

                    {isAdmin ? (
                      <div className="flex shrink-0 items-center gap-1">
                        <Button
                          type="button"
                          size="sm"
                          variant="ghost"
                          disabled={updateMutation.isPending}
                          onClick={() => void handleToggleActive(item)}
                        >
                          {item.active ? "Pausar" : "Activar"}
                        </Button>
                        <button
                          type="button"
                          aria-label="Editar auto post"
                          title="Editar auto post"
                          onClick={() => openEdit(item)}
                          className="rounded-md p-1.5 text-fg-muted hover:bg-surface-2 hover:text-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                        >
                          <Pencil className="h-4 w-4" aria-hidden />
                        </button>
                        <button
                          type="button"
                          aria-label="Borrar auto post"
                          title="Borrar auto post"
                          disabled={deleteMutation.isPending}
                          onClick={() => void handleDelete(item)}
                          className="rounded-md p-1.5 text-fg-muted hover:bg-surface-2 hover:text-danger disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                        >
                          <Trash2 className="h-4 w-4" aria-hidden />
                        </button>
                      </div>
                    ) : null}
                  </div>

                  {item.last_error ? (
                    <div
                      role="status"
                      className="flex items-start gap-2 rounded-md border border-danger bg-surface-2 px-3 py-2 text-xs text-danger"
                    >
                      <AlertCircle
                        className="mt-0.5 h-3.5 w-3.5 shrink-0"
                        aria-hidden
                      />
                      <span>Último error: {item.last_error}</span>
                    </div>
                  ) : null}
                </li>
              );
            })}
          </ul>
        )}
      </div>

      {isAdmin ? (
        <dialog
          ref={dialogRef}
          onClose={closeDialog}
          aria-labelledby="autopost-dialog-title"
          className="max-h-[92dvh] w-full max-w-2xl overflow-y-auto rounded-panel border border-glass bg-surface p-0 text-fg shadow-menu backdrop:bg-backdrop backdrop:opacity-80"
        >
          <form onSubmit={(e) => void handleSubmit(e)} className="space-y-4 p-5">
            <div className="flex items-center justify-between border-b border-glass pb-3">
              <h3
                id="autopost-dialog-title"
                className="text-lg font-medium text-fg"
              >
                {editing ? "Editar auto post" : "Agregar auto post"}
              </h3>
              <button
                type="button"
                aria-label="Cerrar diálogo"
                onClick={closeDialog}
                className="inline-flex h-8 w-8 items-center justify-center rounded-md text-fg-muted hover:bg-hover-glass focus-visible:outline focus-visible:outline-2 focus-visible:outline-neon"
              >
                <X className="h-4 w-4" aria-hidden />
              </button>
            </div>

            <div ref={errorRef}>
              <PublicationErrorAlert
                error={dialogError}
                onDismiss={() => setDialogError(null)}
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="autopost-name" required>
                Nombre
              </Label>
              <Input
                id="autopost-name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Ej: Blog de novedades"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="autopost-feed-url" required>
                URL del feed
              </Label>
              <div className="flex flex-wrap items-center gap-2">
                <Input
                  id="autopost-feed-url"
                  type="url"
                  value={feedUrl}
                  onChange={(e) => {
                    setFeedUrl(e.target.value);
                    setPreviewError(null);
                  }}
                  placeholder="https://ejemplo.com/feed.xml"
                  className="min-w-[220px] flex-1"
                />
                <Button
                  type="button"
                  variant="secondary"
                  loading={previewMutation.isPending}
                  onClick={() => void handlePreview()}
                >
                  Probar
                </Button>
              </div>

              <PublicationErrorAlert
                error={previewError}
                onDismiss={() => setPreviewError(null)}
              />

              {previewItems !== null ? (
                <div className="rounded-md border border-glass bg-surface-2 p-3">
                  <p className="mb-2 text-xs font-medium text-fg-muted">
                    Últimas entradas encontradas ({previewItems.length})
                  </p>
                  {previewItems.length === 0 ? (
                    <p className="text-xs text-fg-muted">
                      El feed no tiene entradas publicadas.
                    </p>
                  ) : (
                    <ul className="divide-y divide-glass">
                      {previewItems.map((entry, idx) => {
                        const dateStr = formatPreviewDate(entry.published_at);
                        return (
                          <li
                            key={`${entry.link}-${idx}`}
                            className="flex items-start justify-between gap-3 py-2 first:pt-0 last:pb-0"
                          >
                            <div className="min-w-0 flex-1 space-y-0.5">
                              <p className="truncate text-sm font-medium text-fg">
                                {entry.title || entry.link}
                              </p>
                              <div className="flex flex-wrap items-center gap-2 text-xs text-fg-muted">
                                {dateStr ? (
                                  <span className="font-numeric tabular-nums">
                                    {dateStr}
                                  </span>
                                ) : null}
                                {entry.link ? (
                                  <a
                                    href={entry.link}
                                    target="_blank"
                                    rel="noreferrer"
                                    className="inline-flex items-center gap-1 text-lit hover:underline"
                                  >
                                    Ver entrada
                                    <ExternalLink
                                      className="h-3 w-3"
                                      aria-hidden
                                    />
                                  </a>
                                ) : null}
                              </div>
                            </div>
                            {entry.image_url ? (
                              // eslint-disable-next-line @next/next/no-img-element
                              <img
                                src={entry.image_url}
                                alt=""
                                className="h-10 w-10 shrink-0 rounded border border-glass object-cover"
                              />
                            ) : null}
                          </li>
                        );
                      })}
                    </ul>
                  )}
                </div>
              ) : null}
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="autopost-mode">
                ¿Qué hacer con cada entrada nueva?
              </Label>
              <Select
                id="autopost-mode"
                value={mode}
                onChange={(e) => setMode(e.target.value as AutopostMode)}
              >
                <option value="publish">Publicar enseguida</option>
                <option value="draft">Guardar como borrador</option>
              </Select>
            </div>

            <div className="space-y-2">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <Label>Canales</Label>
                <SegmentedControl<ChannelScope>
                  ariaLabel="Alcance de canales"
                  size="sm"
                  value={channelScope}
                  onValueChange={setChannelScope}
                  options={[
                    { value: "all", label: "Todos los canales" },
                    { value: "selected", label: "Algunos canales" },
                  ]}
                />
              </div>

              {channelScope === "selected" ? (
                activeChannels.length === 0 ? (
                  <p className="rounded-md border border-glass bg-field px-3 py-2 text-xs text-fg-muted">
                    No hay canales activos conectados en esta cuenta.
                  </p>
                ) : (
                  <div className="flex flex-wrap gap-2">
                    {activeChannels.map((ch) => {
                      const selected = selectedChannelIds.includes(ch.id);
                      return (
                        <button
                          key={ch.id}
                          type="button"
                          aria-pressed={selected}
                          onClick={() => toggleChannel(ch.id)}
                          className={cn(
                            "inline-flex items-center gap-2 rounded-control border px-3 py-1.5 text-sm transition-colors",
                            "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-neon",
                            selected
                              ? "border-neon bg-focused font-medium text-lit"
                              : "border-glass bg-field text-fg-muted hover:bg-hover-glass hover:text-fg",
                          )}
                        >
                          <ChannelAvatar channel={ch} size="sm" />
                          <span>{channelDisplayName(ch)}</span>
                        </button>
                      );
                    })}
                  </div>
                )
              ) : (
                <p className="text-xs text-fg-muted">
                  Se publicará en todos los canales activos conectados a la
                  cuenta.
                </p>
              )}
            </div>

            <div className="space-y-2.5 pt-1">
              <label className="flex cursor-pointer items-center gap-2.5 text-sm text-fg">
                <input
                  type="checkbox"
                  checked={startWithLatest}
                  onChange={(e) => setStartWithLatest(e.target.checked)}
                  className="h-4 w-4 rounded border-glass bg-field accent-primary"
                />
                <span>
                  Publicar también la última entrada que ya está en el feed
                </span>
              </label>

              <label className="flex cursor-pointer items-center gap-2.5 text-sm text-fg">
                <input
                  type="checkbox"
                  checked={active}
                  onChange={(e) => setActive(e.target.checked)}
                  className="h-4 w-4 rounded border-glass bg-field accent-primary"
                />
                <span>Activo</span>
              </label>
            </div>

            <div className="flex items-center justify-end gap-2 border-t border-glass pt-3">
              <Button
                type="button"
                variant="ghost"
                onClick={closeDialog}
                disabled={isSubmitting}
              >
                Cancelar
              </Button>
              <Button type="submit" loading={isSubmitting}>
                {editing ? "Guardar cambios" : "Guardar auto post"}
              </Button>
            </div>
          </form>
        </dialog>
      ) : null}
    </div>
  );
}
