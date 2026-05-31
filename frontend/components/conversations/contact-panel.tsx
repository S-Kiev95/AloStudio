"use client";

import {
  ChevronRight,
  ExternalLink,
  Mail,
  MessageSquare,
  Phone,
  User as UserIcon,
} from "lucide-react";
import Link from "next/link";

import { useContact, useContactNotes } from "@/lib/api/contacts";
import { useConversations } from "@/lib/api/conversations";
import { useCustomAttributes } from "@/lib/api/custom-attributes";
import { relativeTime } from "@/lib/time";
import { cn } from "@/lib/utils";

/**
 * The right-hand panel inside the conversation view: surfaces who the
 * conversation is with — contact identity, custom attributes, recent
 * notes, and the rest of their open conversations. Read-only here;
 * the full edit surface lives at /contacts/[id].
 */
export function ContactPanel({
  accountId,
  contactId,
  currentDisplayId,
}: {
  accountId: string;
  contactId: number | null | undefined;
  currentDisplayId: number;
}) {
  const enabled = typeof contactId === "number" && Number.isFinite(contactId);
  const contact = useContact(accountId, contactId ?? -1);
  const notes = useContactNotes(accountId, contactId ?? -1);
  const attrs = useCustomAttributes(accountId, "contact_attribute");

  if (!enabled) {
    return (
      <aside className="hidden lg:block lg:w-72 lg:shrink-0 lg:border-l lg:border-border lg:pl-4 lg:pt-4">
        <p className="text-sm text-fg-muted">
          Sin contacto asociado a esta conversación.
        </p>
      </aside>
    );
  }

  if (contact.isLoading) {
    return (
      <aside className="hidden lg:block lg:w-72 lg:shrink-0 lg:border-l lg:border-border lg:pl-4 lg:pt-4">
        <p className="text-sm text-fg-muted">Cargando contacto…</p>
      </aside>
    );
  }

  if (contact.isError || !contact.data) {
    return (
      <aside className="hidden lg:block lg:w-72 lg:shrink-0 lg:border-l lg:border-border lg:pl-4 lg:pt-4">
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

  return (
    <aside
      aria-label="Contacto"
      className={cn(
        "hidden shrink-0 overflow-y-auto pt-4",
        "lg:block lg:w-72 lg:border-l lg:border-border lg:pl-4",
      )}
    >
      <div className="space-y-4 pb-6">
        {/* Identity */}
        <div className="flex items-center gap-3">
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary">
            <UserIcon className="h-5 w-5" aria-hidden />
          </span>
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-semibold text-fg">
              {displayName}
              {c.blocked ? (
                <span className="ml-2 rounded bg-danger/10 px-1.5 py-0.5 text-[10px] font-medium uppercase text-danger">
                  Bloqueado
                </span>
              ) : null}
            </p>
            <Link
              href={`/accounts/${accountId}/contacts/${c.id}`}
              className="inline-flex items-center gap-1 text-xs text-info hover:underline"
            >
              Ver perfil completo
              <ExternalLink className="h-3 w-3" aria-hidden />
            </Link>
          </div>
        </div>

        {/* Contact methods */}
        <ul className="space-y-1.5 text-sm text-fg">
          {c.email ? (
            <li className="flex items-center gap-2">
              <Mail className="h-3.5 w-3.5 shrink-0 text-fg-muted" aria-hidden />
              <a
                href={`mailto:${c.email}`}
                className="truncate text-info hover:underline"
              >
                {c.email}
              </a>
            </li>
          ) : null}
          {c.phone_number ? (
            <li className="flex items-center gap-2">
              <Phone className="h-3.5 w-3.5 shrink-0 text-fg-muted" aria-hidden />
              <span className="truncate">{c.phone_number}</span>
            </li>
          ) : null}
        </ul>

        {/* Custom attributes */}
        {attrs.data?.length && Object.keys(c.custom_attributes).length > 0 ? (
          <div>
            <h3 className="mb-1 text-xs font-medium uppercase tracking-wide text-fg-muted">
              Atributos personalizados
            </h3>
            <dl className="space-y-1 text-sm">
              {attrs.data
                .filter((a) =>
                  Object.prototype.hasOwnProperty.call(
                    c.custom_attributes,
                    a.attribute_key,
                  ),
                )
                .map((a) => (
                  <div key={a.id} className="flex justify-between gap-2">
                    <dt className="shrink-0 text-fg-muted">
                      {a.attribute_display_name}
                    </dt>
                    <dd className="min-w-0 truncate text-fg">
                      {formatCustom(
                        c.custom_attributes[a.attribute_key],
                      )}
                    </dd>
                  </div>
                ))}
            </dl>
          </div>
        ) : null}

        {/* Recent notes */}
        <div>
          <h3 className="mb-1 text-xs font-medium uppercase tracking-wide text-fg-muted">
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
                  className="rounded-md border border-border bg-surface p-2 text-xs"
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
    <div>
      <h3 className="mb-1 text-xs font-medium uppercase tracking-wide text-fg-muted">
        Otras conversaciones
      </h3>
      <ul className="divide-y divide-border rounded-md border border-border bg-surface">
        {others.slice(0, 5).map((c) => (
          <li key={c.id}>
            <Link
              href={`/accounts/${accountId}/conversations/${c.id}`}
              className="flex items-center gap-2 px-2 py-1.5 text-xs hover:bg-surface-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring"
            >
              <MessageSquare
                className="h-3 w-3 shrink-0 text-fg-muted"
                aria-hidden
              />
              <span className="min-w-0 flex-1 truncate text-fg">
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
