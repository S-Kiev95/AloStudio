"use client";

import {
  AlertTriangle,
  ChevronLeft,
  ChevronRight,
  Facebook,
  Instagram,
  Plus,
  RefreshCw,
  Trash2,
  X,
} from "lucide-react";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  type Channel,
  type NetworkOption,
  type ParsedPublicationError,
  parsePublicationError,
  useAuthorizeChannel,
  useConnectFormChannel,
  useDeleteChannel,
  usePublicationNetworks,
} from "@/lib/api/publications";
import { cn } from "@/lib/utils";

import { ChannelAvatar, channelDisplayName, NetworkIcon } from "./network-icon";
import { PublicationErrorAlert } from "./publication-error-alert";

export function ChannelsPanel({
  accountId,
  channels,
  isLoading,
  isAdmin,
  selectedChannelId,
  onSelectChannel,
}: {
  accountId: string;
  channels: Channel[];
  isLoading?: boolean;
  isAdmin: boolean;
  selectedChannelId: number | undefined;
  onSelectChannel: (channelId: number | undefined) => void;
}) {
  const [collapsed, setCollapsed] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const [panelError, setPanelError] = useState<ParsedPublicationError | null>(
    null,
  );
  const [formNetwork, setFormNetwork] = useState<NetworkOption | null>(null);

  const networksQuery = usePublicationNetworks(accountId, isAdmin);
  const authorizeMutation = useAuthorizeChannel(accountId);
  const deleteChannelMutation = useDeleteChannel(accountId);

  const networks = networksQuery.data ?? [];

  async function startAuthorize(network: string) {
    setPanelError(null);
    setMenuOpen(false);
    try {
      const { authorize_url } = await authorizeMutation.mutateAsync(network);
      window.location.href = authorize_url;
    } catch (err) {
      setPanelError(
        parsePublicationError(err, "No se pudo iniciar la conexión."),
      );
    }
  }

  function handlePickNetwork(opt: NetworkOption) {
    if (!opt.configured) return;
    setMenuOpen(false);
    if (opt.kind === "form") {
      setFormNetwork(opt);
      return;
    }
    void startAuthorize(opt.network);
  }

  function handleReconnect(channel: Channel) {
    const matching = networks.find((n) => n.network === channel.network);
    if (matching && matching.configured) {
      if (matching.kind === "form") {
        setFormNetwork(matching);
      } else {
        void startAuthorize(matching.network);
      }
      return;
    }
    window.location.href = `/accounts/${accountId}/settings/inboxes`;
  }

  async function handleRemoveChannel(channel: Channel) {
    const name = channelDisplayName(channel);
    if (!window.confirm(`¿Quitar el canal "${name}"?`)) return;
    setPanelError(null);
    try {
      await deleteChannelMutation.mutateAsync(channel.id);
      if (selectedChannelId === channel.id) {
        onSelectChannel(undefined);
      }
    } catch (err) {
      setPanelError(parsePublicationError(err, "No se pudo quitar el canal."));
    }
  }

  if (collapsed) {
    return (
      <aside
        aria-label="Canales"
        className="hidden lg:flex lg:w-12 lg:shrink-0 lg:flex-col lg:items-center lg:rounded-md lg:border lg:border-glass lg:bg-surface lg:py-3"
      >
        <button
          type="button"
          aria-label="Expandir panel de canales"
          title="Mostrar canales"
          onClick={() => setCollapsed(false)}
          className="inline-flex h-9 w-9 items-center justify-center rounded-md text-fg-muted hover:bg-hover-glass hover:text-fg focus-visible:outline focus-visible:outline-2 focus-visible:outline-neon"
        >
          <ChevronLeft className="h-4 w-4" aria-hidden />
        </button>
      </aside>
    );
  }

  const addChannelControl = isAdmin ? (
    <div className="relative">
      <Button
        type="button"
        variant="simple"
        size="sm"
        className="w-full justify-center"
        aria-expanded={menuOpen}
        aria-haspopup="menu"
        loading={authorizeMutation.isPending}
        onClick={() => setMenuOpen((o) => !o)}
      >
        <Plus className="h-4 w-4" aria-hidden />
        Agregar canal
      </Button>

      {menuOpen ? (
        <div
          role="menu"
          aria-label="Redes para conectar"
          className="absolute left-0 right-0 z-30 mt-1.5 overflow-hidden rounded-md border border-glass bg-surface-2 py-1 text-left shadow-menu"
        >
          {networks.map((opt) => (
            <button
              key={opt.network}
              type="button"
              role="menuitem"
              disabled={!opt.configured}
              onClick={() => handlePickNetwork(opt)}
              className={cn(
                "flex w-full flex-col items-start gap-0.5 px-3 py-2 text-left text-sm transition-colors",
                opt.configured
                  ? "text-fg hover:bg-hover-glass"
                  : "cursor-not-allowed opacity-55",
              )}
            >
              <span className="flex items-center gap-2 font-medium">
                <NetworkIcon network={opt.network} />
                {opt.label}
              </span>
              {!opt.configured ? (
                <span className="text-[11px] text-fg-muted">
                  Falta configurar en Ajustes → Instalación
                </span>
              ) : null}
            </button>
          ))}

          <Link
            href={`/accounts/${accountId}/settings/inboxes`}
            role="menuitem"
            onClick={() => setMenuOpen(false)}
            className="flex w-full flex-col items-start gap-0.5 border-t border-glass px-3 py-2 text-sm text-fg transition-colors hover:bg-hover-glass"
          >
            <span className="flex items-center gap-2 font-medium">
              <Instagram className="h-3.5 w-3.5 text-[#E1306C]" aria-hidden />
              Instagram o página de Facebook
            </span>
            <span className="text-[11px] text-fg-muted">
              Ajustes → Bandejas de entrada
            </span>
          </Link>
        </div>
      ) : null}
    </div>
  ) : null;

  return (
    <aside
      aria-label="Canales"
      className="flex w-full flex-col gap-3 rounded-md border border-glass bg-surface p-4 lg:w-72 lg:shrink-0"
    >
      <div className="flex items-center justify-between gap-2">
        <h2 className="text-base font-medium text-fg">Canales</h2>
        <button
          type="button"
          aria-label="Contraer panel de canales"
          title="Contraer panel"
          onClick={() => setCollapsed(true)}
          className="hidden h-8 w-8 items-center justify-center rounded-md text-fg-muted hover:bg-hover-glass hover:text-fg focus-visible:outline focus-visible:outline-2 focus-visible:outline-neon lg:inline-flex"
        >
          <ChevronRight className="h-4 w-4" aria-hidden />
        </button>
      </div>

      {channels.length > 0 ? addChannelControl : null}

      <PublicationErrorAlert
        error={panelError}
        onDismiss={() => setPanelError(null)}
      />

      {selectedChannelId !== undefined ? (
        <div className="flex items-center justify-between rounded-sm bg-focused px-2.5 py-1 text-xs text-lit">
          <span>Filtrando por canal</span>
          <button
            type="button"
            onClick={() => onSelectChannel(undefined)}
            className="font-medium underline hover:no-underline"
          >
            Ver todos
          </button>
        </div>
      ) : null}

      {isLoading ? (
        <p className="py-8 text-center text-xs text-fg-muted">
          Cargando canales…
        </p>
      ) : channels.length === 0 ? (
        <div className="flex flex-1 flex-col items-center justify-center py-8 text-center">
          <div className="mb-4 flex items-center justify-center">
            <span className="-mr-2 -rotate-6 grid h-11 w-11 place-items-center rounded-control border border-glass bg-surface-2 text-[#1877F2]">
              <Facebook className="h-5 w-5" aria-hidden />
            </span>
            <span className="z-10 grid h-14 w-14 place-items-center rounded-panel border border-glass bg-surface-2 text-[#E1306C]">
              <Instagram className="h-6 w-6" aria-hidden />
            </span>
          </div>
          <p className="text-sm font-medium text-fg">Todavía no hay canales</p>
          <p className="mt-1 text-xs text-fg-muted">
            Conectá tus cuentas sociales para programar, publicar y medir tus
            contenidos en un solo lugar.
          </p>
          {addChannelControl ? (
            <div className="mt-4 w-full">{addChannelControl}</div>
          ) : null}
        </div>
      ) : (
        <ul className="space-y-2">
          {channels.map((ch) => {
            const name = channelDisplayName(ch);
            const selected = selectedChannelId === ch.id;
            const needsReconnect = ch.status === "reconnect";

            return (
              <li
                key={ch.id}
                className={cn(
                  "rounded-md border p-2.5 transition-colors",
                  selected
                    ? "border-neon bg-focused text-lit"
                    : "border-glass bg-surface-2",
                )}
              >
                <div className="flex items-center gap-2.5">
                  <button
                    type="button"
                    aria-pressed={selected}
                    onClick={() =>
                      onSelectChannel(selected ? undefined : ch.id)
                    }
                    className="flex min-w-0 flex-1 items-center gap-2.5 text-left focus-visible:outline focus-visible:outline-2 focus-visible:outline-neon"
                  >
                    <ChannelAvatar channel={ch} size="sm" />
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium text-fg">
                        {name}
                      </p>
                      {ch.username && name !== `@${ch.username}` ? (
                        <p className="truncate text-xs text-fg-muted">
                          @{ch.username}
                        </p>
                      ) : null}
                    </div>
                  </button>

                  {isAdmin && ch.inbox_id === null ? (
                    <button
                      type="button"
                      aria-label={`Quitar ${name}`}
                      title="Quitar canal"
                      disabled={deleteChannelMutation.isPending}
                      onClick={() => void handleRemoveChannel(ch)}
                      className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-md text-fg-muted hover:bg-hover-glass hover:text-danger disabled:opacity-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-neon"
                    >
                      <Trash2 className="h-3.5 w-3.5" aria-hidden />
                    </button>
                  ) : null}
                </div>

                {needsReconnect ? (
                  <div className="mt-2 space-y-1.5 rounded-sm border border-warning/30 bg-warning/10 p-2 text-xs">
                    <div className="flex items-center gap-1.5 font-medium text-warning">
                      <AlertTriangle className="h-3.5 w-3.5 shrink-0" aria-hidden />
                      <span>Requiere reconexión</span>
                    </div>
                    {ch.status_message ? (
                      <p className="text-fg-muted">{ch.status_message}</p>
                    ) : null}
                    {isAdmin ? (
                      ch.inbox_id !== null &&
                      !networks.some((n) => n.network === ch.network) ? (
                        <Link
                          href={`/accounts/${accountId}/settings/inboxes`}
                          className="inline-flex items-center gap-1 font-medium text-lit underline hover:no-underline"
                        >
                          <RefreshCw className="h-3 w-3" aria-hidden />
                          Volver a conectar
                        </Link>
                      ) : (
                        <button
                          type="button"
                          onClick={() => handleReconnect(ch)}
                          className="inline-flex items-center gap-1 font-medium text-lit underline hover:no-underline"
                        >
                          <RefreshCw className="h-3 w-3" aria-hidden />
                          Volver a conectar
                        </button>
                      )
                    ) : null}
                  </div>
                ) : null}
              </li>
            );
          })}
        </ul>
      )}

      <ConnectFormDialog
        accountId={accountId}
        networkOption={formNetwork}
        onClose={() => setFormNetwork(null)}
      />
    </aside>
  );
}

