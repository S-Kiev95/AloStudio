"use client";

import { Inbox } from "lucide-react";

import { useContactableInboxes } from "@/lib/api/contacts";

export function ContactableInboxesPanel({
  accountId,
  contactId,
}: {
  accountId: string;
  contactId: number;
}) {
  const { data, isLoading, isError } = useContactableInboxes(
    accountId,
    contactId,
  );

  if (isLoading) {
    return <p className="text-sm text-fg-muted">Cargando bandejas…</p>;
  }
  if (isError) {
    return (
      <p role="alert" className="text-sm text-danger">
        No se pudieron cargar las bandejas disponibles.
      </p>
    );
  }
  if (!data || data.length === 0) {
    return (
      <div className="space-y-2">
        <p className="text-sm text-fg-muted">
          Este contacto todavía no está asociado a ninguna bandeja.
        </p>
        <p className="text-xs text-fg-muted">
          En esta entrega solo soportamos bandejas de tipo API; los demás
          canales se habilitan a medida que se portan en el backend.
        </p>
      </div>
    );
  }

  return (
    <ul className="space-y-2">
      {data.map((ci) => (
        <li
          key={`${ci.inbox.id}-${ci.source_id}`}
          className="flex items-center gap-3 rounded-lg border border-border bg-surface p-3"
        >
          <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary">
            <Inbox className="h-4 w-4" aria-hidden />
          </span>
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-medium text-fg">
              {ci.inbox.name}
            </p>
            <p className="truncate text-xs text-fg-muted">
              {ci.inbox.channel_type} · source_id{" "}
              <code className="font-mono text-[11px]">{ci.source_id}</code>
            </p>
          </div>
        </li>
      ))}
    </ul>
  );
}
