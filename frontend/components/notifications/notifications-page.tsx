"use client";

import { CheckCheck, Trash2 } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { PageHeader } from "@/components/shell/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
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
    <div className="mx-auto max-w-3xl space-y-4">
      <PageHeader
        title="Notificaciones"
        description={
          <span className="font-numeric tabular-nums">
            {unread.data ?? 0} sin leer · {total} en total
          </span>
        }
        actions={
          <Button
            variant="secondary"
            size="sm"
            onClick={() => markAllRead.mutate()}
            disabled={!unread.data || markAllRead.isPending}
          >
            <CheckCheck className="h-4 w-4" aria-hidden />
            Marcar todo
          </Button>
        }
      />

      <Tabs
        value={filter}
        onValueChange={(next) => {
          setFilter(next as "all" | "unread");
          setPage(1);
        }}
      >
        <TabsList aria-label="Filtro">
          <TabsTrigger value="all">Todas</TabsTrigger>
          <TabsTrigger value="unread">No leídas</TabsTrigger>
        </TabsList>
      </Tabs>

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
            <ul className="divide-y divide-glass">
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
                    className="group/row flex items-center gap-3 px-4 py-3 transition-colors hover:bg-hover-glass"
                  >
                    <span
                      aria-hidden
                      className={cn(
                        "h-2 w-2 shrink-0 rounded-full",
                        isUnread ? "bg-neon" : "bg-transparent",
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
                          <p className="mt-0.5 font-numeric text-xs tabular-nums text-fg-muted">
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
                          <p className="mt-0.5 font-numeric text-xs tabular-nums text-fg-muted">
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
                          className="rounded-md px-2 py-1 text-xs text-fg-muted hover:bg-hover-glass hover:text-fg"
                        >
                          Marcar leído
                        </button>
                      ) : null}
                      <button
                        type="button"
                        aria-label="Borrar notificación"
                        onClick={() => deleteOne.mutate(n.id)}
                        className="rounded-md p-1 text-fg-muted hover:bg-hover-glass hover:text-danger"
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
          className="flex items-center justify-between font-numeric text-sm tabular-nums text-fg-muted"
        >
          <Button
            variant="secondary"
            size="sm"
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
            size="sm"
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
