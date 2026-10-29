"use client";

import { Megaphone, Search, SlidersHorizontal, X } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useState } from "react";

import { Avatar } from "@/components/ui/avatar";
import { selectClassName } from "@/components/ui/select";
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
import { useInboxes } from "@/lib/api/inboxes";
import { shortDate } from "@/lib/time";
import { cn } from "@/lib/utils";

import { ChannelBadge } from "./channel-badge";
import { ConversationFilters } from "./conversation-filters";

const STATUS_PILLS = [
  { key: "open", label: "Abiertas" },
  { key: "resolved", label: "Resueltas" },
  { key: "pending", label: "Pendientes" },
  { key: "all", label: "Todas" },
] as const;

const ASSIGNEE_TABS = [
  { key: undefined, label: "Todas", countKey: "all_count" },
  { key: "me", label: "Míos", countKey: "mine_count" },
  { key: "unassigned", label: "Sin asignar", countKey: "unassigned_count" },
] as const;

const PER_PAGE = 25;

export function ConversationList({ accountId }: { accountId: string }) {
  const searchParams = useSearchParams();
  const router = useRouter();
  const pathname = usePathname() ?? "";

  // URL is the source of truth for the shareable list state, so refresh,
  // back/forward, and deep links all just work. Transient UI (selection, the
  // open filter panel) stays local; the advanced filter DSL is complex to
  // serialise so it stays local too (cleared on refresh).
  const status = searchParams.get("status") ?? "open";
  const assigneeType = searchParams.get("assignee") ?? undefined;
  const inboxParam = searchParams.get("inbox_id");
  const inboxId =
    inboxParam && Number.isFinite(Number(inboxParam))
      ? Number(inboxParam)
      : undefined;
  const page = Math.max(1, Number(searchParams.get("page")) || 1);
  const q = searchParams.get("q") ?? "";

  const activeMatch = /^\/accounts\/[^/]+\/conversations\/(\d+)(?:\/|$)/.exec(
    pathname,
  );
  const activeConversationId = activeMatch ? Number(activeMatch[1]) : null;
  const queryString = searchParams.toString();

  const setParams = useCallback(
    (updates: Record<string, string | null>, push = false) => {
      const sp = new URLSearchParams(searchParams.toString());
      for (const [k, v] of Object.entries(updates)) {
        if (v === null || v === "") sp.delete(k);
        else sp.set(k, v);
      }
      const qs = sp.toString();
      const url = qs ? `${pathname}?${qs}` : pathname;
      if (push) router.push(url, { scroll: false });
      else router.replace(url, { scroll: false });
    },
    [searchParams, pathname, router],
  );

  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [filters, setFilters] = useState<FilterCondition[]>([]);
  const [filterMatch, setFilterMatch] = useState<"AND" | "OR">("AND");
  const [showFilters, setShowFilters] = useState(false);

  const trimmed = q.trim();
  const searching = trimmed.length > 0;
  // Search wins over filters when both are set, so the index, search, and
  // filter modes stay mutually exclusive.
  const filtering = !searching && filters.length > 0;

  const indexQ = useConversations(accountId, {
    status,
    assigneeType,
    inboxId,
    page,
  });
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

  const meta = searching
    ? searchQ.data?.meta
    : filtering
      ? filterQ.data?.meta
      : indexQ.data?.data.meta;

  const bulk = useBulkAction(accountId);
  const views = useCustomViews(accountId, "conversation");
  const createView = useCreateCustomView(accountId);
  const deleteView = useDeleteCustomView(accountId);
  const agents = useAgents(accountId);
  const labels = useLabels(accountId);
  const inboxes = useInboxes(accountId);

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
    setParams({ q: null, page: null }); // filters and search are exclusive
    clearSelected();
  }
  function clearFilters() {
    setFilters([]);
    setShowFilters(false);
    setParams({ page: null });
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
    <div className="flex min-h-0 flex-1 flex-col">
      {/* Assignee tabs with counts */}
      <div className="flex items-center gap-4 border-b border-glass px-3">
        {ASSIGNEE_TABS.map((t) => {
          const isActive = assigneeType === t.key;
          const count = meta?.[t.countKey];
          return (
            <button
              key={t.label}
              type="button"
              aria-pressed={isActive}
              onClick={() => {
                setParams({ assignee: t.key ?? null, page: null }, true);
                clearSelected();
              }}
              className={cn(
                "inline-flex items-center gap-1.5 border-b-2 py-2.5 text-xs font-medium transition-colors",
                "focus-visible:outline focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-neon",
                isActive
                  ? "border-neon text-lit"
                  : "border-transparent text-fg-muted hover:text-fg",
              )}
            >
              <span>{t.label}</span>
              {typeof count === "number" ? (
                <span className="font-numeric text-[11px] tabular-nums text-fg-muted">
                  {count}
                </span>
              ) : null}
            </button>
          );
        })}
      </div>

      {/* Search, status pills, inbox selector, and active toolbars */}
      <div className="space-y-2.5 border-b border-glass p-3">
        <div className="flex gap-1.5">
          <div className="relative min-w-0 flex-1">
            <Search
              className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-fg-muted"
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
                setParams({ q: v || null, page: null });
                clearSelected();
                if (v.trim()) setFilters([]); // search and filters are exclusive
              }}
              placeholder="Buscar conversaciones…"
              className="glass-field h-9 w-full rounded-control border border-glass bg-field pl-8 pr-8 text-xs text-fg placeholder:text-fg-muted"
            />
            {q ? (
              <button
                type="button"
                aria-label="Limpiar búsqueda"
                onClick={() => {
                  setParams({ q: null, page: null });
                  clearSelected();
                }}
                className="absolute right-1.5 top-1/2 -translate-y-1/2 rounded-md p-1 text-fg-muted hover:bg-hover-glass hover:text-fg"
              >
                <X className="h-3.5 w-3.5" aria-hidden />
              </button>
            ) : null}
          </div>
          <button
            type="button"
            onClick={() => setShowFilters((s) => !s)}
            aria-pressed={showFilters}
            aria-label="Filtros"
            title="Filtros avanzados"
            className={cn(
              "inline-flex h-9 shrink-0 items-center gap-1 rounded-control border border-glass px-2.5 text-xs font-medium transition-colors",
              "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-neon",
              showFilters || filtering
                ? "bg-focused text-lit"
                : "bg-field text-fg-muted hover:bg-hover-glass hover:text-fg",
            )}
          >
            <SlidersHorizontal className="h-3.5 w-3.5" aria-hidden />
            {filters.length > 0 ? (
              <span className="rounded-pill bg-neon px-1.5 font-numeric text-[10px] font-semibold tabular-nums text-white">
                {filters.length}
              </span>
            ) : null}
          </button>
        </div>

        {/* Status pills */}
        <div className="flex flex-wrap gap-1.5">
          {STATUS_PILLS.map((t) => {
            const isActive = !searching && !filtering && status === t.key;
            return (
              <button
                key={t.key}
                type="button"
                aria-pressed={isActive}
                onClick={() => {
                  setParams(
                    { status: t.key === "open" ? null : t.key, page: null },
                    true,
                  );
                  clearSelected();
                }}
                className={cn(
                  "rounded-pill border px-2.5 py-1 text-xs font-medium transition-colors",
                  "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-neon",
                  isActive
                    ? "border-neon bg-focused text-lit"
                    : "border-glass bg-field text-fg-muted hover:bg-hover-glass hover:text-fg",
                )}
              >
                {t.label}
              </button>
            );
          })}
        </div>

        {/* Inbox selector */}
        <select
          aria-label="Bandeja de entrada"
          value={inboxId != null ? String(inboxId) : ""}
          onChange={(e) => {
            const v = e.target.value;
            setParams({ inbox_id: v || null, page: null }, true);
            clearSelected();
          }}
          className={cn(selectClassName("sm"), "w-full")}
        >
          <option value="">Todas las bandejas</option>
          {(inboxes.data ?? []).map((inbox) => (
            <option key={inbox.id} value={String(inbox.id)}>
              {inbox.name}
            </option>
          ))}
        </select>

        {!searching &&
        !showFilters &&
        selected.size === 0 &&
        (views.data?.length ?? 0) > 0 ? (
          <div className="flex flex-wrap items-center gap-1.5 pt-0.5">
            <span className="text-[11px] font-medium text-fg-muted">
              Vistas:
            </span>
            {views.data!.map((v) => (
              <span
                key={v.id}
                className="inline-flex items-center gap-1 rounded-pill border border-glass bg-field py-0.5 pl-2.5 pr-1 text-xs"
              >
                <button
                  type="button"
                  onClick={() => applyView(v)}
                  className="font-medium text-fg hover:text-lit"
                >
                  {v.name}
                </button>
                <button
                  type="button"
                  onClick={() => deleteView.mutate(v.id)}
                  aria-label={`Eliminar vista ${v.name}`}
                  className="rounded-pill p-0.5 text-fg-muted hover:bg-hover-glass hover:text-danger"
                >
                  <X className="h-3 w-3" aria-hidden />
                </button>
              </span>
            ))}
          </div>
        ) : null}

        {selected.size > 0 ? (
          <div className="flex flex-wrap items-center gap-1.5 rounded-md border border-glass bg-surface-2 p-2">
            <span className="font-numeric text-xs font-medium tabular-nums text-fg">
              {selected.size} seleccionada{selected.size === 1 ? "" : "s"}
            </span>
            <button
              type="button"
              onClick={clearSelected}
              aria-label="Cancelar selección"
              className="ml-auto rounded-md p-1 text-fg-muted hover:bg-hover-glass hover:text-fg"
            >
              <X className="h-3.5 w-3.5" aria-hidden />
            </button>
            <div className="flex w-full flex-wrap items-center gap-1.5">
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
                className={selectClassName("sm")}
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
                  className={selectClassName("sm")}
                >
                  <option value="">Etiquetar…</option>
                  {labels.data!.map((l) => (
                    <option key={l.id} value={l.title}>
                      {l.title}
                    </option>
                  ))}
                </select>
              ) : null}
            </div>
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
          <p className="text-xs text-fg-muted">
            Resultados para{" "}
            <span className="font-medium text-fg">“{trimmed}”</span>
          </p>
        ) : filtering ? (
          <div className="flex flex-wrap items-center gap-2 rounded-md border border-glass bg-surface-2 px-2.5 py-1.5 text-xs">
            <span className="font-medium text-fg">
              {filters.length} filtro{filters.length === 1 ? "" : "s"} activo
              {filters.length === 1 ? "" : "s"}
            </span>
            <button
              type="button"
              onClick={() => setShowFilters(true)}
              className="ml-auto rounded-md px-1.5 py-0.5 font-medium text-fg-muted hover:text-fg"
            >
              Editar
            </button>
            <button
              type="button"
              onClick={clearFilters}
              className="rounded-md px-1.5 py-0.5 font-medium text-fg-muted hover:text-fg"
            >
              Limpiar
            </button>
          </div>
        ) : null}
      </div>

      {/* Scrollable list */}
      <div className="min-h-0 flex-1 overflow-y-auto">
        {active.isLoading ? (
          <p className="p-6 text-center text-sm text-fg-muted">Cargando…</p>
        ) : active.isError ? (
          <p role="alert" className="p-6 text-center text-sm text-danger">
            No se pudieron cargar las conversaciones.
          </p>
        ) : items.length === 0 ? (
          <p className="p-6 text-center text-sm text-fg-muted">
            {searching
              ? `No hay resultados para “${trimmed}”.`
              : filtering
                ? "No hay conversaciones que coincidan con los filtros."
                : "No hay conversaciones en este filtro."}
          </p>
        ) : (
          <ul className="divide-y divide-glass">
            {items.map((c) => (
              <ConversationRow
                key={c.id}
                accountId={accountId}
                conv={c}
                active={activeConversationId === c.id}
                queryString={queryString}
                selected={selected.has(c.id)}
                onToggle={() => toggleSelected(c.id)}
              />
            ))}
          </ul>
        )}
      </div>

      {/* Compact pagination */}
      {page > 1 || items.length >= PER_PAGE ? (
        <div className="flex items-center justify-between border-t border-glass px-3 py-2">
          <FilterButton
            active={false}
            disabled={page <= 1}
            onClick={() => {
              setParams({ page: page <= 2 ? null : String(page - 1) }, true);
              clearSelected();
            }}
          >
            Anterior
          </FilterButton>
          <span className="font-numeric text-xs tabular-nums text-fg-muted">
            Página {page}
          </span>
          <FilterButton
            active={false}
            disabled={items.length < PER_PAGE}
            onClick={() => {
              setParams({ page: String(page + 1) }, true);
              clearSelected();
            }}
          >
            Siguiente
          </FilterButton>
        </div>
      ) : null}
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
        "rounded-control px-2.5 py-1 text-xs font-medium transition-colors",
        "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-neon",
        "disabled:opacity-40",
        active
          ? "border border-neon bg-focused text-lit"
          : "border border-glass bg-field text-fg-muted hover:bg-hover-glass hover:text-fg",
      )}
    >
      {children}
    </button>
  );
}

