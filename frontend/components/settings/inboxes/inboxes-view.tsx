"use client";

import {
  ChevronRight,
  Globe,
  type LucideIcon,
  Mail,
  MessageCircle,
  MessageSquare,
  Phone,
  Plus,
  Send,
  Trash2,
  Webhook,
} from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { buttonVariants } from "@/components/ui/button";
import {
  channelLabel,
  type Inbox,
  useDeleteInbox,
  useInboxes,
} from "@/lib/api/inboxes";
import { cn } from "@/lib/utils";

const CHANNEL_ICON: Record<string, LucideIcon> = {
  "Channel::Telegram": Send,
  "Channel::Whatsapp": MessageCircle,
  "Channel::Sms": MessageSquare,
  "Channel::TwilioSms": Phone,
  "Channel::Email": Mail,
  "Channel::WebWidget": Globe,
  "Channel::Api": Webhook,
};

export function InboxesView({ accountId }: { accountId: string }) {
  const { data: inboxes, isLoading, isError } = useInboxes(accountId);
  const newHref = `/accounts/${accountId}/settings/inboxes/new`;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-xl font-semibold text-fg">Bandejas de entrada</h2>
          <p className="text-sm text-fg-muted">Canales conectados a tu cuenta.</p>
        </div>
        <Link href={newHref} className={buttonVariants({ size: "sm" })}>
          <Plus className="h-4 w-4" aria-hidden />
          Agregar canal
        </Link>
      </div>

      <div className="overflow-hidden rounded-xl border border-border bg-surface shadow-sm">
        {isLoading ? (
          <p className="p-8 text-center text-sm text-fg-muted">Cargando…</p>
        ) : isError ? (
          <p role="alert" className="p-8 text-center text-sm text-danger">
            No se pudieron cargar las bandejas.
          </p>
        ) : (inboxes?.length ?? 0) === 0 ? (
          <div className="p-8 text-center">
            <p className="text-sm text-fg-muted">No hay canales todavía.</p>
            <Link
              href={newHref}
              className={cn(buttonVariants({ size: "sm" }), "mt-3")}
            >
              <Plus className="h-4 w-4" aria-hidden />
              Agregar el primero
            </Link>
          </div>
        ) : (
          <ul className="divide-y divide-border">
            {inboxes!.map((ix) => (
              <InboxRow key={ix.id} accountId={accountId} inbox={ix} />
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

function InboxRow({
  accountId,
  inbox,
}: {
  accountId: string;
  inbox: Inbox;
}) {
  const del = useDeleteInbox(accountId);
  const [error, setError] = useState<string | null>(null);
  const Icon = CHANNEL_ICON[inbox.channel_type] ?? Webhook;

  async function onDelete() {
    if (!window.confirm(`¿Eliminar la bandeja "${inbox.name}"?`)) return;
    setError(null);
    try {
      await del.mutateAsync(inbox.id);
    } catch (e) {
      setError((e as { message?: string })?.message ?? "No se pudo eliminar.");
    }
  }

  return (
    <li className="flex items-center gap-1 pr-2 hover:bg-surface-2">
      <Link
        href={`/accounts/${accountId}/settings/inboxes/${inbox.id}`}
        className="flex min-w-0 flex-1 items-center gap-3 px-4 py-3 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring"
      >
        <span className="grid h-9 w-9 shrink-0 place-items-center rounded-md bg-primary/10 text-primary">
          <Icon className="h-4 w-4" aria-hidden />
        </span>
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium text-fg">{inbox.name}</p>
          <p className="text-xs text-fg-muted">
            {channelLabel(inbox.channel_type)}
          </p>
          {error ? (
            <p role="alert" className="text-xs text-danger">
              {error}
            </p>
          ) : null}
        </div>
      </Link>
      <button
        type="button"
        aria-label="Eliminar"
        title="Eliminar"
        onClick={onDelete}
        disabled={del.isPending}
        className="rounded-md p-1.5 text-fg-muted hover:bg-surface-2 hover:text-danger disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <Trash2 className="h-4 w-4" aria-hidden />
      </button>
      <ChevronRight className="h-4 w-4 shrink-0 text-fg-muted" aria-hidden />
    </li>
  );
}
