"use client";

import { FolderOpen, Pencil, Plus, Trash2 } from "lucide-react";
import { useMemo, useState } from "react";

import {
  ChannelAvatar,
  channelDisplayName,
} from "@/components/publications/network-icon";
import { PublicationEditorDialog } from "@/components/publications/publication-editor-dialog";
import { PublicationErrorAlert } from "@/components/publications/publication-error-alert";
import { Button } from "@/components/ui/button";
import { useIsAccountAdmin } from "@/lib/api/profile";
import {
  type ParsedPublicationError,
  parsePublicationError,
  type PublicationSet,
  useDeletePublicationSet,
  usePublicationChannels,
  usePublicationSets,
} from "@/lib/api/publications";

function formatSetDate(iso: string | null): string {
  if (!iso) return "—";
  const ms = Date.parse(iso);
  if (Number.isNaN(ms)) return "—";
  return new Date(ms).toLocaleDateString();
}

export function SetsView({ accountId }: { accountId: string }) {
  const isAdmin = useIsAccountAdmin(accountId);
  const setsQuery = usePublicationSets(accountId);
  const channelsQuery = usePublicationChannels(accountId);
  const deleteMutation = useDeletePublicationSet(accountId);

  const [editorOpen, setEditorOpen] = useState(false);
  const [editingSet, setEditingSet] = useState<PublicationSet | null>(null);
  const [pageError, setPageError] = useState<ParsedPublicationError | null>(
    null,
  );

  const channels = useMemo(
    () => channelsQuery.data ?? [],
    [channelsQuery.data],
  );
  const channelById = useMemo(
    () => new Map(channels.map((c) => [c.id, c])),
    [channels],
  );

  const sets = setsQuery.data ?? [];

  function openCreate() {
    setEditingSet(null);
    setEditorOpen(true);
  }

  function openEdit(item: PublicationSet) {
    setEditingSet(item);
    setEditorOpen(true);
  }

  function closeEditor() {
    setEditorOpen(false);
    setEditingSet(null);
  }

  async function handleDelete(item: PublicationSet) {
    setPageError(null);
    try {
      await deleteMutation.mutateAsync(item.id);
    } catch (err) {
      setPageError(parsePublicationError(err, "No se pudo borrar el set."));
    }
  }

  return (
    <div className="max-w-3xl space-y-4">
      <div className="space-y-1">
        <h2 className="text-xl font-medium text-fg">Sets ({sets.length})</h2>
        <p className="text-sm text-fg-muted">
          Gestioná tus sets de contenido para reutilizarlos fácilmente en tus
          publicaciones.
        </p>
      </div>

      {isAdmin ? (
        <div className="rounded-xl border border-glass bg-surface-1 p-5">
          <Button type="button" onClick={openCreate}>
            <Plus className="h-4 w-4" aria-hidden />
            Agregar set
          </Button>
        </div>
      ) : null}

      <PublicationErrorAlert
        error={pageError}
        onDismiss={() => setPageError(null)}
      />

      <div className="overflow-hidden rounded-xl border border-glass bg-surface">
        {setsQuery.isLoading ? (
          <p className="p-8 text-center text-sm text-fg-muted">Cargando…</p>
        ) : setsQuery.isError ? (
          <p role="alert" className="p-8 text-center text-sm text-danger">
            No se pudieron cargar los sets.
          </p>
        ) : sets.length === 0 ? (
          <p className="p-8 text-center text-sm text-fg-muted">
            No hay sets guardados todavía.
          </p>
        ) : (
          <ul className="divide-y divide-glass">
            {sets.map((item) => {
              const resolvedChannels = item.targets
                .map((t) => t.channel ?? channelById.get(t.channel_id) ?? null)
                .filter((ch): ch is NonNullable<typeof ch> => ch !== null);

              return (
                <li
                  key={item.id}
                  className="flex flex-wrap items-center justify-between gap-3 px-4 py-3.5 transition-colors hover:bg-hover-glass"
                >
                  <div className="flex min-w-0 flex-1 items-center gap-3">
                    <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-focused text-lit">
                      <FolderOpen className="h-4 w-4" aria-hidden />
                    </span>
                    <div className="min-w-0 flex-1 space-y-0.5">
                      <p className="truncate text-sm font-medium text-fg">
                        {item.name}
                      </p>
                      {item.content ? (
                        <p className="truncate text-xs text-fg-muted">
                          {item.content}
                        </p>
                      ) : null}
                    </div>
                  </div>

                  <div className="flex items-center gap-3">
                    {resolvedChannels.length > 0 ? (
                      <div
                        className="flex items-center -space-x-1.5"
                        aria-label={`Canales: ${resolvedChannels.map(channelDisplayName).join(", ")}`}
                      >
                        {resolvedChannels.map((ch) => (
                          <ChannelAvatar key={ch.id} channel={ch} size="sm" />
                        ))}
                      </div>
                    ) : (
                      <span className="text-xs text-fg-muted">Sin canales</span>
                    )}

                    <span className="font-numeric text-xs tabular-nums text-fg-muted">
                      {formatSetDate(item.updated_at ?? item.created_at)}
                    </span>

                    {isAdmin ? (
                      <div className="flex items-center gap-1">
                        <button
                          type="button"
                          aria-label="Editar set"
                          title="Editar set"
                          onClick={() => openEdit(item)}
                          className="rounded-md p-1.5 text-fg-muted hover:bg-surface-2 hover:text-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                        >
                          <Pencil className="h-4 w-4" aria-hidden />
                        </button>
                        <button
                          type="button"
                          aria-label="Borrar set"
                          title="Borrar set"
                          disabled={deleteMutation.isPending}
                          onClick={() => void handleDelete(item)}
                          className="rounded-md p-1.5 text-fg-muted hover:bg-surface-2 hover:text-danger disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                        >
                          <Trash2 className="h-4 w-4" aria-hidden />
                        </button>
                      </div>
                    ) : null}
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </div>

      {isAdmin ? (
        <PublicationEditorDialog
          accountId={accountId}
          open={editorOpen}
          onClose={closeEditor}
          channels={channels}
          isAdmin={isAdmin}
          mode="set"
          initialSet={editingSet}
        />
      ) : null}
    </div>
  );
}
