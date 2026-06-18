"use client";

import Link from "next/link";
import { useState } from "react";

import {
  type Conversation,
  useConversations,
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

  const { data, isLoading, isError } = useConversations(accountId, {
    status,
    assigneeType,
    page,
  });
  const items = data?.data.payload ?? [];

  return (
    <div className="mx-auto max-w-3xl">
      <h1 className="mb-4 text-2xl font-semibold text-fg">Conversaciones</h1>

      <div className="mb-3 flex flex-wrap gap-2">
        {STATUS_TABS.map((t) => (
          <FilterButton
            key={t.key}
            active={status === t.key}
            onClick={() => {
              setStatus(t.key);
              setPage(1);
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
            }}
          >
            {t.label}
          </FilterButton>
        ))}
      </div>

      <div className="overflow-hidden rounded-lg border border-border bg-surface">
        {isLoading ? (
          <p className="p-8 text-center text-sm text-fg-muted">Cargando…</p>
        ) : isError ? (
          <p role="alert" className="p-8 text-center text-sm text-danger">
            No se pudieron cargar las conversaciones.
          </p>
        ) : items.length === 0 ? (
          <p className="p-8 text-center text-sm text-fg-muted">
            No hay conversaciones en este filtro.
          </p>
        ) : (
          <ul className="divide-y divide-border">
            {items.map((c) => (
              <ConversationRow key={c.id} accountId={accountId} conv={c} />
            ))}
          </ul>
        )}
      </div>

      <div className="mt-3 flex items-center justify-between">
        <FilterButton
          active={false}
          disabled={page <= 1}
          onClick={() => setPage((p) => Math.max(1, p - 1))}
        >
          Anterior
        </FilterButton>
        <span className="text-xs text-fg-muted tabular-nums">Página {page}</span>
        <FilterButton
          active={false}
          disabled={items.length < PER_PAGE}
          onClick={() => setPage((p) => p + 1)}
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
}: {
  accountId: string;
  conv: Conversation;
}) {
  const name = conv.meta?.sender?.name ?? `Conversación #${conv.id}`;
  const last =
    conv.last_non_activity_message?.content ??
    conv.messages?.[conv.messages.length - 1]?.content ??
    "";

  return (
    <li>
      <Link
        href={`/accounts/${accountId}/conversations/${conv.id}`}
        className="flex items-center gap-3 px-4 py-3 hover:bg-surface-2"
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
