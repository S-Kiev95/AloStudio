"use client";

import {
  ChevronLeft,
  ChevronRight,
  Mail,
  Phone,
  Plus,
  Search,
  Trash2,
  User as UserIcon,
} from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { buttonVariants } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  type Contact,
  useContacts,
  useDeleteContact,
  useSearchContacts,
} from "@/lib/api/contacts";
import { cn } from "@/lib/utils";

const PAGE_SIZE = 15; // mirrors backend RESULTS_PER_PAGE

export function ContactsView({ accountId }: { accountId: string }) {
  const [page, setPage] = useState(1);
  const [q, setQ] = useState("");

  const trimmed = q.trim();
  const searching = trimmed.length > 0;

  // Either index or search; only one is enabled at a time.
  const indexQ = useContacts(accountId, page);
  const searchQ = useSearchContacts(accountId, trimmed, page);
  const active = searching ? searchQ : indexQ;

  const data = active.data;
  const items: Contact[] = data?.payload ?? [];
  const total = data?.meta?.count ?? 0;

  const hasMore = searching
    ? Boolean((data as { meta?: { has_more?: boolean } })?.meta?.has_more)
    : page * PAGE_SIZE < total;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div className="mx-auto max-w-4xl space-y-4 p-4 md:p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-xl font-semibold text-fg">Contactos</h2>
        <Link
          href={`/accounts/${accountId}/contacts/new`}
          className={buttonVariants({ size: "sm" })}
        >
          <Plus className="h-4 w-4" aria-hidden />
          Nuevo contacto
        </Link>
      </div>

      <div className="relative">
        <Search
          className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-fg-muted"
          aria-hidden
        />
        <Input
          aria-label="Buscar contactos"
          value={q}
          onChange={(e) => {
            setQ(e.target.value);
            setPage(1);
          }}
          placeholder="Buscar por nombre, email, teléfono o identificador…"
          className="pl-9"
        />
      </div>

      <div className="overflow-hidden rounded-lg border border-border bg-surface">
        {active.isLoading ? (
          <p className="p-8 text-center text-sm text-fg-muted">Cargando…</p>
        ) : active.isError ? (
          <p role="alert" className="p-8 text-center text-sm text-danger">
            No se pudieron cargar los contactos.
          </p>
        ) : items.length === 0 ? (
          <p className="p-8 text-center text-sm text-fg-muted">
            {searching
              ? `No hay resultados para "${trimmed}".`
              : "No hay contactos todavía."}
          </p>
        ) : (
          <ul className="divide-y divide-border">
            {items.map((c) => (
              <ContactRow key={c.id} accountId={accountId} contact={c} />
            ))}
          </ul>
        )}
      </div>

      {/* Pagination */}
      {items.length > 0 ? (
        <div className="flex items-center justify-between text-sm text-fg-muted">
          <span>
            {searching
              ? `Página ${page}`
              : `Página ${page} de ${totalPages} · ${total} contacto${total === 1 ? "" : "s"}`}
          </span>
          <div className="flex gap-1">
            <button
              type="button"
              aria-label="Página anterior"
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page === 1 || active.isFetching}
              className={cn(
                "rounded-md border border-border bg-surface p-1.5 text-fg-muted hover:bg-surface-2 disabled:opacity-50",
              )}
            >
              <ChevronLeft className="h-4 w-4" aria-hidden />
            </button>
            <button
              type="button"
              aria-label="Página siguiente"
              onClick={() => setPage((p) => p + 1)}
              disabled={!hasMore || active.isFetching}
              className={cn(
                "rounded-md border border-border bg-surface p-1.5 text-fg-muted hover:bg-surface-2 disabled:opacity-50",
              )}
            >
              <ChevronRight className="h-4 w-4" aria-hidden />
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}

function ContactRow({
  accountId,
  contact,
}: {
  accountId: string;
  contact: Contact;
}) {
  const del = useDeleteContact(accountId);
  const [error, setError] = useState<string | null>(null);

  async function onDelete(e: React.MouseEvent) {
    e.preventDefault();
    e.stopPropagation();
    const label = contact.name || contact.email || `#${contact.id}`;
    if (!window.confirm(`¿Eliminar el contacto "${label}"?`)) return;
    setError(null);
    try {
      await del.mutateAsync(contact.id);
    } catch (err) {
      setError(
        (err as { message?: string })?.message ?? "No se pudo eliminar.",
      );
    }
  }

  const displayName =
    contact.name?.trim() ||
    contact.email?.trim() ||
    contact.phone_number?.trim() ||
    `Contacto #${contact.id}`;

  return (
    <li className="flex items-center gap-1 pr-2 hover:bg-surface-2">
      <Link
        href={`/accounts/${accountId}/contacts/${contact.id}`}
        className="flex min-w-0 flex-1 items-center gap-3 px-4 py-3 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring"
      >
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary">
          <UserIcon className="h-4 w-4" aria-hidden />
        </span>
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium text-fg">
            {displayName}
            {contact.blocked ? (
              <span className="ml-2 rounded bg-danger/10 px-1.5 py-0.5 text-[10px] font-medium uppercase text-danger">
                Bloqueado
              </span>
            ) : null}
          </p>
          <p className="flex flex-wrap items-center gap-3 text-xs text-fg-muted">
            {contact.email ? (
              <span className="flex items-center gap-1">
                <Mail className="h-3 w-3" aria-hidden />
                {contact.email}
              </span>
            ) : null}
            {contact.phone_number ? (
              <span className="flex items-center gap-1">
                <Phone className="h-3 w-3" aria-hidden />
                {contact.phone_number}
              </span>
            ) : null}
            {!contact.email && !contact.phone_number && contact.identifier
              ? `id ${contact.identifier}`
              : null}
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
        className="rounded-md p-1.5 text-fg-muted hover:bg-surface hover:text-danger disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <Trash2 className="h-4 w-4" aria-hidden />
      </button>
      <ChevronRight className="h-4 w-4 shrink-0 text-fg-muted" aria-hidden />
    </li>
  );
}
