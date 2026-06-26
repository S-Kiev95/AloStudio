"use client";

import { Search, X } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import {
  type Conversation,
  useBulkAction,
  useConversations,
  useSearchConversations,
} from "@/lib/api/conversations";
import { relativeTime } from "@/lib/time";
import { cn } from "@/lib/utils";

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

  const trimmed = q.trim();
  const searching = trimmed.length > 0;

  const indexQ = useConversations(accountId, { status, assigneeType, page });
  const searchQ = useSearchConversations(accountId, trimmed, page);
  const active = searching ? searchQ : indexQ;

  const items: Conversation[] = searching
    ? (searchQ.data?.payload ?? [])
    : (indexQ.data?.data.payload ?? []);

  const bulk = useBulkAction(accountId);

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

  return (
    <div className="mx-auto max-w-3xl">
      <h1 className="mb-4 text-2xl font-semibold text-fg">Conversaciones</h1>

      <div className="relative mb-3">
        <Search
          className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-fg-muted"
          aria-hidden
        />
        <input
          type="search"
          aria-label="Buscar en los mensajes"
          value={q}
          onChange={(e) => {
            setQ(e.target.value);
            setPage(1);
            clearSelected();
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
          <button
            type="button"
            onClick={clearSelected}
            aria-label="Cancelar selección"
            className="ml-auto rounded-md p-1 text-fg-muted hover:bg-surface hover:text-fg"
          >
            <X className="h-4 w-4" aria-hidden />
          </button>
        </div>
      ) : searching ? (
        <p className="mb-3 text-sm text-fg-muted">
          Resultados para{" "}
          <span className="font-medium text-fg">“{trimmed}”</span>
        </p>
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
