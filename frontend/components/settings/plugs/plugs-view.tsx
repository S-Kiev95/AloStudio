"use client";

import {
  CheckCircle2,
  Pencil,
  Plus,
  Trash2,
  X,
  XCircle,
  Zap,
} from "lucide-react";
import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";

import {
  ChannelAvatar,
  channelDisplayName,
  networkLabel,
} from "@/components/publications/network-icon";
import { textLength } from "@/components/publications/network-rules";
import { PublicationErrorAlert } from "@/components/publications/publication-error-alert";
import { Button, buttonVariants } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { useIsAccountAdmin } from "@/lib/api/profile";
import {
  type Channel,
  type ParsedPublicationError,
  parsePublicationError,
  type Plug,
  type PlugKind,
  useCreatePublicationPlug,
  useDeletePublicationPlug,
  usePublicationChannels,
  usePublicationPlugs,
  usePublicationPlugsCatalog,
  useUpdatePublicationPlug,
} from "@/lib/api/publications";
import { cn } from "@/lib/utils";

function formatRunDate(iso: string | null): string | null {
  if (!iso) return null;
  const ms = Date.parse(iso);
  if (Number.isNaN(ms)) return null;
  return new Date(ms).toLocaleString();
}

export function PlugsView({ accountId }: { accountId: string }) {
  const isAdmin = useIsAccountAdmin(accountId);
  const catalogQuery = usePublicationPlugsCatalog(accountId);
  const channelsQuery = usePublicationChannels(accountId);
  const plugsQuery = usePublicationPlugs(accountId);

  const createMutation = useCreatePublicationPlug(accountId);
  const updateMutation = useUpdatePublicationPlug(accountId);
  const deleteMutation = useDeletePublicationPlug(accountId);

  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<Plug | null>(null);
  const [selectedChannelId, setSelectedChannelId] = useState<number | null>(
    null,
  );
  const [selectedKindKey, setSelectedKindKey] = useState("");
  const [likesThreshold, setLikesThreshold] = useState("10");
  const [message, setMessage] = useState("");
  const [active, setActive] = useState(true);

  const [dialogError, setDialogError] = useState<ParsedPublicationError | null>(
    null,
  );
  const [pageError, setPageError] = useState<ParsedPublicationError | null>(
    null,
  );

  const dialogRef = useRef<HTMLDialogElement>(null);
  const errorRef = useRef<HTMLDivElement>(null);

  const catalogByNetwork = useMemo(() => {
    const map = new Map<string, PlugKind[]>();
    for (const entry of catalogQuery.data ?? []) {
      if (entry.kinds.length > 0) {
        map.set(entry.network, entry.kinds);
      }
    }
    return map;
  }, [catalogQuery.data]);

  const compatibleChannels = useMemo(() => {
    const all = channelsQuery.data ?? [];
    return all.filter((ch) => catalogByNetwork.has(ch.network));
  }, [channelsQuery.data, catalogByNetwork]);

  const channelById = useMemo(
    () => new Map((channelsQuery.data ?? []).map((c) => [c.id, c])),
    [channelsQuery.data],
  );

  const plugsByChannel = useMemo(() => {
    const map = new Map<number, Plug[]>();
    for (const plug of plugsQuery.data ?? []) {
      const list = map.get(plug.channel_id) ?? [];
      list.push(plug);
      map.set(plug.channel_id, list);
    }
    return map;
  }, [plugsQuery.data]);

  const selectedChannel: Channel | null = useMemo(() => {
    if (selectedChannelId === null) return null;
    return channelById.get(selectedChannelId) ?? null;
  }, [channelById, selectedChannelId]);

  const availableKinds = useMemo(() => {
    if (!selectedChannel) return [];
    return catalogByNetwork.get(selectedChannel.network) ?? [];
  }, [catalogByNetwork, selectedChannel]);

  const selectedKind: PlugKind | null = useMemo(() => {
    return availableKinds.find((k) => k.kind === selectedKindKey) ?? null;
  }, [availableKinds, selectedKindKey]);

  const requiresMessage =
    selectedKind !== null && selectedKind.message_max !== null;
  const messageMax = selectedKind?.message_max ?? null;
  const messageCount = useMemo(
    () =>
      requiresMessage
        ? textLength(selectedChannel?.network ?? "", message)
        : 0,
    [requiresMessage, selectedChannel?.network, message],
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

  function openCreate(defaultChannel?: Channel) {
    const firstChannel = defaultChannel ?? compatibleChannels[0] ?? null;
    const kinds = firstChannel
      ? (catalogByNetwork.get(firstChannel.network) ?? [])
      : [];
    setEditing(null);
    setSelectedChannelId(firstChannel?.id ?? null);
    setSelectedKindKey(kinds[0]?.kind ?? "");
    setLikesThreshold("10");
    setMessage("");
    setActive(true);
    setDialogError(null);
    setDialogOpen(true);
  }

  function openEdit(plug: Plug) {
    setEditing(plug);
    setSelectedChannelId(plug.channel_id);
    setSelectedKindKey(plug.kind);
    setLikesThreshold(String(plug.likes_threshold));
    setMessage(plug.message ?? "");
    setActive(plug.active);
    setDialogError(null);
    setDialogOpen(true);
  }

  function closeDialog() {
    setDialogOpen(false);
    setEditing(null);
    setDialogError(null);
  }

  function handleChannelChange(nextId: number) {
    setSelectedChannelId(nextId);
    const ch = channelById.get(nextId);
    const kinds = ch ? (catalogByNetwork.get(ch.network) ?? []) : [];
    const nextKind = kinds[0] ?? null;
    setSelectedKindKey(nextKind?.kind ?? "");
    if (!nextKind || nextKind.message_max === null) {
      setMessage("");
    }
  }

  function handleKindChange(nextKindKey: string) {
    setSelectedKindKey(nextKindKey);
    const nextKind = availableKinds.find((k) => k.kind === nextKindKey) ?? null;
    if (!nextKind || nextKind.message_max === null) {
      setMessage("");
    }
  }

  const isSubmitting = createMutation.isPending || updateMutation.isPending;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setDialogError(null);

    if (selectedChannelId === null || !selectedChannel) {
      setDialogError({
        message: "Elegí un canal para configurar el plug.",
        errors: [],
      });
      return;
    }

    if (!selectedKindKey) {
      setDialogError({
        message: "Elegí una acción del catálogo.",
        errors: [],
      });
      return;
    }

    const parsedThreshold = Number.parseInt(likesThreshold, 10);
    if (!Number.isFinite(parsedThreshold) || parsedThreshold < 1) {
      setDialogError({
        message: "El umbral debe ser al menos 1 me gusta.",
        errors: [],
      });
      return;
    }

    if (requiresMessage && messageMax !== null) {
      if (Array.from(message.trim()).length < 1) {
        setDialogError({
          message: "Escribí el mensaje para esta acción.",
          errors: [],
        });
        return;
      }
      if (messageCount > messageMax) {
        setDialogError({
          message: `El mensaje supera el máximo de ${messageMax} caracteres (${messageCount}/${messageMax}).`,
          errors: [],
        });
        return;
      }
    }

    try {
      if (editing) {
        await updateMutation.mutateAsync({
          id: editing.id,
          patch: {
            likes_threshold: parsedThreshold,
            ...(requiresMessage ? { message } : {}),
            active,
          },
        });
      } else {
        await createMutation.mutateAsync({
          channel_id: selectedChannelId,
          kind: selectedKindKey,
          likes_threshold: parsedThreshold,
          ...(requiresMessage ? { message } : {}),
          active,
        });
      }
      closeDialog();
    } catch (err) {
      setDialogError(parsePublicationError(err, "No se pudo guardar el plug."));
    }
  }

  async function handleToggleActive(plug: Plug) {
    setPageError(null);
    try {
      await updateMutation.mutateAsync({
        id: plug.id,
        patch: { active: !plug.active },
      });
    } catch (err) {
      setPageError(
        parsePublicationError(err, "No se pudo actualizar el plug."),
      );
    }
  }

  async function handleDelete(plug: Plug) {
    setPageError(null);
    try {
      await deleteMutation.mutateAsync(plug.id);
    } catch (err) {
      setPageError(parsePublicationError(err, "No se pudo borrar el plug."));
    }
  }

  const isLoading =
    catalogQuery.isLoading || channelsQuery.isLoading || plugsQuery.isLoading;
  const isError =
    catalogQuery.isError || channelsQuery.isError || plugsQuery.isError;

  return (
    <div className="max-w-3xl space-y-4">
      <div className="space-y-1">
        <h2 className="text-xl font-medium text-fg">Plugs</h2>
        <p className="text-sm text-fg-muted">
          Ejecutá acciones automáticas sobre tus publicaciones cuando alcancen
          un umbral de me gusta.
        </p>
      </div>

      <PublicationErrorAlert
        error={pageError}
        onDismiss={() => setPageError(null)}
      />

      {isLoading ? (
        <div className="rounded-xl border border-glass bg-surface p-8 text-center text-sm text-fg-muted">
          Cargando…
        </div>
      ) : isError ? (
        <div
          role="alert"
          className="rounded-xl border border-glass bg-surface p-8 text-center text-sm text-danger"
        >
          No se pudieron cargar los plugs.
        </div>
      ) : compatibleChannels.length === 0 ? (
        <div className="space-y-4 rounded-xl border border-glass bg-surface-1 p-6">
          <div className="space-y-1">
            <p className="text-sm font-medium text-fg">
              Conectá Threads para usar acciones automáticas
            </p>
            <p className="text-xs text-fg-muted">
              No hay canales conectados con acciones disponibles en el catálogo.
            </p>
          </div>
          <Link
            href={`/accounts/${accountId}/publications`}
            className={buttonVariants({ variant: "primary", size: "md" })}
          >
            Ir al calendario para conectar canales
          </Link>
        </div>
      ) : (
        <>
          {isAdmin ? (
            <div className="rounded-xl border border-glass bg-surface-1 p-5">
              <Button type="button" onClick={() => openCreate()}>
                <Plus className="h-4 w-4" aria-hidden />
                Agregar plug
              </Button>
            </div>
          ) : null}

          <div className="space-y-4">
            {compatibleChannels.map((channel) => {
              const channelPlugs = plugsByChannel.get(channel.id) ?? [];
              const channelKinds = catalogByNetwork.get(channel.network) ?? [];
              const kindByKey = new Map(channelKinds.map((k) => [k.kind, k]));

              return (
                <section
                  key={channel.id}
                  aria-label={`Plugs de ${channelDisplayName(channel)}`}
                  className="overflow-hidden rounded-xl border border-glass bg-surface"
                >
                  <div className="flex flex-wrap items-center justify-between gap-3 border-b border-glass bg-surface-1 px-4 py-3">
                    <div className="flex items-center gap-3">
                      <ChannelAvatar channel={channel} size="md" />
                      <div>
                        <p className="text-sm font-medium text-fg">
                          {channelDisplayName(channel)}
                        </p>
                        <p className="text-xs text-fg-muted">
                          {networkLabel(channel.network)}
                        </p>
                      </div>
                    </div>
                  </div>

                  {channelPlugs.length === 0 ? (
                    <p className="p-6 text-center text-sm text-fg-muted">
                      No hay acciones automáticas configuradas en este canal.
                    </p>
                  ) : (
                    <ul className="divide-y divide-glass">
                      {channelPlugs.map((plug) => {
                        const kindMeta = kindByKey.get(plug.kind);
                        return (
                          <li key={plug.id} className="space-y-3 px-4 py-3.5">
                            <div className="flex flex-wrap items-start justify-between gap-3">
                              <div className="flex min-w-0 flex-1 items-start gap-3">
                                <span className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-focused text-lit">
                                  <Zap className="h-4 w-4" aria-hidden />
                                </span>
                                <div className="min-w-0 flex-1 space-y-1">
                                  <div className="flex flex-wrap items-center gap-2">
                                    <p className="text-sm font-medium text-fg">
                                      {kindMeta?.label ?? plug.kind}
                                    </p>
                                    <span
                                      className={cn(
                                        "rounded-sm border px-2 py-0.5 text-xs font-medium",
                                        plug.active
                                          ? "border-success bg-surface-2 text-success"
                                          : "border-glass bg-surface-2 text-fg-muted",
                                      )}
                                    >
                                      {plug.active ? "Activo" : "Pausado"}
                                    </span>
                                  </div>

                                  <p className="font-numeric text-xs tabular-nums text-fg-muted">
                                    Cuando llegue a {plug.likes_threshold} me
                                    gusta
                                  </p>

                                  {plug.message ? (
                                    <p className="whitespace-pre-wrap break-words rounded-md border border-glass bg-surface-2 px-3 py-2 text-xs text-fg">
                                      {plug.message}
                                    </p>
                                  ) : null}
                                </div>
                              </div>

                              {isAdmin ? (
                                <div className="flex shrink-0 items-center gap-1">
                                  <Button
                                    type="button"
                                    size="sm"
                                    variant="ghost"
                                    disabled={updateMutation.isPending}
                                    onClick={() => void handleToggleActive(plug)}
                                  >
                                    {plug.active ? "Pausar" : "Activar"}
                                  </Button>
                                  <button
                                    type="button"
                                    aria-label="Editar plug"
                                    title="Editar plug"
                                    onClick={() => openEdit(plug)}
                                    className="rounded-md p-1.5 text-fg-muted hover:bg-surface-2 hover:text-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                                  >
                                    <Pencil className="h-4 w-4" aria-hidden />
                                  </button>
                                  <button
                                    type="button"
                                    aria-label="Borrar plug"
                                    title="Borrar plug"
                                    disabled={deleteMutation.isPending}
                                    onClick={() => void handleDelete(plug)}
                                    className="rounded-md p-1.5 text-fg-muted hover:bg-surface-2 hover:text-danger disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                                  >
                                    <Trash2 className="h-4 w-4" aria-hidden />
                                  </button>
                                </div>
                              ) : null}
                            </div>

                            {plug.runs.length > 0 ? (
                              <div className="space-y-1.5 rounded-md border border-glass bg-surface-2 p-2.5">
                                <p className="text-[11px] font-medium uppercase tracking-wider text-fg-muted">
                                  Últimas corridas
                                </p>
                                <ul className="space-y-1">
                                  {plug.runs.map((run, idx) => {
                                    const ranAt = formatRunDate(run.ran_at);
                                    return (
                                      <li
                                        key={`${run.target_id}-${idx}`}
                                        className="flex flex-wrap items-center justify-between gap-2 text-xs"
                                      >
                                        <span className="inline-flex items-center gap-1.5">
                                          {run.ok ? (
                                            <span className="inline-flex items-center gap-1 font-medium text-success">
                                              <CheckCircle2
                                                className="h-3.5 w-3.5"
                                                aria-hidden
                                              />
                                              Bien
                                            </span>
                                          ) : (
                                            <span className="inline-flex items-center gap-1 font-medium text-danger">
                                              <XCircle
                                                className="h-3.5 w-3.5"
                                                aria-hidden
                                              />
                                              Falló
                                            </span>
                                          )}
                                          {!run.ok && run.error_message ? (
                                            <span className="text-danger">
                                              — {run.error_message}
                                            </span>
                                          ) : null}
                                        </span>
                                        {ranAt ? (
                                          <span className="font-numeric tabular-nums text-fg-muted">
                                            {ranAt}
                                          </span>
                                        ) : null}
                                      </li>
                                    );
                                  })}
                                </ul>
                              </div>
                            ) : null}
                          </li>
                        );
                      })}
                    </ul>
                  )}
                </section>
              );
            })}
          </div>
        </>
      )}

      {isAdmin ? (
        <dialog
          ref={dialogRef}
          onClose={closeDialog}
          aria-labelledby="plug-dialog-title"
          className="max-h-[92dvh] w-full max-w-lg overflow-y-auto rounded-panel border border-glass bg-surface p-0 text-fg shadow-menu backdrop:bg-backdrop backdrop:opacity-80"
        >
          <form onSubmit={(e) => void handleSubmit(e)} className="space-y-4 p-5">
            <div className="flex items-center justify-between border-b border-glass pb-3">
              <h3
                id="plug-dialog-title"
                className="text-lg font-medium text-fg"
              >
                {editing ? "Editar plug" : "Agregar plug"}
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
              <Label htmlFor="plug-channel" required>
                Canal
              </Label>
              <Select
                id="plug-channel"
                value={selectedChannelId !== null ? String(selectedChannelId) : ""}
                disabled={Boolean(editing)}
                onChange={(e) => handleChannelChange(Number(e.target.value))}
              >
                {compatibleChannels.map((ch) => (
                  <option key={ch.id} value={ch.id}>
                    {channelDisplayName(ch)} ({networkLabel(ch.network)})
                  </option>
                ))}
              </Select>
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="plug-kind" required>
                Acción
              </Label>
              <Select
                id="plug-kind"
                value={selectedKindKey}
                disabled={Boolean(editing)}
                onChange={(e) => handleKindChange(e.target.value)}
              >
                {availableKinds.map((kind) => (
                  <option key={kind.kind} value={kind.kind}>
                    {kind.label}
                  </option>
                ))}
              </Select>
              {selectedKind?.description ? (
                <p className="text-xs text-fg-muted">
                  {selectedKind.description}
                </p>
              ) : null}
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="plug-threshold" required>
                Cuando llegue a N me gusta
              </Label>
              <Input
                id="plug-threshold"
                type="number"
                min={1}
                step={1}
                value={likesThreshold}
                onChange={(e) => setLikesThreshold(e.target.value)}
              />
            </div>

            {requiresMessage && messageMax !== null ? (
              <div className="space-y-1.5">
                <div className="flex items-center justify-between gap-2">
                  <Label htmlFor="plug-message" required>
                    Mensaje
                  </Label>
                  <span
                    className={cn(
                      "font-numeric text-xs tabular-nums",
                      messageCount > messageMax
                        ? "text-danger"
                        : "text-fg-muted",
                    )}
                  >
                    {messageCount} / {messageMax}
                  </span>
                </div>
                <Textarea
                  id="plug-message"
                  rows={3}
                  value={message}
                  onChange={(e) => setMessage(e.target.value)}
                  placeholder="Escribí la respuesta automática…"
                  aria-invalid={messageCount > messageMax}
                />
              </div>
            ) : null}

            <label className="flex cursor-pointer items-center gap-2.5 text-sm text-fg">
              <input
                type="checkbox"
                checked={active}
                onChange={(e) => setActive(e.target.checked)}
                className="h-4 w-4 rounded border-glass bg-field accent-primary"
              />
              <span>Activo</span>
            </label>

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
                {editing ? "Guardar cambios" : "Guardar plug"}
              </Button>
            </div>
          </form>
        </dialog>
      ) : null}
    </div>
  );
}
