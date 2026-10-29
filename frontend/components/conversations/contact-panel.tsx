"use client";

import {
  ChevronRight,
  ExternalLink,
  MessageSquare,
} from "lucide-react";
import Link from "next/link";

import { Avatar } from "@/components/ui/avatar";
import { useContact, useContactNotes } from "@/lib/api/contacts";
import { useConversations } from "@/lib/api/conversations";
import { useCustomAttributes } from "@/lib/api/custom-attributes";
import { relativeTime } from "@/lib/time";
import { cn } from "@/lib/utils";

const STATUS_BADGE: Record<string, { label: string; className: string }> = {
  open: {
    label: "Abierta",
    className: "border border-success bg-surface-2 text-success",
  },
  pending: {
    label: "Pendiente",
    className: "border border-warning bg-surface-2 text-warning",
  },
  resolved: {
    label: "Resuelta",
    className: "border border-glass bg-surface-2 text-fg-muted",
  },
  snoozed: {
    label: "Pospuesta",
    className: "border border-glass bg-surface-2 text-fg-muted",
  },
};

/**
 * The right-hand panel (~280 px) inside the three-column inbox: surfaces who
 * the conversation is with — large avatar, name, status, email, phone, custom
 * attributes, recent notes, and other open conversations. Read-only here; the
 * full edit surface lives at `/contacts/[id]`.
 */
export function ContactPanel({
  accountId,
  contactId,
  currentDisplayId,
  conversationStatus,
}: {
  accountId: string;
  contactId: number | null | undefined;
  currentDisplayId: number;
  conversationStatus?: string;
}) {
  const enabled = typeof contactId === "number" && Number.isFinite(contactId);
  const contact = useContact(accountId, contactId ?? -1);
  const notes = useContactNotes(accountId, contactId ?? -1);
  const attrs = useCustomAttributes(accountId, "contact_attribute");

  if (!enabled) {
    return (
      <aside className="hidden lg:block lg:w-[280px] lg:shrink-0 lg:border-l lg:border-glass lg:p-4">
        <p className="text-sm text-fg-muted">
          Sin contacto asociado a esta conversación.
        </p>
      </aside>
    );
  }

  if (contact.isLoading) {
    return (
      <aside className="hidden lg:block lg:w-[280px] lg:shrink-0 lg:border-l lg:border-glass lg:p-4">
        <p className="text-sm text-fg-muted">Cargando contacto…</p>
      </aside>
    );
  }

  if (contact.isError || !contact.data) {
    return (
      <aside className="hidden lg:block lg:w-[280px] lg:shrink-0 lg:border-l lg:border-glass lg:p-4">
        <p role="alert" className="text-sm text-danger">
          No se pudo cargar el contacto.
        </p>
      </aside>
    );
  }

  const c = contact.data;
  const displayName =
    c.name?.trim() ||
    c.email?.trim() ||
    c.phone_number?.trim() ||
    `Contacto #${c.id}`;

  const statusMeta = conversationStatus
    ? STATUS_BADGE[conversationStatus]
    : undefined;

  const customMap = c.custom_attributes ?? {};
  const attrNameByKey = new Map(
    (attrs.data ?? []).map((a) => [a.attribute_key, a.attribute_display_name]),
  );
  const customEntries = Object.entries(customMap).map(([key, val]) => ({
    key,
    label: attrNameByKey.get(key) ?? key,
    value: formatCustom(val),
  }));

  return (
    <aside
      aria-label="Contacto"
      className={cn(
        "hidden shrink-0 overflow-y-auto p-4",
        "lg:block lg:w-[280px] lg:border-l lg:border-glass",
      )}
    >
      <div className="space-y-5 pb-4">
        {/* Identity */}
        <div className="flex flex-col items-center text-center">
          <Avatar name={displayName} size="xl" />
          <p className="mt-3 max-w-full truncate text-base font-semibold text-fg">
            {displayName}
          </p>
          <div className="mt-1.5 flex flex-wrap items-center justify-center gap-1.5">
            {statusMeta ? (
              <span
                className={cn(
                  "rounded-pill px-2.5 py-0.5 text-xs font-medium",
                  statusMeta.className,
                )}
              >
                {statusMeta.label}
              </span>
            ) : null}
            {c.blocked ? (
              <span className="rounded-pill border border-danger bg-surface-2 px-2 py-0.5 text-[10px] font-medium uppercase text-danger">
                Bloqueado
              </span>
            ) : null}
          </div>
          <Link
            href={`/accounts/${accountId}/contacts/${c.id}`}
            className="mt-2 inline-flex items-center gap-1 text-xs text-info hover:underline"
          >
            Ver perfil completo
            <ExternalLink className="h-3 w-3" aria-hidden />
          </Link>
        </div>

        {/* Contact methods */}
        <div className="space-y-3 border-t border-glass pt-4 text-sm">
          <div>
            <p className="text-[11px] font-medium uppercase tracking-wide text-fg-muted">
              Email
            </p>
            {c.email ? (
              <a
                href={`mailto:${c.email}`}
                className="mt-0.5 block truncate text-fg hover:text-lit hover:underline"
              >
                {c.email}
              </a>
            ) : (
              <p className="mt-0.5 text-fg-muted">—</p>
            )}
          </div>
          <div>
            <p className="text-[11px] font-medium uppercase tracking-wide text-fg-muted">
              Teléfono
            </p>
            <p className="mt-0.5 truncate font-numeric tabular-nums text-fg">
              {c.phone_number || "—"}
            </p>
          </div>
        </div>

        {/* Custom attributes */}
        {customEntries.length > 0 ? (
          <div className="border-t border-glass pt-4">
            <h3 className="mb-2 text-[11px] font-medium uppercase tracking-wide text-fg-muted">
              Atributos personalizados
            </h3>
            <dl className="space-y-2 text-xs">
              {customEntries.map((entry) => (
                <div key={entry.key}>
                  <dt className="text-fg-muted">{entry.label}</dt>
                  <dd className="mt-0.5 break-words font-medium text-fg">
                    {entry.value}
                  </dd>
                </div>
              ))}
            </dl>
          </div>
        ) : null}

        {/* Recent notes */}
        <div className="border-t border-glass pt-4">
          <h3 className="mb-1.5 text-[11px] font-medium uppercase tracking-wide text-fg-muted">
            Notas recientes
          </h3>
          {notes.isLoading ? (
            <p className="text-xs text-fg-muted">Cargando…</p>
          ) : !notes.data?.length ? (
            <p className="text-xs text-fg-muted">Sin notas.</p>
          ) : (
            <ul className="space-y-1.5">
              {notes.data.slice(0, 3).map((n) => (
                <li
                  key={n.id}
                  className="rounded-md border border-glass bg-surface-2 p-2 text-xs"
                >
                  <p className="line-clamp-3 text-fg">{n.content}</p>
                  <p className="mt-0.5 text-fg-muted">
                    {n.user?.name ?? "Sistema"}
                    {n.created_at ? ` · ${relativeTime(n.created_at)}` : ""}
                  </p>
                </li>
              ))}
            </ul>
          )}
        </div>

        {/* Other open conversations */}
        <OtherConversations
          accountId={accountId}
          contactId={c.id}
          currentDisplayId={currentDisplayId}
        />
      </div>
    </aside>
  );
}