function ConnectFormDialog({
  accountId,
  networkOption,
  onClose,
}: {
  accountId: string;
  networkOption: NetworkOption | null;
  onClose: () => void;
}) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const [values, setValues] = useState<Record<string, string>>({});
  const [error, setError] = useState<ParsedPublicationError | null>(null);
  const connectMutation = useConnectFormChannel(accountId);

  const open = networkOption !== null;

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
    if (!networkOption) return;
    setError(null);
    const initial: Record<string, string> = {};
    for (const f of networkOption.fields) {
      initial[f.name] = "";
    }
    setValues(initial);
  }, [networkOption]);

  if (!networkOption) return null;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!networkOption) return;
    setError(null);

    for (const f of networkOption.fields) {
      if (!values[f.name]?.trim()) {
        setError({
          message: `El campo "${f.label}" es obligatorio.`,
          errors: [],
        });
        return;
      }
    }

    const trimmedFields: Record<string, string> = {};
    for (const f of networkOption.fields) {
      trimmedFields[f.name] = values[f.name].trim();
    }

    try {
      await connectMutation.mutateAsync({
        network: networkOption.network,
        fields: trimmedFields,
      });
      onClose();
    } catch (err) {
      setError(parsePublicationError(err, "No se pudo conectar el canal."));
    }
  }

  return (
    <dialog
      ref={dialogRef}
      onClose={onClose}
      aria-labelledby="connect-network-dialog-title"
      className="w-full max-w-md rounded-panel border border-glass bg-surface p-0 text-fg shadow-menu backdrop:bg-backdrop/75"
    >
      <form onSubmit={handleSubmit} className="space-y-4 p-5">
        <div className="flex items-start justify-between gap-3">
          <h2
            id="connect-network-dialog-title"
            className="flex items-center gap-2 text-lg font-medium text-fg"
          >
            <NetworkIcon network={networkOption.network} />
            Conectar {networkOption.label}
          </h2>
          <button
            type="button"
            aria-label="Cerrar diálogo"
            onClick={onClose}
            className="inline-flex h-9 w-9 items-center justify-center rounded-md text-fg-muted hover:bg-hover-glass focus-visible:outline focus-visible:outline-2 focus-visible:outline-neon"
          >
            <X className="h-4 w-4" aria-hidden />
          </button>
        </div>

        <PublicationErrorAlert error={error} />

        {networkOption.fields.map((field) => {
          const inputId = `connect-field-${field.name}`;
          return (
            <div key={field.name} className="space-y-1.5">
              <Label htmlFor={inputId} required>
                {field.label}
              </Label>
              <Input
                id={inputId}
                type={field.secret ? "password" : "text"}
                value={values[field.name] ?? ""}
                onChange={(e) =>
                  setValues((prev) => ({
                    ...prev,
                    [field.name]: e.target.value,
                  }))
                }
              />
              {field.help ? (
                <p className="text-xs text-fg-muted">{field.help}</p>
              ) : null}
            </div>
          );
        })}

        <div className="flex justify-end gap-2 pt-2">
          <Button
            type="button"
            variant="ghost"
            onClick={onClose}
            disabled={connectMutation.isPending}
          >
            Cancelar
          </Button>
          <Button type="submit" loading={connectMutation.isPending}>
            Conectar
          </Button>
        </div>
      </form>
    </dialog>
  );
}
