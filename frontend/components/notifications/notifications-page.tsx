"use client";

import { CheckCheck, Trash2 } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  NOTIFICATION_TYPE_LABELS,
  useDeleteNotification,
  useMarkAllNotificationsRead,
  useMarkNotificationRead,
  useNotifications,
  useUnreadCount,
} from "@/lib/api/notifications";
import { relativeTime } from "@/lib/time";
import { cn } from "@/lib/utils";

/**
 * Full-page notifications inbox. Same actions as the bell dropdown,
 * but paginated + with a filter toggle (all vs unread).
 */
export function NotificationsPage({ accountId }: { accountId: string }) {
  const [filter, setFilter] = useState<"all" | "unread">("all");
  const [page, setPage] = useState(1);

  const list = useNotifications(accountId, {
    page,
    status: filter === "unread" ? "unread" : undefined,
  });
  const unread = useUnreadCount(accountId);
  const markRead = useMarkNotificationRead(accountId);
  const markAllRead = useMarkAllNotificationsRead(accountId);
  const deleteOne = useDeleteNotification(accountId);

  const rows = list.data?.payload ?? [];
  const total = list.data?.meta.count ?? 0;
  const pageSize = 15;
  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  return (
    <div className="mx-auto max-w-3xl space-y-4 p-4 md:p-6">
      <header className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h1 className="text-xl font-semibold text-fg">Notificaciones</h1>
          <p className="text-sm text-fg-muted">
            {unread.data ?? 0} sin leer · {total} en total
          </p>
        </div>
        <div className="flex items-center gap-2">
          <div
            role="tablist"
            aria-label="Filtro"
            className="inline-flex rounded-md border border-border bg-surface p-0.5"
          >
            <button
              role="tab"
              aria-selected={filter === "all"}
              onClick={() => {
                setFilter("all");
                setPage(1);
              }}
              className={cn(
                "rounded px-3 py-1 text-xs font-medium",
                filter === "all"
                  ? "bg-primary text-primary-fg"
                  : "text-fg-muted hover:text-fg",
              )}
            >
              Todas
            </button>
            <button
              role="tab"
              aria-selected={filter === "unread"}
              onClick={() => {
                setFilter("unread");
                setPage(1);
              }}
              className={cn(
                "rounded px-3 py-1 text-xs font-medium",
                filter === "unread"
                  ? "bg-primary text-primary-fg"
                  : "text-fg-muted hover:text-fg",
              )}
            >
              No leídas
            </button>
          </div>
          <Button
            variant="secondary"
            onClick={() => markAllRead.mutate()}
            disabled={!unread.data || markAllRead.isPending}
          >
            <CheckCheck className="mr-1 h-4 w-4" aria-hidden />
            Marcar todo
          </Button>
        </div>
      </header>

      <Card>
        <CardContent className="p-0">
          {list.isLoading ? (
            <p className="px-4 py-6 text-sm text-fg-muted">Cargando…</p>
          ) : list.isError ? (
            <p role="alert" className="px-4 py-6 text-sm text-danger">
              No se pudieron cargar las notificaciones.
            </p>
          ) : rows.length === 0 ? (
            <p className="px-4 py-10 text-center text-sm text-fg-muted">
              {filter === "unread"
                ? "No tenés notificaciones sin leer."
                : "Todavía no tenés notificaciones."}
            </p>
          ) : (
            <ul className="divide-y divide-border">
              {rows.map((n) => {
                const isUnread = n.read_at == null;
                const label =
                  NOTIFICATION_TYPE_LABELS[n.notification_type] ??
                  "Notificación";
                const href =
                  n.primary_actor?.display_id != null
                    ? `/accounts/${accountId}/conversations/${n.primary_actor.display_id}`
                    : undefined;
                return (
                  <li
                    key={n.id}
                    className="group/row flex items-center gap-3 px-4 py-3 hover:bg-surface-2"
                  >
                    <span
                      aria-hidden
                      className={cn(
                        "h-2 w-2 shrink-0 rounded-full",
                        isUnread ? "bg-primary" : "bg-transparent",
                      )}
                    />
                    <div className="min-w-0 flex-1">
                      {href ? (
                        <Link
                          href={href}
                          onClick={() => markRead.mutate(n.id)}
                          className="block"
                        >
                          <p
                            className={cn(
                              "truncate text-sm",
                              isUnread
                                ? "font-medium text-fg"
                                : "text-fg-muted",
                            )}
                          >
                            {label}
                          </p>
                          <p className="mt-0.5 text-xs text-fg-muted">
                            {n.primary_actor?.display_id != null
                              ? `Conversación #${n.primary_actor.display_id}`
                              : null}
                            {n.primary_actor?.display_id != null &&
                            n.last_activity_at
                              ? " · "
                              : null}
                            {relativeTime(n.last_activity_at)}
                          </p>
                        </Link>
                      ) : (
                        <>
                          <p
                            className={cn(
                              "truncate text-sm",
                              isUnread
                                ? "font-medium text-fg"
                                : "text-fg-muted",
                            )}
                          >
                            {label}
                          </p>
                          <p className="mt-0.5 text-xs text-fg-muted">
                            {relativeTime(n.last_activity_at)}
                          </p>
                        </>
                      )}
                    </div>
                    <div className="flex items-center gap-1">
                      {isUnread ? (
                        <button
                          type="button"
                          onClick={() => markRead.mutate(n.id)}
                          className="rounded-md px-2 py-1 text-xs text-fg-muted hover:bg-surface"
                        >
                          Marcar leído
                        </button>
                      ) : null}
                      <button
                        type="button"
                        aria-label="Borrar notificación"
                        onClick={() => deleteOne.mutate(n.id)}
                        className="rounded-md p-1 text-fg-muted hover:bg-surface"
                      >
                        <Trash2 className="h-4 w-4" aria-hidden />
                      </button>
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </CardContent>
      </Card>

      {totalPages > 1 ? (
        <nav
          aria-label="Paginación"
          className="flex items-center justify-between text-sm text-fg-muted"
        >
          <Button
            variant="secondary"
            disabled={page <= 1}
            onClick={() => setPage((p) => Math.max(1, p - 1))}
          >
            Anterior
          </Button>
          <span>
            Página {page} de {totalPages}
          </span>
          <Button
            variant="secondary"
            disabled={page >= totalPages}
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
          >
            Siguiente
          </Button>
        </nav>
      ) : null}
    </div>
  );
}
