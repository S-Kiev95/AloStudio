"use client";

import {
  Globe,
  Instagram,
  type LucideIcon,
  Mail,
  MessageCircle,
  MessageSquare,
  Phone,
  Plus,
  Send,
  Webhook,
} from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { Button, buttonVariants } from "@/components/ui/button";
import {
  channelLabel,
  type Inbox,
  useDeleteInbox,
  useInboxes,
} from "@/lib/api/inboxes";
import { useIsAccountAdmin } from "@/lib/api/profile";
import { cn } from "@/lib/utils";

const CHANNEL_ICON: Record<string, LucideIcon> = {
  "Channel::Telegram": Send,
  "Channel::Whatsapp": MessageCircle,
  "Channel::Sms": MessageSquare,
  "Channel::TwilioSms": Phone,
  "Channel::Email": Mail,
  "Channel::WebWidget": Globe,
  "Channel::Api": Webhook,
  "Channel::Instagram": Instagram,
  "Channel::FacebookPage": MessageCircle,
};

export function InboxChannelsView({ accountId }: { accountId: string }) {
  const { data: inboxes, isLoading, isError } = useInboxes(accountId);
  // Connecting and disconnecting are admin-only: an agent would only get
  // the backend's denial.
  const isAdmin = useIsAccountAdmin(accountId);
  const newHref = `/accounts/${accountId}/settings/inboxes/new`;

  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-medium text-fg">Canales conectados</h2>
          <p className="text-sm text-fg-muted">
            Todos los canales conectados acá llegan a la misma bandeja.
          </p>
        </div>
        {isAdmin ? (
          <Link href={newHref} className={buttonVariants({ size: "sm" })}>
            <Plus className="h-4 w-4" aria-hidden />
            Conectar canal
          </Link>
        ) : null}
      </div>

      <div className="overflow-hidden rounded-md border border-glass bg-surface">
        {isLoading ? (
          <p className="p-8 text-center text-sm text-fg-muted">Cargando…</p>
        ) : isError ? (
          <p role="alert" className="p-8 text-center text-sm text-danger">
            No se pudieron cargar los canales.
          </p>
        ) : (inboxes?.length ?? 0) === 0 ? (
          <div className="p-8 text-center">
            <p className="text-sm text-fg-muted">
              No hay canales conectados todavía.
            </p>
            {isAdmin ? (
              <Link
                href={newHref}
                className={cn(buttonVariants({ size: "sm" }), "mt-3")}
              >
                <Plus className="h-4 w-4" aria-hidden />
                Conectar canal
              </Link>
            ) : null}
          </div>
        ) : (
          <ul className="divide-y divide-glass">
            {inboxes!.map((ix) => (
              <ChannelRow
                key={ix.id}
                accountId={accountId}
                inbox={ix}
                isAdmin={isAdmin}
              />
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

function ChannelRow({
  accountId,
  inbox,
  isAdmin,
}: {
  accountId: string;
  inbox: Inbox;
  isAdmin: boolean;
}) {
  const del = useDeleteInbox(accountId);
  const [error, setError] = useState<string | null>(null);
  const Icon = CHANNEL_ICON[inbox.channel_type] ?? Webhook;

  async function onDisconnect() {
    if (!window.confirm(`¿Desconectar el canal "${inbox.name}"?`)) return;
    setError(null);
    try {
      await del.mutateAsync(inbox.id);
    } catch (e) {
      setError(
        (e as { message?: string })?.message ?? "No se pudo desconectar.",
      );
    }
  }

  return (
    <li className="flex flex-wrap items-center gap-3 px-4 py-3 transition-colors hover:bg-hover-glass">
      <span className="grid h-9 w-9 shrink-0 place-items-center rounded-md bg-focused text-lit">
        <Icon className="h-4 w-4" aria-hidden />
      </span>
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium text-fg">{inbox.name}</p>
        <p className="text-xs text-fg-muted">
          {channelLabel(inbox.channel_type)}
        </p>
        {error ? (
          <p role="alert" className="mt-1 text-xs text-danger">
            {error}
          </p>
        ) : null}
      </div>
      <div className="flex shrink-0 items-center gap-2">
        <Link
          href={`/accounts/${accountId}/settings/inboxes/${inbox.id}`}
          className={buttonVariants({ variant: "secondary", size: "sm" })}
        >
          Detalles de conexión
        </Link>
        {isAdmin ? (
          <Button
            type="button"
            variant="ghost"
            size="sm"
            loading={del.isPending}
            onClick={onDisconnect}
            className="text-fg-muted hover:text-danger"
          >
            Desconectar
          </Button>
        ) : null}
      </div>
    </li>
  );
}