function OtherConversations({
  accountId,
  contactId,
  currentDisplayId,
}: {
  accountId: string;
  contactId: number;
  currentDisplayId: number;
}) {
  // Best-effort: the conversation list endpoint takes no contact filter
  // in the current backend port, so we fetch the open page and filter
  // client-side. Good enough for the common case (a few open convos per
  // contact); paginate-and-search lands when the backend exposes a
  // contact_id filter or we wire ``GET /contacts/:id/conversations``.
  const list = useConversations(accountId, { status: "open" });
  const all = list.data?.data?.payload ?? [];
  const others = all.filter(
    (c) =>
      c.meta?.sender?.id === contactId && c.id !== currentDisplayId,
  );

  if (others.length === 0) return null;

  return (
    <div className="border-t border-glass pt-4">
      <h3 className="mb-1.5 text-[11px] font-medium uppercase tracking-wide text-fg-muted">
        Otras conversaciones
      </h3>
      <ul className="divide-y divide-glass rounded-md border border-glass bg-surface-2">
        {others.slice(0, 5).map((c) => (
          <li key={c.id}>
            <Link
              href={`/accounts/${accountId}/conversations/${c.id}`}
              className="flex items-center gap-2 px-2 py-1.5 text-xs hover:bg-hover-glass focus-visible:outline focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-neon"
            >
              <MessageSquare
                className="h-3 w-3 shrink-0 text-fg-muted"
                aria-hidden
              />
              <span className="min-w-0 flex-1 truncate font-numeric text-fg">
                #{c.id}
              </span>
              <span className="shrink-0 text-fg-muted">{c.status}</span>
              <ChevronRight className="h-3 w-3 text-fg-muted" aria-hidden />
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}

function formatCustom(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "boolean") return value ? "Sí" : "No";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}
