"use client";

import { Search, SlidersHorizontal, X } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { useAgents, useLabels } from "@/lib/api/account";
import {
  type Conversation,
  type FilterCondition,
  useBulkAction,
  useConversations,
  useFilterConversations,
  useSearchConversations,
} from "@/lib/api/conversations";
import {
  type CustomView,
  useCreateCustomView,
  useCustomViews,
  useDeleteCustomView,
} from "@/lib/api/custom-views";
import { relativeTime } from "@/lib/time";
import { cn } from "@/lib/utils";

import { ConversationFilters } from "./conversation-filters";

const STATUS_TABS = [
  { key: "open", label: "Abiertas" },
  { key: "pending", label: "Pendientes" },
  { key: "resolved", label: "Resueltas" },
] as const;

const ASSIGNEE_TABS = [
  { key: undefined, label: "Todas" },
  { key: "me", label: "Míos" },
  { key: "unassigned", label: "Sin asignar" },
] as const;

const PER_PAGE = 25;

export function ConversationList({ accountId }: { accountId: string }) {
  const [status, setStatus] = useState<string>("open");
  const [assigneeType, setAssigneeType] = useState<string | undefined>(
    undefined,
  );
  const [page, setPage] = useState(1);
  const [q, setQ] = useState("");
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [filters, setFilters] = useState<FilterCondition[]>([]);
  const [filterMatch, setFilterMatch] = useState<"AND" | "OR">("AND");
  const [showFilters, setShowFilters] = useState(false);

  const trimmed = q.trim();
  const searching = trimmed.length > 0;
  // Search wins over filters when both are set, so the index, search, and
  // filter modes stay mutually exclusive.
  const filtering = !searching && filters.length > 0;

  const indexQ = useConversations(accountId, { status, assigneeType, page });
  const searchQ = useSearchConversations(accountId, trimmed, page);
  const filterQ = useFilterConversations(
    accountId,
    filtering ? filters : [],
    page,
  );
  const active = searching ? searchQ : filtering ? filterQ : indexQ;

  const items: Conversation[] = searching
    ? (searchQ.data?.payload ?? [])
    : filtering
      ? (filterQ.data?.payload ?? [])
      : (indexQ.data?.data.payload ?? []);

  const bulk = useBulkAction(accountId);
  const views = useCustomViews(accountId, "conversation");
  const createView = useCreateCustomView(accountId);
  const deleteView = useDeleteCustomView(accountId);
  const agents = useAgents(accountId);
  const labels = useLabels(accountId);

  function clearSelected() {
    setSelected(new Set());
  }
  function toggleSelected(id: number) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }
  async function bulkStatus(newStatus: string) {
    const ids = [...selected];
    if (ids.length === 0) return;
    await bulk.mutateAsync({ ids, fields: { status: newStatus } });
    clearSelected();
  }
  async function bulkAssign(assigneeId: number | null) {
    const ids = [...selected];
    if (ids.length === 0) return;
    await bulk.mutateAsync({ ids, fields: { assignee_id: assigneeId } });
    clearSelected();
  }
  async function bulkAddLabel(title: string) {
    const ids = [...selected];
    if (ids.length === 0) return;
    await bulk.mutateAsync({ ids, labels: { add: [title] } });
    clearSelected();
  }
  function applyFilters(conds: FilterCondition[], match: "AND" | "OR") {
    setFilters(conds);
    setFilterMatch(match);
    setShowFilters(false);
    setQ(""); // filters and search are mutually exclusive
    setPage(1);
    clearSelected();
  }
  function clearFilters() {
    setFilters([]);
    setShowFilters(false);
    setPage(1);
    clearSelected();
  }
  async function saveView(
    name: string,
    conds: FilterCondition[],
    match: "AND" | "OR",
  ) {
    await createView.mutateAsync({ name, query: { payload: conds } });
    applyFilters(conds, match);
  }
  function applyView(view: CustomView) {
    const conds = view.query?.payload ?? [];
    if (conds.length === 0) return;
    const match = conds[0]?.query_operator === "OR" ? "OR" : "AND";
    applyFilters(conds, match);
  }

  return (
    <div className="mx-auto max-w-3xl">
      <h1 className="mb-4 text-2xl font-semibold text-fg">Conversaciones</h1>

      <div className="mb-3 flex gap-2">
        <div className="relative flex-1">
          <Search
            className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-fg-muted"
            aria-hidden
          />
          <input
            type="search"
            name="conversation-search"
            autoComplete="off"
            aria-label="Buscar en los mensajes"
            value={q}
            onChange={(e) => {
              const v = e.target.value;
              setQ(v);
              setPage(1);
              clearSelected();
              if (v.trim()) setFilters([]); // search and filters are exclusive
            }}
            placeholder="Buscar en los mensajes…"
            className="h-11 w-full rounded-md border border-border bg-surface pl-9 pr-9 text-sm text-fg placeholder:text-fg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-bg"
          />
          {q ? (
            <button
              type="button"
              aria-label="Limpiar búsqueda"
              onClick={() => {
                setQ("");
                setPage(1);
                clearSelected();
              }}
              className="absolute right-2 top-1/2 -translate-y-1/2 rounded-md p-1 text-fg-muted hover:bg-surface-2 hover:text-fg"
            >
              <X className="h-4 w-4" aria-hidden />
            </button>
          ) : null}
        </div>
        <button
          type="button"
          onClick={() => setShowFilters((s) => !s)}
          aria-pressed={showFilters}
          aria-label="Filtros"
          className={cn(
            "inline-flex shrink-0 items-center gap-1.5 rounded-md border border-border px-3 text-sm font-medium transition-colors",
            "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
            showFilters || filtering
              ? "bg-surface-2 text-fg"
              : "bg-surface text-fg-muted hover:bg-surface-2 hover:text-fg",
          )}
        >
          <SlidersHorizontal className="h-4 w-4" aria-hidden />
          Filtros
          {filters.length > 0 ? (
            <span className="rounded-full bg-primary px-1.5 text-[10px] font-semibold text-primary-fg tabular-nums">
              {filters.length}
            </span>
          ) : null}
        </button>
      </div>

      {!searching &&
      !showFilters &&
      selected.size === 0 &&
      (views.data?.length ?? 0) > 0 ? (
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <span className="text-xs font-medium text-fg-muted">Vistas:</span>
          {views.data!.map((v) => (
            <span
              key={v.id}
              className="inline-flex items-center gap-1 rounded-full border border-border bg-surface py-1 pl-3 pr-1 text-xs"
            >
              <button
                type="button"
                onClick={() => applyView(v)}
                className="font-medium text-fg hover:text-primary"
              >
                {v.name}
              </button>
              <button
                type="button"
                onClick={() => deleteView.mutate(v.id)}
                aria-label={`Eliminar vista ${v.name}`}
                className="rounded-full p-0.5 text-fg-muted hover:bg-surface-2 hover:text-danger"
              >
                <X className="h-3 w-3" aria-hidden />
              </button>
            </span>
          ))}
        </div>
      ) : null}

      {selected.size > 0 ? (
        <div className="mb-3 flex flex-wrap items-center gap-2 rounded-md border border-border bg-surface-2 px-3 py-2">
          <span className="text-sm font-medium tabular-nums text-fg">
            {selected.size} seleccionada{selected.size === 1 ? "" : "s"}
          </span>
          <span className="mx-1 h-4 w-px bg-border" aria-hidden />
          <FilterButton
            active={false}
            disabled={bulk.isPending}
            onClick={() => bulkStatus("resolved")}
          >
            Resolver
          </FilterButton>
          <FilterButton
            active={false}
            disabled={bulk.isPending}
            onClick={() => bulkStatus("open")}
          >
            Reabrir
          </FilterButton>
          <FilterButton
            active={false}
            disabled={bulk.isPending}
            onClick={() => bulkStatus("pending")}
          >
            Pendiente
          </FilterButton>
          <span className="mx-1 h-4 w-px bg-border" aria-hidden />
          <select
            aria-label="Asignar a"
            value=""
            disabled={bulk.isPending}
            onChange={(e) => {
              const v = e.target.value;
              if (!v) return;
              void bulkAssign(v === "none" ? null : Number(v));
              e.currentTarget.value = "";
            }}
            className="rounded-md border border-border bg-surface px-2 py-1.5 text-sm font-medium text-fg-muted hover:bg-surface-2 hover:text-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-40"
          >
            <option value="">Asignar a…</option>
            <option value="none">Sin asignar</option>
            {(agents.data ?? []).map((a) => (
              <option key={a.id} value={a.id}>
                {a.name}
              </option>
            ))}
          </select>
          {(labels.data?.length ?? 0) > 0 ? (
            <select
              aria-label="Etiquetar"
              value=""
              disabled={bulk.isPending}
              onChange={(e) => {
                const v = e.target.value;
                if (!v) return;
                void bulkAddLabel(v);
                e.currentTarget.value = "";
              }}
              className="rounded-md border border-border bg-surface px-2 py-1.5 text-sm font-medium text-fg-muted hover:bg-surface-2 hover:text-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-40"
            >
              <option value="">Etiquetar…</option>
              {labels.data!.map((l) => (
                <option key={l.id} value={l.title}>
                  {l.title}
                </option>
              ))}
            </select>
          ) : null}
          <button
            type="button"
            onClick={clearSelected}
            aria-label="Cancelar selección"
            className="ml-auto rounded-md p-1 text-fg-muted hover:bg-surface hover:text-fg"
          >
            <X className="h-4 w-4" aria-hidden />
          </button>
        </div>
      ) : showFilters ? (
        <ConversationFilters
          accountId={accountId}
          initial={filters}
          initialMatch={filterMatch}
          onApply={applyFilters}
          onClear={clearFilters}
          onCancel={() => setShowFilters(false)}
          onSaveView={saveView}
        />
      ) : searching ? (
        <p className="mb-3 text-sm text-fg-muted">
          Resultados para{" "}
          <span className="font-medium text-fg">“{trimmed}”</span>
        </p>
      ) : filtering ? (
        <div className="mb-3 flex flex-wrap items-center gap-2 rounded-md border border-border bg-surface-2 px-3 py-2 text-sm">
          <span className="font-medium text-fg">
            {filters.length} filtro{filters.length === 1 ? "" : "s"} activo
            {filters.length === 1 ? "" : "s"}
          </span>
          <button
            type="button"
            onClick={() => setShowFilters(true)}
            className="ml-auto rounded-md px-2 py-1 font-medium text-fg-muted hover:text-fg"
          >
            Editar
          </button>
          <button
            type="button"
            onClick={clearFilters}
            className="rounded-md px-2 py-1 font-medium text-fg-muted hover:text-fg"
          >
            Limpiar
          </button>
        </div>
      ) : (
        <div className="mb-3 flex flex-wrap gap-2">
          {STATUS_TABS.map((t) => (
            <FilterButton
              key={t.key}
              active={status === t.key}
              onClick={() => {
                setStatus(t.key);
                setPage(1);
                clearSelected();
              }}
            >
              {t.label}
            </FilterButton>
          ))}
          <span className="mx-1 w-px self-stretch bg-border" aria-hidden />
          {ASSIGNEE_TABS.map((t) => (
            <FilterButton
              key={t.label}
              active={assigneeType === t.key}
              onClick={() => {
                setAssigneeType(t.key);
                setPage(1);
                clearSelected();
              }}
            >
              {t.label}
            </FilterButton>
          ))}
        </div>
      )}

      <div className="overflow-hidden rounded-lg border border-border bg-surface">
        {active.isLoading ? (
          <p className="p-8 text-center text-sm text-fg-muted">Cargando…</p>
        ) : active.isError ? (
          <p role="alert" className="p-8 text-center text-sm text-danger">
            No se pudieron cargar las conversaciones.
          </p>
        ) : items.length === 0 ? (
          <p className="p-8 text-center text-sm text-fg-muted">
            {searching
              ? `No hay resultados para “${trimmed}”.`
              : filtering
                ? "No hay conversaciones que coincidan con los filtros."
                : "No hay conversaciones en este filtro."}
          </p>
        ) : (
          <ul className="divide-y divide-border">
            {items.map((c) => (
              <ConversationRow
                key={c.id}
                accountId={accountId}
                conv={c}
                selected={selected.has(c.id)}
                onToggle={() => toggleSelected(c.id)}
              />
            ))}
          </ul>
        )}
      </div>

      <div className="mt-3 flex items-center justify-between">
        <FilterButton
          active={false}
          disabled={page <= 1}
          onClick={() => {
            setPage((p) => Math.max(1, p - 1));
            clearSelected();
          }}
        >
          Anterior
        </FilterButton>
        <span className="text-xs text-fg-muted tabular-nums">Página {page}</span>
        <FilterButton
          active={false}
          disabled={items.length < PER_PAGE}
          onClick={() => {
            setPage((p) => p + 1);
            clearSelected();
          }}
        >
          Siguiente
        </FilterButton>
      </div>
    </div>
  );
}