function ConversationRow({
  accountId,
  conv,
  active,
  queryString,
  selected,
  onToggle,
}: {
  accountId: string;
  conv: Conversation;
  active: boolean;
  queryString: string;
  selected: boolean;
  onToggle: () => void;
}) {
  const name = conv.meta?.sender?.name ?? `Conversación #${conv.id}`;
  const last =
    conv.last_non_activity_message?.content ??
    conv.messages?.[conv.messages.length - 1]?.content ??
    "";
  const unread = conv.unread_count > 0;
  const baseHref = `/accounts/${accountId}/conversations/${conv.id}`;
  const href = queryString ? `${baseHref}?${queryString}` : baseHref;

  return (
    <li
      className={cn(
        "group flex items-center transition-colors",
        active ? "bg-focused" : "hover:bg-hover-glass",
      )}
    >
      <label className="flex shrink-0 cursor-pointer items-center py-3 pl-2.5 pr-1">
        <input
          type="checkbox"
          checked={selected}
          onChange={onToggle}
          aria-label={`Seleccionar ${name}`}
          className={cn(
            "h-3.5 w-3.5 rounded-sm border-glass accent-neon transition-opacity focus-visible:opacity-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-neon",
            selected ? "opacity-100" : "opacity-40 group-hover:opacity-100",
          )}
        />
      </label>
      <Link
        href={href}
        aria-current={active ? "page" : undefined}
        className="flex min-w-0 flex-1 items-center gap-2.5 py-2.5 pr-3 focus-visible:outline focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-neon"
      >
        <Avatar name={name} size="sm" />
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-1.5">
            {/* Before the name, so the column reads as one scannable strip
                of origins rather than an icon floating at a different x on
                every row. */}
            <ChannelBadge channel={conv.meta?.channel} />
            <span
              className={cn(
                "min-w-0 flex-1 truncate text-sm",
                active ? "text-lit" : "text-fg",
                unread ? "font-semibold" : "font-medium",
              )}
            >
              {name}
            </span>
            {conv.ad_referral ? (
              // Origin marker: lets you scan the column for the conversations
              // an ad paid for. The headline rides in the tooltip so the row
              // stays two lines.
              <Megaphone
                className="h-3.5 w-3.5 shrink-0 text-neon"
                aria-label={`Vino de ${
                  conv.ad_referral.headline ?? "un anuncio"
                }`}
              >
                <title>
                  {`Vino de ${conv.ad_referral.headline ?? "un anuncio"}`}
                </title>
              </Megaphone>
            ) : null}
            <span className="shrink-0 font-numeric text-[11px] tabular-nums text-fg-muted">
              {shortDate(conv.last_activity_at || conv.timestamp)}
            </span>
          </div>
          <div className="mt-0.5 flex items-center gap-2">
            <p
              className={cn(
                "min-w-0 flex-1 truncate text-xs",
                unread ? "text-fg" : "text-fg-muted",
              )}
            >
              {last || "—"}
            </p>
            {unread ? (
              <span className="shrink-0 rounded-pill bg-neon px-1.5 py-0.5 font-numeric text-[10px] font-semibold leading-none tabular-nums text-white">
                {conv.unread_count}
              </span>
            ) : null}
          </div>
        </div>
      </Link>
    </li>
  );
}
