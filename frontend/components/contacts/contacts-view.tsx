"use client";

import {
  ChevronLeft,
  ChevronRight,
  Mail,
  Phone,
  Plus,
  Search,
  SlidersHorizontal,
  Trash2,
  X,
} from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { PageHeader } from "@/components/shell/page-header";
import { Avatar } from "@/components/ui/avatar";
import { buttonVariants } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  type Contact,
  useContactCompanies,
  useContacts,
  useDeleteContact,
  useFilterContacts,
  useSearchContacts,
} from "@/lib/api/contacts";
import type { FilterCondition } from "@/lib/api/conversations";
import {
  type CustomView,
  useCreateCustomView,
  useCustomViews,
  useDeleteCustomView,
} from "@/lib/api/custom-views";
import { cn } from "@/lib/utils";

import { ContactFilters } from "./contact-filters";

const PAGE_SIZE = 15; // mirrors backend RESULTS_PER_PAGE

export function ContactsView({ accountId }: { accountId: string }) {
  const [page, setPage] = useState(1);
  const [q, setQ] = useState("");
  const [company, setCompany] = useState<string | null>(null);
  const [filters, setFilters] = useState<FilterCondition[]>([]);
  const [filterMatch, setFilterMatch] = useState<"AND" | "OR">("AND");
  const [showFilters, setShowFilters] = useState(false);

  const trimmed = q.trim();
  const searching = trimmed.length > 0;
  const filtering = !searching && filters.length > 0;

  const companies = useContactCompanies(accountId);
  const segments = useCustomViews(accountId, "contact");
  const createSegment = useCreateCustomView(accountId);
  const deleteSegment = useDeleteCustomView(accountId);

  // Priority: search > advanced filter > company/index — one at a time.
  const indexQ = useContacts(accountId, page, company ?? undefined);
  const searchQ = useSearchContacts(accountId, trimmed, page);
  const filterQ = useFilterContacts(accountId, filters, page);
  const active = searching ? searchQ : filtering ? filterQ : indexQ;

  function applyFilters(conds: FilterCondition[], match: "AND" | "OR") {
    setFilters(conds);
    setFilterMatch(match);
    setQ("");
    setCompany(null);
    setPage(1);
    setShowFilters(false);
  }
  function clearFilters() {
    setFilters([]);
    setPage(1);
  }
  async function saveSegment(
    name: string,
    conds: FilterCondition[],
    match: "AND" | "OR",
  ) {
    await createSegment.mutateAsync({
      name,
      filter_type: "contact",
      query: { payload: conds },
    });
    applyFilters(conds, match);
  }
  function applySegment(view: CustomView) {
    const conds = view.query?.payload ?? [];
    const match = (conds[0]?.query_operator as "AND" | "OR") ?? "AND";
    applyFilters(conds, match);
  }

  const data = active.data;
  const items: Contact[] = data?.payload ?? [];
  const total = data?.meta?.count ?? 0;

  const hasMore = searching
    ? Boolean((data as { meta?: { has_more?: boolean } })?.meta?.has_more)
    : page * PAGE_SIZE < total;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div className="mx-auto max-w-4xl space-y-4">
      <PageHeader
        title="Contactos"
        actions={
          <Link
            href={`/accounts/${accountId}/contacts/new`}
            className={buttonVariants({ size: "sm" })}
          >
            <Plus className="h-4 w-4" aria-hidden />
            Nuevo contacto
          </Link>
        }
      />

      <div className="flex gap-2">
        <div className="relative flex-1">
          <Search
            className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-fg-muted"
            aria-hidden
          />
          <Input
            aria-label="Buscar contactos"
            value={q}
            onChange={(e) => {
              setQ(e.target.value);
              setCompany(null);
              setFilters([]);
              setPage(1);
            }}
            placeholder="Buscar por nombre, email, teléfono o identificador…"
            className="pl-9"
          />
        </div>
        <button
          type="button"
          onClick={() => setShowFilters((s) => !s)}
          aria-pressed={showFilters}
          className={cn(
            "inline-flex items-center gap-1.5 rounded-control border border-glass px-3 text-sm font-medium transition-colors",
            "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-neon",
            showFilters || filtering
              ? "bg-focused text-lit"
              : "bg-field text-fg-muted hover:bg-hover-glass hover:text-fg",
          )}
        >
          <SlidersHorizontal className="h-4 w-4" aria-hidden />
          Filtros
        </button>
      </div>

      {showFilters ? (
        <ContactFilters
          initial={filters}
          initialMatch={filterMatch}
          onApply={applyFilters}
          onClear={() => {
            clearFilters();
            setShowFilters(false);
          }}
          onCancel={() => setShowFilters(false)}
          onSaveSegment={saveSegment}
        />
      ) : null}

      {!searching && (segments.data?.length ?? 0) > 0 ? (
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs font-medium text-fg-muted">Segmentos:</span>
          {segments.data?.map((seg) => (
            <span
              key={seg.id}
              className="inline-flex items-center rounded-pill border border-glass bg-field text-xs"
            >
              <button
                type="button"
                onClick={() => applySegment(seg)}
                className="rounded-l-pill px-2.5 py-0.5 font-medium text-fg hover:bg-hover-glass"
              >
                {seg.name}
              </button>
              <button
                type="button"
                aria-label={`Eliminar segmento ${seg.name}`}
                onClick={() => deleteSegment.mutate(seg.id)}
                className="rounded-r-pill py-0.5 pl-1 pr-2 text-fg-muted hover:text-danger"
              >
                <X className="h-3 w-3" aria-hidden />
              </button>
            </span>
          ))}
        </div>
      ) : null}

      {!searching && !filtering && (companies.data?.length ?? 0) > 0 ? (
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs font-medium text-fg-muted">Empresas:</span>
          {companies.data?.map((co) => {
            const on = company === co.name;
            return (
              <button
                key={co.name}
                type="button"
                aria-pressed={on}
                onClick={() => {
                  setCompany(on ? null : co.name);
                  setPage(1);
                }}
                className={cn(
                  "inline-flex items-center gap-1 rounded-pill border px-2.5 py-0.5 text-xs transition-colors",
                  "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-neon",
                  on
                    ? "border-neon bg-focused font-medium text-lit"
                    : "border-glass bg-field text-fg-muted hover:bg-hover-glass",
                )}
              >
                {co.name}
                <span className="font-numeric tabular-nums text-fg-muted">
                  {co.count}
                </span>
                {on ? <X className="h-3 w-3" aria-hidden /> : null}
              </button>
            );
          })}
        </div>
      ) : null}

      <div className="overflow-hidden rounded-md border border-glass bg-surface">
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
              : filtering
                ? "No hay contactos que coincidan con el filtro."
                : company
                  ? `No hay contactos en ${company}.`
                  : "No hay contactos todavía."}
          </p>
        ) : (
          <ul className="divide-y divide-glass">
            {items.map((c) => (
              <ContactRow key={c.id} accountId={accountId} contact={c} />
            ))}
          </ul>
        )}
      </div>

      {/* Pagination */}
      {items.length > 0 ? (
        <div className="flex items-center justify-between font-numeric text-sm tabular-nums text-fg-muted">
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
              className="rounded-md border border-glass bg-field p-1.5 text-fg-muted hover:bg-hover-glass hover:text-fg disabled:opacity-50"
            >
              <ChevronLeft className="h-4 w-4" aria-hidden />
            </button>
            <button
              type="button"
              aria-label="Página siguiente"
              onClick={() => setPage((p) => p + 1)}
              disabled={!hasMore || active.isFetching}
              className="rounded-md border border-glass bg-field p-1.5 text-fg-muted hover:bg-hover-glass hover:text-fg disabled:opacity-50"
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
    <li className="flex items-center gap-1 pr-2 transition-colors hover:bg-hover-glass">
      <Link
        href={`/accounts/${accountId}/contacts/${contact.id}`}
        className="flex min-w-0 flex-1 items-center gap-3 px-4 py-3 focus-visible:outline focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-neon"
      >
        <Avatar name={displayName} />
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium text-fg">
            {displayName}
            {contact.blocked ? (
              <span className="ml-2 rounded-sm bg-danger/10 px-1.5 py-0.5 text-[10px] font-medium uppercase text-danger">
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
              <span className="flex items-center gap-1 font-numeric tabular-nums">
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
        className="rounded-md p-1.5 text-fg-muted hover:bg-hover-glass hover:text-danger disabled:opacity-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-neon"
      >
        <Trash2 className="h-4 w-4" aria-hidden />
      </button>
      <ChevronRight className="h-4 w-4 shrink-0 text-fg-muted" aria-hidden />
    </li>
  );
}