function FilterButton({
  active,
  disabled,
  onClick,
  children,
}: {
  active: boolean;
  disabled?: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      aria-pressed={active}
      className={cn(
        "rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        "disabled:opacity-40",
        active
          ? "border border-border bg-surface-2 font-semibold text-fg"
          : "border border-border bg-surface text-fg-muted hover:bg-surface-2 hover:text-fg",
      )}
    >
      {children}
    </button>
  );
}

function ConversationRow({
  accountId,
  conv,
  selected,
  onToggle,
}: {
  accountId: string;
  conv: Conversation;
  selected: boolean;
  onToggle: () => void;
}) {
  const name = conv.meta?.sender?.name ?? `Conversación #${conv.id}`;
  const last =
    conv.last_non_activity_message?.content ??
    conv.messages?.[conv.messages.length - 1]?.content ??
    "";

  return (
    <li className="flex items-center hover:bg-surface-2">
      <label className="flex shrink-0 cursor-pointer items-center py-3 pl-4 pr-1">
        <input
          type="checkbox"
          checked={selected}
          onChange={onToggle}
          aria-label={`Seleccionar ${name}`}
          className="h-4 w-4 rounded border-border accent-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        />
      </label>
      <Link
        href={`/accounts/${accountId}/conversations/${conv.id}`}
        className="flex min-w-0 flex-1 items-center gap-3 py-3 pr-4 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring"
      >
        <span className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-surface-2 text-xs font-semibold text-fg-muted">
          {name.charAt(0).toUpperCase()}
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="truncate text-sm font-medium text-fg">{name}</span>
            {conv.unread_count > 0 ? (
              <span className="rounded-full bg-primary px-1.5 text-[10px] font-semibold text-primary-fg tabular-nums">
                {conv.unread_count}
              </span>
            ) : null}
          </div>
          <p className="truncate text-xs text-fg-muted">{last || "—"}</p>
        </div>
        <span className="shrink-0 text-[11px] text-fg-muted tabular-nums">
          {relativeTime(conv.last_activity_at || conv.timestamp)}
        </span>
      </Link>
    </li>
  );
}
